#!/usr/bin/env python3
"""
Skript pro synchronizaci dat z MS SQL (Pohoda) do Google BigQuery.
Stahuje data po dávkách a nahrává je do BigQuery.
"""

import json
import logging
import os
import re
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd
import pyodbc
import sentry_sdk
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from sentry_sdk import capture_exception, capture_message


class PohodaBigQuerySync:
    """Třída pro synchronizaci dat z Pohoda do BigQuery."""

    def __init__(self, config_path: str = "config.json"):
        """
        Inicializace synchronizátoru.
        
        Args:
            config_path: Cesta ke konfiguračnímu souboru
        """
        self.config = self._load_config(config_path)
        self._setup_logging()
        self._setup_sentry()
        
        self.mssql_conn = None
        self.bq_client = None
        self.linked_server = None
        self.pohoda_database = None
        self.sync_mode = self.config['sync'].get('mode', 'full')

    def _load_config(self, config_path: str) -> dict:
        """Načtení konfigurace ze souboru."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"CHYBA: Konfigurační soubor {config_path} nenalezen!")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"CHYBA: Neplatný JSON v konfiguračním souboru: {e}")
            sys.exit(1)

    def _setup_logging(self):
        """Nastavení logování do souboru a konzole."""
        log_config = self.config['logging']
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Root logger
        logger = logging.getLogger()
        logger.setLevel(getattr(logging, log_config['log_level']))
        
        # File handler s rotací
        file_handler = RotatingFileHandler(
            log_config['log_file'],
            maxBytes=log_config['max_bytes'],
            backupCount=log_config['backup_count'],
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        self.logger = logger

    def _setup_sentry(self):
        """Nastavení Sentry pro error tracking."""
        sentry_config = self.config.get('sentry', {})
        dsn = sentry_config.get('dsn')
        
        if dsn and dsn != "your_sentry_dsn_here":
            try:
                sentry_sdk.init(
                    dsn=dsn,
                    environment=sentry_config.get('environment', 'production'),
                    traces_sample_rate=sentry_config.get('traces_sample_rate', 0.1)
                )
                self.logger.info("Sentry inicializováno úspěšně")
            except Exception as e:
                self.logger.warning(f"Nepodařilo se inicializovat Sentry: {e}")
        else:
            self.logger.info("Sentry není nakonfigurováno, error tracking vypnut")

    def connect_mssql(self):
        """Připojení k MS SQL serveru."""
        try:
            mssql_config = self.config['mssql']
            
            connection_string = (
                f"DRIVER={{{mssql_config['driver']}}};"
                f"SERVER={mssql_config['server']};"
                f"DATABASE={mssql_config['database']};"
                f"UID={mssql_config['username']};"
                f"PWD={mssql_config['password']};"
                f"Timeout={mssql_config['timeout']};"
            )
            
            # Přidání TrustServerCertificate pokud je v konfiguraci
            if mssql_config.get('trust_server_certificate', False):
                connection_string += "TrustServerCertificate=yes;"
            
            self.mssql_conn = pyodbc.connect(connection_string)
            self.logger.info(f"Připojeno k MS SQL serveru: {mssql_config['server']}")
            
        except pyodbc.Error as e:
            self.logger.error(f"Chyba při připojení k MS SQL: {e}")
            capture_exception(e)
            raise

    def connect_bigquery(self):
        """Připojení k BigQuery."""
        try:
            bq_config = self.config['bigquery']
            credentials_path = bq_config['credentials_file']
            
            # Nastavení proměnné prostředí pro credentials
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            
            self.bq_client = bigquery.Client(
                project=bq_config['project_id'],
                location=bq_config['location']
            )
            
            self.logger.info(f"Připojeno k BigQuery projektu: {bq_config['project_id']}")
            
            # Ujištění, že dataset existuje
            self._ensure_dataset_exists()
            
        except Exception as e:
            self.logger.error(f"Chyba při připojení k BigQuery: {e}")
            capture_exception(e)
            raise

    def _ensure_dataset_exists(self):
        """Zajistí, že dataset v BigQuery existuje."""
        try:
            dataset_id = self.config['bigquery']['dataset']
            dataset_ref = f"{self.config['bigquery']['project_id']}.{dataset_id}"
            
            try:
                self.bq_client.get_dataset(dataset_ref)
                self.logger.info(f"Dataset {dataset_id} již existuje")
            except NotFound:
                # Dataset neexistuje, vytvoříme ho
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = self.config['bigquery']['location']
                dataset = self.bq_client.create_dataset(dataset, timeout=30)
                self.logger.info(f"Dataset {dataset_id} vytvořen")
                
        except Exception as e:
            self.logger.error(f"Chyba při kontrole/vytváření datasetu: {e}")
            capture_exception(e)
            raise

    def _ensure_sync_metadata_table(self):
        """Zajistí, že existuje tabulka pro tracking synchronizace."""
        try:
            dataset_id = self.config['bigquery']['dataset']
            project_id = self.config['bigquery']['project_id']
            table_id = f"{project_id}.{dataset_id}._sync_metadata"
            
            # Zkontrolujeme, zda tabulka existuje
            try:
                self.bq_client.get_table(table_id)
                self.logger.debug("Metadata tabulka už existuje")
                return
            except NotFound:
                pass
            
            # Vytvoříme metadata tabulku
            schema = [
                bigquery.SchemaField("table_name", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("last_sync_timestamp", "TIMESTAMP"),
                bigquery.SchemaField("last_max_date", "DATE"),
                bigquery.SchemaField("records_synced", "INTEGER"),
                bigquery.SchemaField("sync_mode", "STRING"),
                bigquery.SchemaField("created_at", "TIMESTAMP"),
                bigquery.SchemaField("updated_at", "TIMESTAMP"),
            ]
            
            table = bigquery.Table(table_id, schema=schema)
            table = self.bq_client.create_table(table)
            self.logger.info("Metadata tabulka _sync_metadata vytvořena")
            
        except Exception as e:
            self.logger.error(f"Chyba při vytváření metadata tabulky: {e}")
            capture_exception(e)
            raise

    def get_last_sync_info(self, table_name: str) -> dict:
        """
        Zkontroluje, zda tabulka v BigQuery existuje.
        NEPOUŽÍVÁ metadata tabulku - pouze kontroluje existenci.
        
        Returns:
            dict: {'exists': bool}
        """
        try:
            dataset_id = self.config['bigquery']['dataset']
            project_id = self.config['bigquery']['project_id']
            table_id = f"{project_id}.{dataset_id}.{table_name}"
            
            # Zkontrolujeme, zda hlavní tabulka existuje
            table_exists = True
            try:
                self.bq_client.get_table(table_id)
            except NotFound:
                table_exists = False
                
            return {
                'exists': table_exists
            }
            
        except Exception as e:
            self.logger.warning(f"Chyba při získávání info o tabulce {table_name}: {e}")
            return {
                'exists': False
            }

    def update_sync_metadata(self, table_name: str, records_count: int, max_date):
        """Aktualizuje metadata o synchronizaci."""
        try:
            dataset_id = self.config['bigquery']['dataset']
            project_id = self.config['bigquery']['project_id']
            metadata_table_id = f"{project_id}.{dataset_id}._sync_metadata"
            
            # Bezpečné formátování data
            if hasattr(max_date, 'strftime'):
                date_str = max_date.strftime('%Y-%m-%d')
            else:
                date_str = str(max_date)
            
            # MERGE metadata
            merge_query = f"""
                MERGE `{metadata_table_id}` T
                USING (
                    SELECT 
                        '{table_name}' as table_name,
                        CURRENT_TIMESTAMP() as last_sync_timestamp,
                        CAST('{date_str}' AS DATE) as last_max_date,
                        {records_count} as records_synced,
                        '{self.sync_mode}' as sync_mode,
                        CURRENT_TIMESTAMP() as created_at,
                        CURRENT_TIMESTAMP() as updated_at
                ) S
                ON T.table_name = S.table_name
                WHEN MATCHED THEN UPDATE SET
                    last_sync_timestamp = S.last_sync_timestamp,
                    last_max_date = S.last_max_date,
                    records_synced = S.records_synced,
                    sync_mode = S.sync_mode,
                    updated_at = S.updated_at
                WHEN NOT MATCHED THEN INSERT VALUES(
                    S.table_name, S.last_sync_timestamp, S.last_max_date,
                    S.records_synced, S.sync_mode, S.created_at, S.updated_at
                )
            """
            
            self.bq_client.query(merge_query).result()
            self.logger.debug(f"Metadata aktualizovány pro {table_name}")
            
        except Exception as e:
            self.logger.warning(f"Chyba při aktualizaci metadata pro {table_name}: {e}")

    def get_pohoda_connection_info(self) -> Tuple[str, str]:
        """
        Získání informací o linked serveru a databázi.
        
        Returns:
            Tuple[linked_server, database]
        """
        try:
            query = "SELECT TOP 1 linked_server, [database] FROM companies"
            
            cursor = self.mssql_conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
            cursor.close()
            
            if not row:
                raise ValueError("Tabulka companies neobsahuje žádné záznamy")
            
            self.linked_server = row.linked_server
            self.pohoda_database = row.database
            
            self.logger.info(
                f"Pohoda connection: linked_server={self.linked_server}, "
                f"database={self.pohoda_database}"
            )
            
            return self.linked_server, self.pohoda_database
            
        except Exception as e:
            self.logger.error(f"Chyba při získávání connection info: {e}")
            capture_exception(e)
            raise

    def _add_table_prefix(self, sql_content: str, sync_info: dict = None, table_name: str = None) -> str:
        """
        Přidá prefix ke všem tabulkám v SQL dotazu.
        IGNORUJE metadata - používá pouze days_back z konfigurace.
        
        Args:
            sql_content: Obsah SQL souboru
            sync_info: Informace o tabulce (nepoužívá se pro datum)
            table_name: Název tabulky
            
        Returns:
            Upravený SQL dotaz s prefixy
        """
        # Prefix pro tabulky: [linked_server].[database].dbo.
        prefix = f"[{self.linked_server}].[{self.pohoda_database}].dbo."
        
        # Seznam tabulek, které potřebujeme prefixovat
        tables = [
            'FA', 'FApol',
            'PH', 'PHpol',
            'SKPP', 'SKPPpol',
            'SKPV', 'SKPVpol',
            'sStr', 'sCin', 'AD', 'sZeme', 'sSklad',
            'sFormUh', 'Kasa'
        ]
        
        modified_sql = sql_content
        
        # Regex pattern pro nalezení tabulek (FROM/JOIN table)
        for table in tables:
            # Pattern pro FROM/JOIN následovaný názvem tabulky
            patterns = [
                (rf'\bFROM\s+{table}\b', f'FROM {prefix}{table}'),
                (rf'\bJOIN\s+{table}\b', f'JOIN {prefix}{table}'),
            ]
            
            for pattern, replacement in patterns:
                modified_sql = re.sub(
                    pattern,
                    replacement,
                    modified_sql,
                    flags=re.IGNORECASE
                )

        # Určení days_back podle sync mode - IGNORUJEME metadata
        if self.sync_mode == 'full':
            days_back = self.config['sync'].get('full_sync_days_back', 
                                              self.config['sync'].get('days_back', 14))
            self.logger.info(f"Full load pro {table_name} - days_back: {days_back}")
        else:
            # Incremental - také používá days_back
            days_back = self.config['sync'].get('days_back', 7)
            self.logger.info(f"Incremental load pro {table_name} - days_back: {days_back}")

        # Nahrazení placeholderu <DAYS_BACK>
        modified_sql = re.sub(r'<DAYS_BACK>', str(days_back), modified_sql)
        
        return modified_sql

    

    def load_and_prepare_sql(self, sql_file: str, sync_info: dict = None) -> str:
        """
        Načte SQL soubor a přidá prefixy k tabulkám.
        
        Args:
            sql_file: Název SQL souboru
            sync_info: Informace o poslední synchronizaci
            
        Returns:
            Upravený SQL dotaz
        """
        try:
            sql_path = Path(sql_file)
            
            if not sql_path.exists():
                raise FileNotFoundError(f"SQL soubor {sql_file} nenalezen")
            
            with open(sql_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # Přidání prefixů a incremental logiky
            table_name = sql_path.stem
            modified_sql = self._add_table_prefix(sql_content, sync_info, table_name)
            
            self.logger.debug(f"SQL dotaz připraven z {sql_file}")
            return modified_sql
            
        except Exception as e:
            self.logger.error(f"Chyba při načítání SQL souboru {sql_file}: {e}")
            capture_exception(e)
            raise

    def fetch_data_in_batches(self, sql_query: str, batch_size: int) -> pd.DataFrame:
        """
        Stáhne všechna data z databáze.
        
        Args:
            sql_query: SQL dotaz
            batch_size: Velikost dávky (pro informaci)
            
        Returns:
            DataFrame se všemi daty
        """
        try:
            self.logger.info(f"Stahuji data z MS SQL (batch size: {batch_size})...")
            
            # Použití pyodbc cursor s manuálním načtením pro lepší kontrolu
            cursor = self.mssql_conn.cursor()
            cursor.execute(sql_query)
            
            # Získání názvů sloupců a jejich typů
            columns = [desc[0] for desc in cursor.description]
            col_types = [desc[1] for desc in cursor.description]
            
            # Logování typů sloupců pro debugging
            for col, col_type in zip(columns, col_types):
                self.logger.debug(f"Sloupec {col}: type={col_type}")
            
            # Načtení všech dat
            rows = cursor.fetchall()
            cursor.close()
            
            # Vytvoření DataFrame
            df = pd.DataFrame.from_records(rows, columns=columns)
            
            # Diagnostic: kontrola typů v DataFrame (použijeme df.columns místo columns, kvůli duplicitám)
            for col in df.columns:
                if len(df) > 0:
                    try:
                        col_data = df[col]
                        sample_val = col_data.dropna().iloc[0] if len(col_data.dropna()) > 0 else None
                        if sample_val is not None:
                            self.logger.debug(f"DF sloupec {col}: dtype={col_data.dtype}, sample type={type(sample_val)}, sample={sample_val}")
                    except Exception as e:
                        self.logger.debug(f"DF sloupec {col}: error getting sample - {e}")
            
            self.logger.info(f"Staženo {len(df)} záznamů")
            return df
            
        except Exception as e:
            self.logger.error(f"Chyba při stahování dat: {e}")
            capture_exception(e)
            raise

    def _prepare_dataframe_for_bigquery(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Připraví DataFrame pro nahrání do BigQuery.
        Ošetří NULL hodnoty a datové typy a duplicitní sloupce.
        
        Args:
            df: Původní DataFrame
            
        Returns:
            Upravený DataFrame
        """
        import decimal
        import datetime
        
        df = df.copy()
        
        # Ošetření duplicitních názvů sloupců
        cols = list(df.columns)
        seen = {}
        for i, col in enumerate(cols):
            if col in seen:
                # Duplicitní sloupec - přidáme číslo
                seen[col] += 1
                cols[i] = f"{col}_{seen[col]}"
            else:
                seen[col] = 0
        df.columns = cols
        
        # Ošetření datových typů a NULL hodnot
        for col in df.columns:
            try:
                # Kontrola na binární data (bytestring) - typicky GUID/UUID z SQL Serveru
                if df[col].dtype == 'object':
                    non_null_values = df[col].dropna()
                    if len(non_null_values) > 0:
                        first_val = non_null_values.iloc[0]
                        
                        # Pokud je to datetime.date, převeď na pandas datetime
                        if isinstance(first_val, (datetime.date, datetime.datetime)):
                            self.logger.info(f"Sloupec {col} obsahuje date/datetime, převádím na pandas datetime")
                            df[col] = pd.to_datetime(df[col])
                            continue
                        
                        # Pokud je to decimal.Decimal, převeď na float
                        if isinstance(first_val, decimal.Decimal):
                            self.logger.info(f"Sloupec {col} obsahuje Decimal, převádím na float")
                            def convert_decimal(val):
                                if val is None or pd.isna(val):
                                    return None
                                if isinstance(val, decimal.Decimal):
                                    return float(val)
                                return val
                            
                            df[col] = df[col].apply(convert_decimal)
                            continue
                        
                        # Pokud je to bytes, je to pravděpodobně GUID z SQL Serveru
                        if isinstance(first_val, bytes):
                            self.logger.info(f"Sloupec {col} obsahuje binární data (GUID), převádím na string")
                            def convert_guid(val):
                                if val is None or pd.isna(val):
                                    return None
                                if isinstance(val, bytes):
                                    try:
                                        # Pokus o převod bytes na UUID string
                                        import uuid
                                        # SQL Server GUID má jiné pořadí bytů
                                        return str(uuid.UUID(bytes_le=val))
                                    except Exception as e:
                                        self.logger.warning(f"Nepodařilo se převést GUID: {e}, používám hex")
                                        return val.hex()
                                return str(val)
                            
                            df[col] = df[col].apply(convert_guid)
                            continue
                        
                        # Test zda obsahuje mix čísel a stringů
                        has_numeric = False
                        has_string = False
                        
                        for val in non_null_values.head(100):  # Sample prvních 100 hodnot
                            if pd.api.types.is_number(val):
                                has_numeric = True
                            elif isinstance(val, str) and val.strip():
                                has_string = True
                            
                            if has_numeric and has_string:
                                break
                        
                        # Pokud obsahuje mix, převeď vše na string
                        if has_numeric and has_string:
                            self.logger.warning(f"Sloupec {col} obsahuje mixed types, převádím na string")
                            df[col] = df[col].astype(str).replace('nan', None).replace('None', None)
                        else:
                            # Jen stringy nebo jen čísla
                            df[col] = df[col].where(pd.notna(df[col]), None)
                    else:
                        # Prázdný sloupec
                        df[col] = None
                        
                elif df[col].dtype in ['int64', 'float64']:
                    # Numeric sloupce - nahraď NaN jako None pro BigQuery
                    df[col] = df[col].where(pd.notna(df[col]), None)
                    
                elif 'datetime' in str(df[col].dtype):
                    # Datetime sloupce - ošetření NaT
                    df[col] = df[col].where(pd.notna(df[col]), None)
                    
            except Exception as e:
                self.logger.warning(f"Problém s převodem sloupce {col}: {e}, převádím na string")
                # Pokud selže cokoliv, převeď sloupec na string
                try:
                    df[col] = df[col].astype(str).replace('nan', None).replace('None', None)
                except:
                    df[col] = None
        
        return df

    def _get_bigquery_schema_from_dataframe(self, df: pd.DataFrame) -> list:
        """
        Vytvoří BigQuery schéma z DataFrame s bezpečnými typy.
        Automaticky detekuje typy ze sloupců DataFrame.
        
        Args:
            df: DataFrame pro analýzu
            
        Returns:
            Seznam BigQuery SchemaField objektů
        """
        schema = []
        
        for col in df.columns:
            # Automatická detekce typu podle pandas dtype
            dtype_str = str(df[col].dtype)
            
            if col == 'ID':
                # ID je vždy string
                field_type = "STRING"
            elif 'datetime' in dtype_str or 'timestamp' in dtype_str:
                # Datetime sloupce
                field_type = "TIMESTAMP"
            elif dtype_str == 'float64':
                # Float sloupce
                field_type = "FLOAT64"
            elif dtype_str in ['int64', 'int32', 'int16']:
                # Integer sloupce
                field_type = "INTEGER"
            elif dtype_str == 'bool':
                # Boolean sloupce
                field_type = "BOOLEAN"
            else:
                # Vše ostatní jako STRING (object, string, mixed types)
                field_type = "STRING"
            
            schema.append(
                bigquery.SchemaField(
                    col, 
                    field_type, 
                    mode="NULLABLE"  # Všechny sloupce můžou být NULL
                )
            )
        
        return schema

    def _validate_and_fix_types(self, df: pd.DataFrame, table_name: str, schema: list) -> pd.DataFrame:
        """
        Zkontroluje DataFrame proti schématu a zaloguje konkrétní sloupce/ID, které
        obsahují hodnoty nekonzistentní s očekávaným typem. Nevalidní hodnoty se
        přepíší na None, aby nahrání do BigQuery nepadalo.

        Args:
            df: DataFrame ke kontrole
            table_name: název tabulky (pro logování)
            schema: seznam bigquery.SchemaField

        Returns:
            upravený DataFrame
        """
        if df is None or len(df) == 0:
            return df

        df = df.copy()

        # map column -> expected type (STRING, INTEGER, NUMERIC, DATE...)
        expected = {f.name: f.field_type for f in (schema or [])}

        for col, expected_type in expected.items():
            if col not in df.columns:
                continue

            # Only validate numeric-like types
            if expected_type in ("INTEGER", "NUMERIC"):
                series = df[col]
                # Consider non-null samples
                non_null = series[series.notna()]
                if non_null.empty:
                    continue

                # Try coercion to numeric
                coerced = pd.to_numeric(non_null, errors='coerce')
                invalid_mask = coerced.isna()

                if invalid_mask.any():
                    # Collect sample of offending rows (up to 10)
                    invalid_idx = invalid_mask[invalid_mask].index.tolist()[:10]
                    samples = []
                    for idx in invalid_idx:
                        try:
                            id_val = df.at[idx, 'ID'] if 'ID' in df.columns else 'N/A'
                        except Exception:
                            id_val = 'N/A'
                        val = df.at[idx, col]
                        samples.append({'index': idx, 'id': id_val, 'value': val})

                    # Log clear message
                    self.logger.error(
                        f"Datatype mismatch in table={table_name} column={col}: "
                        f"expected={expected_type} but found {len(invalid_mask[invalid_mask])} non-numeric values. "
                        f"Samples={samples}"
                    )

                    # Coerce invalids to None to avoid load failure
                    # Operate on original dataframe indices
                    for idx in invalid_mask[invalid_mask].index:
                        # Only if value is not already NaN
                        try:
                            if pd.notna(df.at[idx, col]):
                                df.at[idx, col] = None
                        except Exception:
                            df.at[idx, col] = None

                # Finally convert whole column to numeric (nullable)
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                except Exception:
                    # If conversion fails, leave as is (None for invalids)
                    pass

        return df

    def upload_to_bigquery(self, df: pd.DataFrame, table_name: str, batch_size: int):
        """
        Nahraje data do BigQuery po dávkách.
        
        Args:
            df: DataFrame s daty
            table_name: Název tabulky v BigQuery
            batch_size: Velikost dávky pro nahrávání
        """
        try:
            dataset_id = self.config['bigquery']['dataset']
            project_id = self.config['bigquery']['project_id']
            table_id = f"{project_id}.{dataset_id}.{table_name}"
            
            total_rows = len(df)
            
            if total_rows == 0:
                self.logger.warning(f"Žádná data k nahrání pro tabulku {table_name}")
                return
            
            # Ošetření NULL hodnot a datových typů
            df = self._prepare_dataframe_for_bigquery(df)
            
            # Dodatečná kontrola na problematické typy
            for col in df.columns:
                if df[col].dtype == 'object':
                    sample = df[col].dropna().head(5)
                    for idx, val in sample.items():
                        if isinstance(val, bytes):
                            self.logger.error(f"CHYBA: Sloupec {col} stále obsahuje bytes po konverzi! row={idx}, val={val[:20]}")
            
            self.logger.info(f"Nahrávám {total_rows} záznamů do {table_id}...")
            
            # Získání explicitního schématu
            schema = self._get_bigquery_schema_from_dataframe(df)
            
            # Konfigurace pro load job s explicitním schématem
            job_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                schema=schema,
                # Povolíme nekonzistentní types a chybné hodnoty
                allow_jagged_rows=False,
                allow_quoted_newlines=True,
                ignore_unknown_values=True,
            )
            
            # Nahrávání po dávkách
            uploaded = 0
            for i in range(0, total_rows, batch_size):
                batch = df.iloc[i:i + batch_size]
                
                # První batch použije WRITE_TRUNCATE, další WRITE_APPEND
                if i > 0:
                    job_config.write_disposition = bigquery.WriteDisposition.WRITE_APPEND
                
                job = self.bq_client.load_table_from_dataframe(
                    batch,
                    table_id,
                    job_config=job_config
                )
                
                job.result()  # Čekání na dokončení
                
                uploaded += len(batch)
                self.logger.info(
                    f"Nahráno {uploaded}/{total_rows} záznamů "
                    f"({uploaded/total_rows*100:.1f}%)"
                )
            
            self.logger.info(f"✓ Tabulka {table_name} úspěšně nahrána do BigQuery")
            
        except Exception as e:
            self.logger.error(f"Chyba při nahrávání do BigQuery: {e}")
            
            # Dodatečná diagnostika
            self.logger.error("Diagnostika DataFrame:")
            for col in df.columns:
                try:
                    sample = df[col].dropna().head(1)
                    if len(sample) > 0:
                        val = sample.iloc[0]
                        self.logger.error(f"  {col}: type={type(val)}, value={val}")
                except Exception as diag_e:
                    self.logger.error(f"  {col}: diagnostic error={diag_e}")
            
            capture_exception(e)
            raise

    def upload_with_merge(self, df: pd.DataFrame, table_name: str, batch_size: int):
        """
        Nahraje data do BigQuery pomocí MERGE operace pro incremental update.
        
        Args:
            df: DataFrame s daty
            table_name: Název tabulky v BigQuery  
            batch_size: Velikost dávky pro nahrávání
        """
        try:
            dataset_id = self.config['bigquery']['dataset']
            project_id = self.config['bigquery']['project_id']
            table_id = f"{project_id}.{dataset_id}.{table_name}"
            temp_table_id = f"{project_id}.{dataset_id}.{table_name}_temp_{int(datetime.now().timestamp())}"
            
            total_rows = len(df)
            
            if total_rows == 0:
                self.logger.warning(f"Žádná data k nahrání pro tabulku {table_name}")
                return
                
            # Ošetření DataFrame
            df = self._prepare_dataframe_for_bigquery(df)
            
            self.logger.info(f"Incremental sync - MERGE {total_rows} záznamů do {table_id}")
            
            # Získání explicitního schématu
            schema = self._get_bigquery_schema_from_dataframe(df)
            
            # 1. Vytvoření dočasné tabulky a nahrání dat
            job_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                schema=schema,
                ignore_unknown_values=True,
            )
            
            self.logger.info(f"Vytvářím dočasnou tabulku {temp_table_id}...")
            
            # Nahrávání do temp tabulky po dávkách
            uploaded = 0
            for i in range(0, total_rows, batch_size):
                batch = df.iloc[i:i + batch_size]
                
                if i > 0:
                    job_config.write_disposition = bigquery.WriteDisposition.WRITE_APPEND
                
                job = self.bq_client.load_table_from_dataframe(
                    batch,
                    temp_table_id,
                    job_config=job_config
                )
                job.result()
                
                uploaded += len(batch)
                self.logger.info(f"Nahráno do temp: {uploaded}/{total_rows} ({uploaded/total_rows*100:.1f}%)")
            
            # 2. MERGE operace
            self.logger.info(f"Provádím MERGE operaci...")
            
            # Získáme schema z temp tabulky pro CREATE
            temp_table = self.bq_client.get_table(temp_table_id)
            columns = [field.name for field in temp_table.schema if field.name != 'ID']
            
            # Vytvoříme SET klauzuli pro UPDATE (všechny sloupce kromě ID)
            set_clause = ", ".join([f"T.{col} = S.{col}" for col in columns])
            
            merge_query = f"""
                MERGE `{table_id}` T
                USING `{temp_table_id}` S
                ON T.ID = S.ID
                WHEN MATCHED THEN 
                    UPDATE SET {set_clause}
                WHEN NOT MATCHED THEN 
                    INSERT ({', '.join(['ID'] + columns)})
                    VALUES ({', '.join(['S.ID'] + [f'S.{col}' for col in columns])})
            """
            
            merge_job = self.bq_client.query(merge_query)
            merge_result = merge_job.result()
            
            # Získáme statistiky MERGE operace
            if hasattr(merge_job, 'dml_stats') and merge_job.dml_stats:
                stats = merge_job.dml_stats
                self.logger.info(
                    f"MERGE dokončen - "
                    f"Vloženo: {stats.inserted_row_count}, "
                    f"Aktualizováno: {stats.updated_row_count}, "
                    f"Smazáno: {stats.deleted_row_count}"
                )
            else:
                self.logger.info("MERGE operace dokončena")
            
            # 3. Smazání dočasné tabulky
            self.bq_client.delete_table(temp_table_id)
            self.logger.debug(f"Dočasná tabulka smazána: {temp_table_id}")
            
            self.logger.info(f"✓ Incremental sync tabulky {table_name} dokončen")
            
        except Exception as e:
            # Pokus o smazání dočasné tabulky při chybě
            try:
                self.bq_client.delete_table(temp_table_id)
            except:
                pass
                
            self.logger.error(f"Chyba při MERGE operaci: {e}")
            capture_exception(e)
            raise

    def sync_table(self, sql_file: str):
        """
        Synchronizuje jednu tabulku z SQL souboru s podporou full/incremental mode.
        IGNORUJE metadata tabulku - řídí se pouze days_back z konfigurace.
        
        Args:
            sql_file: Název SQL souboru
        """
        try:
            table_name = Path(sql_file).stem  # Název bez přípony
            
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Synchronizace tabulky: {table_name} (mode: {self.sync_mode})")
            self.logger.info(f"{'='*60}")
            
            # 1. Zjistíme pouze zda tabulka existuje (pro incremental mode)
            sync_info = self.get_last_sync_info(table_name)
            
            if self.sync_mode == 'full':
                self.logger.info(f"Full load - tabulka bude vyčištěna a nahrána data podle days_back")
            elif self.sync_mode == 'incremental':
                if sync_info and sync_info.get('exists'):
                    self.logger.info(f"Incremental load - UPSERT podle ID, data podle days_back")
                else:
                    self.logger.info(f"Incremental load - tabulka neexistuje, vytvoří se nová")
            
            # 2. Načtení a úprava SQL (sync_info se používá jen pro kontrolu existence)
            sql_query = self.load_and_prepare_sql(sql_file, sync_info)
            
            # 3. Stažení dat
            batch_size = self.config['sync']['batch_size']
            df = self.fetch_data_in_batches(sql_query, batch_size)
            
            # 4. Nahrání podle sync mode
            if self.sync_mode == 'incremental' and sync_info and sync_info.get('exists'):
                # Incremental sync - MERGE (UPSERT podle ID)
                self.upload_with_merge(df, table_name, batch_size)
            else:
                # Full sync - TRUNCATE a INSERT
                # Nebo incremental když tabulka neexistuje
                self.upload_to_bigquery(df, table_name, batch_size)
            
            # 5. Aktualizace metadata (volitelné, pro tracking)
            if len(df) > 0:
                # Bezpečné získání max datum
                try:
                    if 'Datum' in df.columns:
                        # Odfiltruj NaN hodnoty a převeď na datum
                        date_series = pd.to_datetime(df['Datum'], errors='coerce').dropna()
                        if len(date_series) > 0:
                            max_date = date_series.max().date()
                        else:
                            max_date = datetime.now().date()
                    else:
                        max_date = datetime.now().date()
                except Exception as e:
                    self.logger.warning(f"Chyba při zjišťování max_date: {e}, použiji current date")
                    max_date = datetime.now().date()
                    
                self.update_sync_metadata(table_name, len(df), max_date)
            
        except Exception as e:
            self.logger.error(f"Chyba při synchronizaci tabulky {sql_file}: {e}")
            capture_exception(e)
            raise

    def run(self):
        """Hlavní metoda pro spuštění synchronizace."""
        start_time = datetime.now()
        
        try:
            self.logger.info("="*70)
            self.logger.info(f"START synchronizace Pohoda → BigQuery (mode: {self.sync_mode})")
            self.logger.info("="*70)
            
            # 1. Připojení k databázím
            self.connect_mssql()
            self.connect_bigquery()
            
            # 2. Inicializace metadata tabulky (vždy)
            self._ensure_sync_metadata_table()
            
            # 3. Získání connection info
            self.get_pohoda_connection_info()
            
            # 4. Synchronizace všech tabulek
            sql_files = self.config['sync']['sql_files']
            
            for sql_file in sql_files:
                self.sync_table(sql_file)
            
            # Úspěch
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.info("\n" + "="*70)
            self.logger.info(f"✓ Synchronizace dokončena úspěšně za {duration:.1f} sekund")
            self.logger.info("="*70)
            
            return True
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.error("\n" + "="*70)
            self.logger.error(f"✗ Synchronizace selhala po {duration:.1f} sekundách")
            self.logger.error(f"Chyba: {e}")
            self.logger.error("="*70)
            
            capture_exception(e)
            return False
            
        finally:
            # Uzavření připojení
            if self.mssql_conn:
                try:
                    self.mssql_conn.close()
                    self.logger.info("MS SQL připojení uzavřeno")
                except Exception as e:
                    self.logger.warning(f"Chyba při uzavírání MS SQL: {e}")
            
            if self.bq_client:
                try:
                    self.bq_client.close()
                    self.logger.info("BigQuery připojení uzavřeno")
                except Exception as e:
                    self.logger.warning(f"Chyba při uzavírání BigQuery: {e}")


def main():
    """Hlavní funkce."""
    try:
        # Změna do složky se skriptem
        script_dir = Path(__file__).parent
        os.chdir(script_dir)
        
        # Spuštění synchronizace
        syncer = PohodaBigQuerySync()
        success = syncer.run()
        
        # Exit code pro cron
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\nSynchronizace přerušena uživatelem")
        sys.exit(130)
    except Exception as e:
        print(f"\nKritická chyba: {e}")
        capture_exception(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
