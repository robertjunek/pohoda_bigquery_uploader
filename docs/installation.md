---
layout: default
title: Instalace
nav_order: 2
---

# 📦 Instalace a nastavení

Detailní průvodce instalací a konfigurací projektu.

---

## Požadavky

### Systémové požadavky

- **OS:** Linux, macOS, Windows
- **Python:** 3.12 nebo novější
- **MS SQL Server:** Přístup k Pohoda databázi
- **Google Cloud:** BigQuery projekt a credentials

### ODBC Driver

Pro připojení k MS SQL serveru potřebuješ ODBC driver.

#### Ubuntu/Debian

```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | \
  sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

#### macOS

```bash
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
brew update
brew install msodbcsql18 mssql-tools18
```

#### Windows

Stáhni a nainstaluj z [Microsoft Download Center](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)

---

## Krok 1: Klonování repozitáře

```bash
git clone https://github.com/robertjunek/pohoda_bigquery_uploader.git
cd pohoda_bigquery_uploader
```

---

## Krok 2: Virtual Environment

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

---

## Krok 3: Instalace závislostí

```bash
pip install -r requirements.txt
```

Nebo použij Makefile:

```bash
make install
```

### Co se nainstaluje

- `pyodbc` - MS SQL připojení
- `google-cloud-bigquery` - BigQuery API
- `pandas` - Data manipulace
- `pyarrow` - Efektivní data transfer
- `sentry-sdk` - Error tracking
- `python-dotenv` - Environment variables

---

## Krok 4: Google Cloud Credentials

### Vytvoření Service Account

1. Otevři [Google Cloud Console](https://console.cloud.google.com/)
2. Vyber nebo vytvoř projekt
3. Jdi na **IAM & Admin** → **Service Accounts**
4. Klikni na **Create Service Account**
5. Zadej název (např. "pohoda-sync")
6. Přiřaď role:
   - BigQuery Data Editor
   - BigQuery Job User
7. Vytvoř JSON klíč
8. Ulož jako `pohoda_bigquery_uploader.json` (nebo jiný název)

### Umístění credentials

```bash
# Zkopíruj credentials do projektu
cp /path/to/downloaded/key.json pohoda_bigquery_uploader.json
```

⚠️ **DŮLEŽITÉ:** Nikdy necommituj `pohoda_bigquery_uploader.json` do gitu!

---

## Krok 5: Konfigurace

### Interaktivní způsob

```bash
python setup_config.py
```

Průvodce se tě zeptá na:
- MS SQL server adresu
- Databázi
- Username a password
- Sentry DSN (volitelné)

### Manuální způsob

Uprav `config.json`:

```json
{
  "mssql": {
    "server": "192.168.1.50",
    "database": "pohoda_bigquery_uploader",
    "username": "sa",
    "password": "tvoje_heslo",
    "driver": "ODBC Driver 18 for SQL Server",
    "timeout": 30,
    "trust_server_certificate": true
  },
  "bigquery": {
    "project_id": "tvuj-projekt-id",
    "dataset": "pohoda",
    "credentials_file": "pohoda_bigquery_uploader.json",
    "location": "EU"
  },
  "sync": {
    "batch_size": 5000,
    "sql_files": [
      "FA.sql",
      "PH.sql",
      "SKPP.sql",
      "SKPV.sql"
    ]
  },
  "logging": {
    "log_file": "sync.log",
    "log_level": "INFO",
    "max_bytes": 10485760,
    "backup_count": 5
  },
  "sentry": {
    "dsn": "https://xxx@xxx.ingest.sentry.io/xxx",
    "environment": "production",
    "traces_sample_rate": 0.1
  }
}
```

---

## Krok 6: Test připojení

```bash
python test_connections.py
```

Nebo:

```bash
make test-conn
```

**Výstup by měl vypadat:**

```
======================================================================
Test připojení k databázím
======================================================================

1️⃣  Test MS SQL připojení...
----------------------------------------------------------------------
✅ MS SQL připojení OK
   Server: 192.168.1.50
   Database: pohoda_bigquery_uploader
   Linked server: TEST1
   Pohoda database: StwPhHPA_02891042_202502

2️⃣  Test BigQuery připojení...
----------------------------------------------------------------------
✅ BigQuery připojení OK
   Projekt: havlikova-apoteka
   Dataset: pohoda
   Location: EU
   Dataset existuje: ✅

3️⃣  Test SQL souborů...
----------------------------------------------------------------------
✅ FA.sql
✅ PH.sql
✅ SKPP.sql
✅ SKPV.sql

======================================================================
✅ Všechny testy prošly úspěšně!
======================================================================
```

---

## Krok 7: První synchronizace

```bash
./test_sync.sh
```

Nebo:

```bash
python sync_pohoda_to_bigquery.py
```

Nebo použij Makefile:

```bash
make test-sync
```

---

## Krok 8: Automatické spouštění

### Cron (Linux/macOS)

```bash
# Otevři crontab editor
crontab -e

# Přidej řádek (každý den ve 2:00)
0 2 * * * cd /home/robert/projekty/pohoda_bigquery_uploader && .venv/bin/python sync_pohoda_to_bigquery.py >> cron.log 2>&1
```

### Task Scheduler (Windows)

1. Otevři Task Scheduler
2. Create Basic Task
3. Trigger: Daily v 2:00
4. Action: Start a program
   - Program: `C:\path\to\.venv\Scripts\python.exe`
   - Arguments: `sync_pohoda_to_bigquery.py`
   - Start in: `C:\path\to\pohoda_bigquery_uploader`

---

## Troubleshooting instalace

### Python verze

```bash
python --version
# Mělo by být 3.12 nebo vyšší
```

Pokud máš starší verzi, nainstaluj novější Python.

### pip nefunguje

```bash
python -m pip install --upgrade pip
```

### ODBC Driver chyba

Zkontroluj nainstalované drivery:

```bash
# Linux/macOS
odbcinst -q -d

# Windows
# Otevři ODBC Data Source Administrator
```

### Permissions chyba

```bash
# Ujisti se, že máš práva ke spuštění
chmod +x test_sync.sh
```

### BigQuery credentials chyba

Zkontroluj:
1. Cesta k JSON s BigQuery credentials je správná
2. Service account má správné role
3. Projekt ID v config.json je správný

---

## Ověření instalace

Po dokončení by měly fungovat tyto příkazy:

```bash
make test-conn    # ✅ Všechny testy prošly
make test-sync    # ✅ Synchronizace dokončena
make status       # 📊 Zobrazí stav
```

---

## Další kroky

- [Použití](usage.md) - Jak používat skript
- [Konfigurace](configuration.md) - Detailní konfigurace
- [Troubleshooting](troubleshooting.md) - Řešení problémů

---

[← Zpět na hlavní stránku](index.md)
