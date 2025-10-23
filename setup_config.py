#!/usr/bin/env python3
"""
Pomocný skript pro konfiguraci připojení k MS SQL serveru.
"""

import json
import getpass
import sys


def configure_mssql():
    """Interaktivní konfigurace MS SQL připojení."""
    print("="*60)
    print("Konfigurace MS SQL Server připojení")
    print("="*60)
    print()
    
    # Načtení existující konfigurace
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ Soubor config.json nenalezen!")
        sys.exit(1)
    
    # Interaktivní zadání
    print("Zadej přihlašovací údaje k MS SQL serveru:")
    print("(prázdný vstup ponechá aktuální hodnotu)\n")
    
    current = config['mssql']
    
    server = input(f"Server [{current['server']}]: ").strip()
    if server:
        current['server'] = server
    
    database = input(f"Database [{current['database']}]: ").strip()
    if database:
        current['database'] = database
    
    username = input(f"Username [{current['username']}]: ").strip()
    if username:
        current['username'] = username
    
    password = getpass.getpass("Password (nebude zobrazeno): ").strip()
    if password:
        current['password'] = password
    
    driver = input(f"ODBC Driver [{current['driver']}]: ").strip()
    if driver:
        current['driver'] = driver
    
    print()
    print("Sentry DSN (volitelné):")
    sentry_dsn = input(f"Sentry DSN [{config['sentry']['dsn']}]: ").strip()
    if sentry_dsn:
        config['sentry']['dsn'] = sentry_dsn
    
    # Uložení
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print()
    print("="*60)
    print("✅ Konfigurace uložena do config.json")
    print("="*60)
    print()
    print("Můžeš nyní spustit synchronizaci pomocí:")
    print("  python sync_pohoda_to_bigquery.py")
    print("nebo:")
    print("  ./test_sync.sh")


if __name__ == "__main__":
    try:
        configure_mssql()
    except KeyboardInterrupt:
        print("\n\nKonfigurace zrušena")
        sys.exit(1)
