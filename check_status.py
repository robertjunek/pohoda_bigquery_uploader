#!/usr/bin/env python3
"""
Kontrola stavu poslední synchronizace.
Parsuje log a zobrazuje přehled.
"""

import os
import re
from datetime import datetime
from pathlib import Path


def parse_log():
    """Parsování sync.log a zobrazení stavu."""
    log_file = Path("sync.log")
    
    if not log_file.exists():
        print("❌ Log soubor sync.log nenalezen")
        print("   Synchronizace ještě neběžela")
        return
    
    print("="*70)
    print("📊 Přehled poslední synchronizace")
    print("="*70)
    print()
    
    # Čtení logu
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    if not lines:
        print("Log soubor je prázdný")
        return
    
    # Hledání poslední synchronizace
    start_pattern = re.compile(r'START synchronizace Pohoda.*BigQuery')
    success_pattern = re.compile(r'✓ Synchronizace dokončena úspěšně za ([\d.]+) sekund')
    failure_pattern = re.compile(r'✗ Synchronizace selhala po ([\d.]+) sekundách')
    table_pattern = re.compile(r'Synchronizace tabulky: (\w+)')
    uploaded_pattern = re.compile(r'✓ Tabulka (\w+) úspěšně nahrána')
    error_pattern = re.compile(r'ERROR - (.+)')
    
    # Analýza logu
    last_sync_start = None
    last_sync_end = None
    duration = None
    success = None
    tables_processed = []
    errors = []
    
    for i, line in enumerate(lines):
        # Datum a čas z logu
        timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
        
        if start_pattern.search(line):
            if timestamp_match:
                last_sync_start = timestamp_match.group(1)
            tables_processed = []
            errors = []
            success = None
        
        if table_pattern.search(line):
            match = table_pattern.search(line)
            tables_processed.append(match.group(1))
        
        if uploaded_pattern.search(line):
            pass  # Již zahrnuto v tables_processed
        
        if success_pattern.search(line):
            match = success_pattern.search(line)
            duration = match.group(1)
            success = True
            if timestamp_match:
                last_sync_end = timestamp_match.group(1)
        
        if failure_pattern.search(line):
            match = failure_pattern.search(line)
            duration = match.group(1)
            success = False
            if timestamp_match:
                last_sync_end = timestamp_match.group(1)
        
        if error_pattern.search(line) and last_sync_start:
            match = error_pattern.search(line)
            errors.append(match.group(1))
    
    # Zobrazení výsledků
    if last_sync_start:
        print(f"🕐 Start:    {last_sync_start}")
        if last_sync_end:
            print(f"🕐 Konec:    {last_sync_end}")
        if duration:
            print(f"⏱️  Trvání:  {duration} s")
        print()
        
        if success is True:
            print("✅ Status:   ÚSPĚCH")
        elif success is False:
            print("❌ Status:   CHYBA")
        else:
            print("⏳ Status:   BĚŽÍ nebo NEUKONČENO")
        
        print()
        
        if tables_processed:
            print(f"📋 Zpracované tabulky ({len(tables_processed)}):")
            for table in tables_processed:
                print(f"   ✓ {table}")
            print()
        
        if errors:
            print(f"⚠️  Chyby ({len(errors)}):")
            for error in errors[-5:]:  # Posledních 5 chyb
                print(f"   • {error[:100]}")
            if len(errors) > 5:
                print(f"   ... a dalších {len(errors) - 5} chyb")
            print()
    else:
        print("Žádná synchronizace nenalezena v logu")
        print()
    
    # Velikost logu
    log_size = log_file.stat().st_size
    log_size_mb = log_size / 1024 / 1024
    print(f"📁 Velikost logu: {log_size_mb:.2f} MB")
    
    print()
    print("="*70)
    print()
    print("💡 Příkazy:")
    print("   tail -f sync.log          # živé sledování")
    print("   tail -n 50 sync.log       # posledních 50 řádků")
    print("   grep ERROR sync.log       # jen chyby")
    print("="*70)


if __name__ == "__main__":
    try:
        parse_log()
    except KeyboardInterrupt:
        print("\n\nPřerušeno")
    except Exception as e:
        print(f"Chyba při parsování logu: {e}")
