#!/usr/bin/env python3
"""
Diagnostický skript pro kontrolu ODBC instalace a připojení.
"""

import sys
import subprocess
import os
from pathlib import Path


def run_command(cmd, description):
    """Spustí command a vrátí výstup."""
    print(f"🔍 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description}")
            if result.stdout.strip():
                print(f"   {result.stdout.strip()}")
        else:
            print(f"❌ {description}")
            if result.stderr.strip():
                print(f"   Error: {result.stderr.strip()}")
        return result.returncode == 0
    except Exception as e:
        print(f"❌ {description}: {e}")
        return False


def check_file_exists(filepath, description):
    """Kontrola existence souboru."""
    print(f"🔍 {description}...")
    exists = Path(filepath).exists()
    if exists:
        print(f"✅ {description}")
        print(f"   Cesta: {filepath}")
    else:
        print(f"❌ {description}")
        print(f"   Očekávaná cesta: {filepath}")
    return exists


def main():
    print("=" * 70)
    print("🩺 ODBC Diagnostika")
    print("=" * 70)
    print()
    
    # 1. Systémová diagnostika
    print("1️⃣  Systémová diagnostika")
    print("-" * 40)
    
    run_command("uname -a", "Informace o systému")
    run_command("lsb_release -a 2>/dev/null || cat /etc/os-release", "Distribuce")
    print()
    
    # 2. ODBC Driver diagnostika
    print("2️⃣  ODBC Driver diagnostika")
    print("-" * 40)
    
    run_command("which odbcinst", "odbcinst nástroj")
    run_command("odbcinst -q -d", "Dostupné ODBC drivery")
    
    # Kontrola konkrétního driveru
    has_driver = run_command(
        "odbcinst -q -d | grep -i 'ODBC Driver.*SQL Server'", 
        "MS SQL Server ODBC Driver"
    )
    print()
    
    # 3. Knihovny diagnostika
    print("3️⃣  Knihovny diagnostika")
    print("-" * 40)
    
    run_command("ldconfig -p | grep odbc", "ODBC knihovny")
    
    # Specifické knihovny
    libs_to_check = [
        "libodbc.so.2",
        "libodbc.so.1", 
        "libodbc.so",
        "libodbcinst.so.2"
    ]
    
    for lib in libs_to_check:
        run_command(f"ldconfig -p | grep {lib}", f"Knihovna {lib}")
    
    print()
    
    # 4. Python pyodbc diagnostika
    print("4️⃣  Python pyodbc diagnostika")
    print("-" * 40)
    
    # Kontrola virtual env
    venv_python = Path(".venv/bin/python")
    if check_file_exists(venv_python, "Virtual environment Python"):
        
        # Test importu pyodbc
        print("🔍 Test importu pyodbc...")
        try:
            result = subprocess.run([
                str(venv_python), "-c", "import pyodbc; print(f'pyodbc verze: {pyodbc.version}')"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ pyodbc import úspěšný")
                print(f"   {result.stdout.strip()}")
            else:
                print("❌ pyodbc import selhal")
                print(f"   Error: {result.stderr.strip()}")
        except Exception as e:
            print(f"❌ pyodbc test selhal: {e}")
        
        # Test dostupných driverů přes pyodbc
        print("🔍 Test ODBC driverů přes pyodbc...")
        try:
            result = subprocess.run([
                str(venv_python), "-c", 
                "import pyodbc; drivers = pyodbc.drivers(); print('Dostupné drivery:'); [print(f'  - {d}') for d in drivers]"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ pyodbc drivery získány")
                print(f"   {result.stdout.strip()}")
            else:
                print("❌ pyodbc drivery nelze získat")
                print(f"   Error: {result.stderr.strip()}")
        except Exception as e:
            print(f"❌ pyodbc drivery test selhal: {e}")
    
    print()
    
    # 5. Konfigurační soubory diagnostika
    print("5️⃣  Konfigurační soubory diagnostika")
    print("-" * 40)
    
    config_files = [
        ("config.json", "Hlavní konfigurace"),
        ("requirements.txt", "Python závislosti"),
        ("sync_pohoda_to_bigquery.py", "Hlavní skript"),
        ("test_connections.py", "Test připojení skript")
    ]
    
    for filepath, description in config_files:
        check_file_exists(filepath, description)
    
    print()
    
    # 6. Doporučení
    print("6️⃣  Doporučení")
    print("-" * 40)
    
    print("💡 Pro vyřešení problému s libodbc.so.2:")
    print("   1. Spusťte: make install-odbc")
    print("   2. Nebo ručně: sudo ./install_odbc.sh")
    print("   3. Restartujte terminál")
    print("   4. Případně restartujte systém")
    print()
    
    print("💡 Pro test připojení:")
    print("   1. make test-conn")
    print("   2. make test-sync")
    print()
    
    print("=" * 70)
    print("🏁 Diagnostika dokončena")
    print("=" * 70)


if __name__ == "__main__":
    main()