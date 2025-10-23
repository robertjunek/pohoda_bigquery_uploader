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

    def _add_table_prefix(self, sql_content: str) -> str:
        """
        Přidá prefix ke všem tabulkám v SQL dotazu.
        
        Args:
            sql_content: Obsah SQL souboru
            
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
        
        return modified_sql

    def load_and_prepare_sql(self, sql_file: str) -> str:
        """
        Načte SQL soubor a přidá prefixy k tabulkám.
        
        Args:
            sql_file: Název SQL souboru
            
        Returns:
            Upravený SQL dotaz
        """
        try:
            sql_path = Path(sql_file)
            
            if not sql_path.exists():
                raise FileNotFoundError(f"SQL soubor {sql_file} nenalezen")
            
            with open(sql_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # Přidání prefixů
            modified_sql = self._add_table_prefix(sql_content)
            
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
            
            # Použití pandas pro efektivní načtení
            df = pd.read_sql(sql_query, self.mssql_conn)
            
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
        df = df.copy()
        
        # Ošetření duplicitních názvů sloupců
        cols = pd.Series(df.columns)
        for dup in cols[cols.duplicated()].unique():
            # Pro každý duplicitní sloupec přidáme číslo
            indices = cols[cols == dup].index.tolist()
            for i, idx in enumerate(indices):
                if i > 0:  # První necháme bez čísla
                    cols[idx] = f"{dup}_{i}"
        df.columns = cols
        
        # Ošetření None hodnot v object sloupcích
        for col in df.columns:
            try:
                if df[col].dtype == 'object':
                    # Object sloupce - nahraď None prázdným stringem nebo None
                    df[col] = df[col].where(pd.notna(df[col]), None)
            except Exception as e:
                self.logger.warning(f"Problém s převodem sloupce {col}: {e}")
                continue
        
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
            
            self.logger.info(f"Nahrávám {total_rows} záznamů do {table_id}...")
            
            # Konfigurace pro load job
            job_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                autodetect=True,
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
            capture_exception(e)
            raise

    def sync_table(self, sql_file: str):
        """
        Synchronizuje jednu tabulku z SQL souboru.
        
        Args:
            sql_file: Název SQL souboru
        """
        try:
            table_name = Path(sql_file).stem  # Název bez přípony
            
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Synchronizace tabulky: {table_name}")
            self.logger.info(f"{'='*60}")
            
            # 1. Načtení a úprava SQL
            sql_query = self.load_and_prepare_sql(sql_file)
            
            # 2. Stažení dat
            batch_size = self.config['sync']['batch_size']
            df = self.fetch_data_in_batches(sql_query, batch_size)
            
            # 3. Nahrání do BigQuery
            self.upload_to_bigquery(df, table_name, batch_size)
            
        except Exception as e:
            self.logger.error(f"Chyba při synchronizaci tabulky {sql_file}: {e}")
            capture_exception(e)
            raise

    def run(self):
        """Hlavní metoda pro spuštění synchronizace."""
        start_time = datetime.now()
        
        try:
            self.logger.info("="*70)
            self.logger.info("START synchronizace Pohoda → BigQuery")
            self.logger.info("="*70)
            
            # 1. Připojení k databázím
            self.connect_mssql()
            self.connect_bigquery()
            
            # 2. Získání connection info
            self.get_pohoda_connection_info()
            
            # 3. Synchronizace všech tabulek
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
