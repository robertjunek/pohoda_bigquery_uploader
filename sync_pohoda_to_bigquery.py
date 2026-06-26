#!/usr/bin/env python3
"""
Synchronizace dat z MS SQL (Pohoda) do Google BigQuery.

Logika:
- Config je POLE nezávislých bloků; každý blok má vlastní MSSQL/BQ připojení,
  seznam databází (current + history) a seznam dotazů. Bloky se spouští samostatně.
- Pro každou databázi se spustí každý SQL dotaz a výsledek se streamuje po malých
  dávkách (fetchmany) přes dočasnou tabulku do cílové BQ tabulky.
- Mode (full/incremental) se určuje u každého dotazu v configu.
- Backfill spouští stejné dotazy proti historickým databázím (current je vždy
  poslední) a NIKDY netruncatuje cílovou tabulku - jen MERGE/append.
"""

import argparse
import decimal
import json
import logging
import os
import re
import sys
import uuid
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import pyodbc
import sentry_sdk
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from sentry_sdk import capture_exception

logger = logging.getLogger("pohoda_sync")

# Sloupce, které se NEpřevádějí na STRING.
DATE_COLUMNS = {"Datum"}
NUMERIC_COLUMNS = {"Mnozstvi", "KcJedn", "Kc", "Pocet", "Cena"}

# Tabulky Pohody, které je potřeba prefixovat [linked_server].[database].dbo.
PREFIX_TABLES = [
    "FA", "FApol",
    "PH", "PHpol",
    "SKPP", "SKPPpol",
    "SKPV", "SKPVpol",
    "SKz",
    "sStr", "sCin", "AD", "sZeme", "sSklad",
    "sFormUh", "Kasa",
]


# ---------------------------------------------------------------------------
# Čisté pomocné funkce (testovatelné bez připojení)
# ---------------------------------------------------------------------------

def load_config(config_path: str) -> List[dict]:
    """Načte config a vždy vrátí SEZNAM bloků.

    Top-level může být buď pole bloků, nebo (kvůli zpětné kompatibilitě) jeden
    objekt - ten se zabalí do seznamu o jednom prvku.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"CHYBA: Konfigurační soubor {config_path} nenalezen!")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"CHYBA: Neplatný JSON v konfiguračním souboru: {e}")
        sys.exit(1)

    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not data:
        print("CHYBA: Config musí být neprázdné pole bloků (nebo jeden objekt).")
        sys.exit(1)
    return data


def dedupe_columns(columns: List[str]) -> List[str]:
    """Ošetří duplicitní názvy sloupců (přidá _1, _2, ...)."""
    seen: Dict[str, int] = {}
    result = []
    for col in columns:
        if col in seen:
            seen[col] += 1
            result.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            result.append(col)
    return result


def prepare_sql(sql_content: str, linked_server: str, database: str, days_back: int) -> str:
    """Přidá prefix k tabulkám a dosadí <DAYS_BACK>.

    Args:
        sql_content: Obsah SQL souboru.
        linked_server: Název linked serveru.
        database: Název Pohoda databáze.
        days_back: Hodnota dosazená za placeholder <DAYS_BACK>.
    """
    prefix = f"[{linked_server}].[{database}].dbo."
    modified = sql_content
    for table in PREFIX_TABLES:
        for kw in ("FROM", "JOIN"):
            modified = re.sub(
                rf"\b{kw}\s+{table}\b",
                f"{kw} {prefix}{table}",
                modified,
                flags=re.IGNORECASE,
            )
    modified = re.sub(r"<DAYS_BACK>", str(days_back), modified)
    return modified


def build_bq_schema(columns: List[str]) -> List[bigquery.SchemaField]:
    """Sestaví BQ schéma z názvů sloupců (deterministicky, ne z dat).

    Datum -> TIMESTAMP, množství/ceny -> FLOAT64, zbytek -> STRING.
    """
    schema = []
    for col in columns:
        # base name bez sufixu z dedupe (Datum_1 atd.)
        base = re.sub(r"_\d+$", "", col)
        if base in DATE_COLUMNS:
            field_type = "TIMESTAMP"
        elif base in NUMERIC_COLUMNS:
            field_type = "FLOAT64"
        else:
            field_type = "STRING"
        schema.append(bigquery.SchemaField(col, field_type, mode="NULLABLE"))
    return schema


def _convert_value_to_string(val):
    if val is None or (not isinstance(val, (list, dict)) and pd.isna(val)):
        return None
    if isinstance(val, bytes):
        # GUID z SQL Serveru
        try:
            return str(uuid.UUID(bytes_le=val))
        except Exception:
            return val.hex()
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, decimal.Decimal):
        return str(val)
    return str(val)


def _convert_value_to_float(val, col):
    if val is None or pd.isna(val):
        return None
    if isinstance(val, decimal.Decimal):
        return float(val)
    try:
        return float(val)
    except (ValueError, TypeError):
        logger.warning(f"Nelze převést na float: {val} v sloupci {col}")
        return None


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Připraví DataFrame pro BigQuery (typy + NULL + bytes/Decimal)."""
    df = df.copy()
    df.columns = dedupe_columns(list(df.columns))

    for col in df.columns:
        base = re.sub(r"_\d+$", "", col)
        try:
            if base in DATE_COLUMNS:
                df[col] = pd.to_datetime(df[col], errors="coerce")
                df[col] = df[col].where(pd.notna(df[col]), None)
            elif base in NUMERIC_COLUMNS:
                df[col] = df[col].apply(lambda v: _convert_value_to_float(v, col))
            else:
                df[col] = df[col].apply(_convert_value_to_string)
        except Exception as e:
            logger.warning(f"Problém s převodem sloupce {col}: {e}, převádím na string")
            try:
                df[col] = df[col].astype(str).replace("nan", None).replace("None", None)
            except Exception:
                df[col] = None
    return df


def databases_to_process(
    databases_cfg: dict, backfill: bool, database_filter: Optional[str] = None
) -> List[dict]:
    """Vrátí seznam databází ke zpracování ve správném pořadí.

    - normální běh: jen current
    - backfill: historie v pořadí ze configu, current VŽDY poslední
    - database_filter: omezí na databázi daného jména (z current i history)
    """
    current = databases_cfg["current"]
    history = databases_cfg.get("history", []) if backfill else []

    if backfill:
        ordered = list(history) + [current]
    else:
        ordered = [current]

    if database_filter:
        ordered = [db for db in ordered if db.get("database") == database_filter]

    return ordered


def build_finalize_statements(
    mode: str, backfill: bool, target_id: str, temp_id: str, key: str, columns: List[str]
) -> List[str]:
    """Sestaví SQL příkazy pro finalizaci (z temp tabulky do cílové).

    - normální + full: CREATE OR REPLACE TABLE target AS SELECT * FROM temp
    - incremental (i backfill): MERGE podle key
    - backfill + full: append (INSERT INTO target SELECT * FROM temp)
    """
    if mode == "full" and not backfill:
        return [f"CREATE OR REPLACE TABLE `{target_id}` AS SELECT * FROM `{temp_id}`"]

    ensure = f"CREATE TABLE IF NOT EXISTS `{target_id}` LIKE `{temp_id}`"

    if mode == "incremental":
        non_key = [c for c in columns if c != key]
        set_clause = ", ".join(f"T.`{c}` = S.`{c}`" for c in non_key)
        insert_cols = ", ".join(f"`{c}`" for c in columns)
        insert_vals = ", ".join(f"S.`{c}`" for c in columns)
        # Zdroj musí mít klíč unikátní (jinak BigQuery MERGE selže s
        # "must match at most one source row for each target row").
        # Deduplikujeme - na klíč ponecháme jeden řádek.
        dedup_source = (
            f"(SELECT * FROM `{temp_id}` "
            f"QUALIFY ROW_NUMBER() OVER (PARTITION BY `{key}` ORDER BY `{key}`) = 1)"
        )
        merge = f"""
            MERGE `{target_id}` T
            USING {dedup_source} S
            ON T.`{key}` = S.`{key}`
            WHEN MATCHED THEN UPDATE SET {set_clause}
            WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})
        """.strip()
        return [ensure, merge]

    # backfill + full -> append
    return [ensure, f"INSERT INTO `{target_id}` SELECT * FROM `{temp_id}`"]


# ---------------------------------------------------------------------------
# Hlavní třída - jeden config blok
# ---------------------------------------------------------------------------

class PohodaBigQuerySync:
    """Synchronizace pro JEDEN config blok."""

    def __init__(self, config: dict):
        self.config = config
        self.name = config.get("name", "default")
        self.mssql_conn = None
        self.bq_client = None

    # --- připojení ---------------------------------------------------------

    def connect_mssql(self):
        cfg = self.config["mssql"]
        conn_str = (
            f"DRIVER={{{cfg['driver']}}};"
            f"SERVER={cfg['server']};"
            f"DATABASE={cfg['database']};"
            f"UID={cfg['username']};"
            f"PWD={cfg['password']};"
            f"Timeout={cfg['timeout']};"
        )
        if cfg.get("trust_server_certificate", False):
            conn_str += "TrustServerCertificate=yes;"
        try:
            self.mssql_conn = pyodbc.connect(conn_str)
            logger.info(f"[{self.name}] Připojeno k MS SQL: {cfg['server']}")
        except pyodbc.Error as e:
            logger.error(f"[{self.name}] Chyba připojení k MS SQL: {e}")
            capture_exception(e)
            raise

    def connect_bigquery(self):
        cfg = self.config["bigquery"]
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cfg["credentials_file"]
        try:
            self.bq_client = bigquery.Client(
                project=cfg["project_id"], location=cfg["location"]
            )
            logger.info(f"[{self.name}] Připojeno k BigQuery: {cfg['project_id']}")
            self._ensure_dataset_exists()
        except Exception as e:
            logger.error(f"[{self.name}] Chyba připojení k BigQuery: {e}")
            capture_exception(e)
            raise

    def _ensure_dataset_exists(self):
        cfg = self.config["bigquery"]
        dataset_ref = f"{cfg['project_id']}.{cfg['dataset']}"
        try:
            self.bq_client.get_dataset(dataset_ref)
        except NotFound:
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = cfg["location"]
            self.bq_client.create_dataset(dataset, timeout=30)
            logger.info(f"[{self.name}] Dataset {cfg['dataset']} vytvořen")

    def close(self):
        if self.mssql_conn:
            try:
                self.mssql_conn.close()
            except Exception as e:
                logger.warning(f"[{self.name}] Chyba při zavírání MS SQL: {e}")
        if self.bq_client:
            try:
                self.bq_client.close()
            except Exception as e:
                logger.warning(f"[{self.name}] Chyba při zavírání BigQuery: {e}")

    # --- pomocné -----------------------------------------------------------

    def _table_id(self, table_name: str) -> str:
        cfg = self.config["bigquery"]
        return f"{cfg['project_id']}.{cfg['dataset']}.{table_name}"

    def _load_sql_file(self, sql_file: str) -> str:
        path = Path(sql_file)
        if not path.exists():
            raise FileNotFoundError(f"SQL soubor {sql_file} nenalezen")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _create_temp_table(self, temp_id: str, schema: List[bigquery.SchemaField]):
        try:
            self.bq_client.delete_table(temp_id, not_found_ok=True)
        except Exception:
            pass
        table = bigquery.Table(temp_id, schema=schema)
        self.bq_client.create_table(table)

    def _stream_to_temp(self, cursor, columns, schema, temp_id, batch_size) -> int:
        """Streamuje řádky z kurzoru po dávkách do temp tabulky."""
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            schema=schema,
            ignore_unknown_values=True,
        )
        total = 0
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            df = pd.DataFrame.from_records(
                [tuple(r) for r in rows], columns=columns
            )
            df = prepare_dataframe(df)
            job = self.bq_client.load_table_from_dataframe(
                df, temp_id, job_config=job_config
            )
            job.result()
            total += len(df)
            logger.info(f"[{self.name}]   nahráno do temp: {total} řádků")
        return total

    # --- jeden dotaz × jedna databáze -------------------------------------

    def sync_query(self, db: dict, query_cfg: dict, backfill: bool):
        sql_file = query_cfg["file"]
        table_name = Path(sql_file).stem
        mode = query_cfg.get("mode", "incremental")
        key = query_cfg.get("key", "ID")

        sync_cfg = self.config["sync"]
        batch_size = sync_cfg.get("batch_size", 5000)
        if backfill:
            days_back = sync_cfg.get("backfill_days_back", 4000)
        else:
            days_back = query_cfg.get("days_back", sync_cfg.get("days_back", 7))

        linked_server = db["linked_server"]
        database = db["database"]

        logger.info(
            f"[{self.name}] {database} / {table_name} "
            f"(mode={mode}, backfill={backfill}, days_back={days_back})"
        )

        sql = prepare_sql(self._load_sql_file(sql_file), linked_server, database, days_back)

        target_id = self._table_id(table_name)
        temp_id = f"{target_id}_temp_{int(datetime.now().timestamp())}"

        cursor = self.mssql_conn.cursor()
        try:
            cursor.execute(sql)
            columns = dedupe_columns([d[0] for d in cursor.description])
            schema = build_bq_schema(columns)

            self._create_temp_table(temp_id, schema)
            total = self._stream_to_temp(cursor, columns, schema, temp_id, batch_size)
            cursor.close()

            statements = build_finalize_statements(
                mode, backfill, target_id, temp_id, key, columns
            )
            for stmt in statements:
                self.bq_client.query(stmt).result()

            logger.info(
                f"[{self.name}] ✓ {database} / {table_name}: {total} řádků "
                f"({'append' if backfill and mode == 'full' else mode})"
            )
        except Exception as e:
            logger.error(f"[{self.name}] Chyba u {database}/{table_name}: {e}")
            capture_exception(e)
            raise
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            try:
                self.bq_client.delete_table(temp_id, not_found_ok=True)
            except Exception:
                pass

    # --- běh bloku ---------------------------------------------------------

    def run(self, backfill: bool = False, database: Optional[str] = None,
            only: Optional[List[str]] = None) -> bool:
        start = datetime.now()
        logger.info("=" * 70)
        logger.info(
            f"[{self.name}] START (backfill={backfill}"
            + (f", database={database}" if database else "")
            + ")"
        )
        try:
            self.connect_mssql()
            self.connect_bigquery()

            dbs = databases_to_process(self.config["databases"], backfill, database)
            if not dbs:
                logger.warning(f"[{self.name}] Žádná databáze ke zpracování (filter={database})")
                return True

            queries = self.config["sync"]["queries"]
            if only:
                queries = [q for q in queries if q["file"] in only]

            for db in dbs:
                for query_cfg in queries:
                    self.sync_query(db, query_cfg, backfill)

            dur = (datetime.now() - start).total_seconds()
            logger.info(f"[{self.name}] ✓ Hotovo za {dur:.1f}s")
            return True
        except Exception as e:
            dur = (datetime.now() - start).total_seconds()
            logger.error(f"[{self.name}] ✗ Selhalo po {dur:.1f}s: {e}")
            capture_exception(e)
            return False
        finally:
            self.close()


# ---------------------------------------------------------------------------
# Orchestrace + CLI
# ---------------------------------------------------------------------------

def setup_logging(log_config: dict):
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_config.get("log_level", "INFO")))

    file_handler = RotatingFileHandler(
        log_config.get("log_file", "sync.log"),
        maxBytes=log_config.get("max_bytes", 10485760),
        backupCount=log_config.get("backup_count", 5),
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)


def setup_sentry(blocks: List[dict]):
    for block in blocks:
        sc = block.get("sentry", {})
        dsn = sc.get("dsn")
        if dsn and dsn != "your_sentry_dsn_here":
            try:
                sentry_sdk.init(
                    dsn=dsn,
                    environment=sc.get("environment", "production"),
                    traces_sample_rate=sc.get("traces_sample_rate", 0.1),
                )
                logger.info("Sentry inicializováno")
            except Exception as e:
                logger.warning(f"Nepodařilo se inicializovat Sentry: {e}")
            return


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Synchronizace Pohoda (MS SQL) -> BigQuery"
    )
    parser.add_argument("--config", default="config.json", help="Cesta ke configu")
    parser.add_argument("--backfill", action="store_true",
                        help="Spustit i historické databáze (current poslední)")
    parser.add_argument("--database", help="Omezit na jednu konkrétní databázi")
    parser.add_argument("--block", help="Omezit na jeden config blok podle 'name'")
    parser.add_argument("--only", help="Omezit na vybrané SQL soubory (čárkou oddělené)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    # Změna do složky se skriptem (kvůli relativním cestám ke configu/SQL)
    os.chdir(Path(__file__).parent)

    blocks = load_config(args.config)

    if args.block:
        blocks = [b for b in blocks if b.get("name") == args.block]
        if not blocks:
            print(f"CHYBA: Config blok '{args.block}' nenalezen.")
            sys.exit(1)

    setup_logging(blocks[0].get("logging", {}))
    setup_sentry(blocks)

    only = [s.strip() for s in args.only.split(",")] if args.only else None

    all_ok = True
    for block in blocks:
        syncer = PohodaBigQuerySync(block)
        ok = syncer.run(backfill=args.backfill, database=args.database, only=only)
        all_ok = all_ok and ok

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nPřerušeno uživatelem")
        sys.exit(130)
    except Exception as exc:
        print(f"\nKritická chyba: {exc}")
        capture_exception(exc)
        sys.exit(1)
