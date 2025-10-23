#!/usr/bin/env python3
"""
Test připojení k MS SQL a BigQuery bez spuštění synchronizace.
"""

import json
import os
import sys
import pyodbc
from google.cloud import bigquery


def test_connections():
    """Test připojení k databázím."""
    print("="*70)
    print("Test připojení k databázím")
    print("="*70)
    print()
    
    # Načtení konfigurace
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ Soubor config.json nenalezen!")
        return False
    
    success = True
    
    # Test MS SQL
    print("1️⃣  Test MS SQL připojení...")
    print("-" * 70)
    try:
        mssql_config = config['mssql']
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
        
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        
        # Test dotaz
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        
        print(f"✅ MS SQL připojení OK")
        print(f"   Server: {mssql_config['server']}")
        print(f"   Database: {mssql_config['database']}")
        print(f"   Version: {version.split('\\n')[0]}")
        
        # Test companies tabulky
        try:
            cursor.execute("SELECT TOP 1 linked_server, [database] FROM companies")
            row = cursor.fetchone()
            if row:
                print(f"   Linked server: {row.linked_server}")
                print(f"   Pohoda database: {row.database}")
            else:
                print("   ⚠️  Tabulka companies je prázdná")
                success = False
        except pyodbc.Error as e:
            print(f"   ⚠️  Tabulka companies nenalezena: {e}")
            success = False
        
        cursor.close()
        conn.close()
        
    except pyodbc.Error as e:
        print(f"❌ MS SQL připojení selhalo: {e}")
        success = False
    
    print()
    
    # Test BigQuery
    print("2️⃣  Test BigQuery připojení...")
    print("-" * 70)
    try:
        bq_config = config['bigquery']
        credentials_path = bq_config['credentials_file']
        
        if not os.path.exists(credentials_path):
            print(f"❌ Credentials soubor {credentials_path} nenalezen!")
            success = False
        else:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            
            client = bigquery.Client(
                project=bq_config['project_id'],
                location=bq_config['location']
            )
            
            # Test dotaz
            query = "SELECT 1 as test"
            result = client.query(query).result()
            
            print(f"✅ BigQuery připojení OK")
            print(f"   Projekt: {bq_config['project_id']}")
            print(f"   Dataset: {bq_config['dataset']}")
            print(f"   Location: {bq_config['location']}")
            
            # Kontrola datasetu
            try:
                dataset_ref = f"{bq_config['project_id']}.{bq_config['dataset']}"
                dataset = client.get_dataset(dataset_ref)
                print(f"   Dataset existuje: ✅")
            except Exception:
                print(f"   Dataset existuje: ⚠️  Ne (bude vytvořen při synchronizaci)")
            
            client.close()
            
    except Exception as e:
        print(f"❌ BigQuery připojení selhalo: {e}")
        success = False
    
    print()
    
    # Test SQL souborů
    print("3️⃣  Test SQL souborů...")
    print("-" * 70)
    sql_files = config['sync']['sql_files']
    for sql_file in sql_files:
        if os.path.exists(sql_file):
            print(f"✅ {sql_file}")
        else:
            print(f"❌ {sql_file} - nenalezen")
            success = False
    
    print()
    print("="*70)
    if success:
        print("✅ Všechny testy prošly úspěšně!")
        print()
        print("Můžeš spustit synchronizaci:")
        print("  python sync_pohoda_to_bigquery.py")
        print("nebo:")
        print("  ./test_sync.sh")
    else:
        print("❌ Některé testy selhaly - oprav je před spuštěním synchronizace")
    print("="*70)
    
    return success


if __name__ == "__main__":
    try:
        success = test_connections()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest přerušen")
        sys.exit(130)
