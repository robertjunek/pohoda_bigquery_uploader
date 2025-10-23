---
layout: default
title: Domů
nav_order: 1
---

# 🚀 Pohoda → BigQuery Synchronizace

Automatická synchronizace dat z MS SQL (Pohoda) do Google BigQuery s kompletním error handlingem, logováním a monitoringem.

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![BigQuery](https://img.shields.io/badge/BigQuery-ready-orange.svg)](https://cloud.google.com/bigquery)

---

## ✨ Hlavní funkce

- ✅ **Automatické stahování** dat z MS SQL serveru (Pohoda)
- ✅ **Batch processing** - zpracování po 5000 záznamech
- ✅ **BigQuery upload** - nahrávání do Google BigQuery
- ✅ **Error tracking** - integrace se Sentry.io
- ✅ **Rotační logování** - automatická rotace log souborů
- ✅ **Cron ready** - připraveno pro automatické spouštění
- ✅ **Kompletní dokumentace** - včetně troubleshootingu

---

## 📋 Rychlý start

### 1. Instalace

```bash
# Klonování repozitáře
git clone https://github.com/robertjunek/pohoda_bigquery_uploader.git
cd pohoda_bigquery_uploader

# Vytvoření virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# nebo: .venv\Scripts\activate  # Windows

# Instalace závislostí
pip install -r requirements.txt
```

### 2. Konfigurace

```bash
# Interaktivní konfigurace
python setup_config.py

# Nebo použij Makefile
make config
```

### 3. Test připojení

```bash
# Test MS SQL a BigQuery připojení
python test_connections.py

# Nebo
make test-conn
```

### 4. Spuštění synchronizace

```bash
# Testovací spuštění
./test_sync.sh

# Nebo přímo
python sync_pohoda_to_bigquery.py

# Nebo použij Makefile
make sync
```

---

## 🏗️ Architektura

```
┌─────────────────┐
│   CRON JOB      │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  sync_pohoda_to_bigquery.py     │
│  • Error handling               │
│  • Batch processing (5000)      │
│  • Logging + Sentry             │
└────┬──────────────────┬─────────┘
     │                  │
     ▼                  ▼
┌──────────┐      ┌──────────────┐
│ MS SQL   │      │   BigQuery   │
│ (Pohoda) │──────▶│  Dataset:    │
│          │      │   pohoda     │
└──────────┘      └──────────────┘
```

---

## 📊 Podporované tabulky

| Tabulka | Popis | SQL soubor |
|---------|-------|------------|
| **FA** | Faktury | `FA.sql` |
| **PH** | Prodejky | `PH.sql` |
| **SKPP** | Příjemky | `SKPP.sql` |
| **SKPV** | Výdejky | `SKPV.sql` |

Všechny tabulky jsou synchronizovány do BigQuery datasetu `pohoda`.

---

## 🔧 Konfigurace

### config.json

```json
{
  "mssql": {
    "server": "your_server",
    "database": "your_database",
    "username": "your_username",
    "password": "your_password",
    "driver": "ODBC Driver 18 for SQL Server",
    "timeout": 30,
    "trust_server_certificate": true
  },
  "bigquery": {
    "project_id": "your-project-id",
    "dataset": "pohoda",
    "credentials_file": "credentials.json",
    "location": "EU"
  },
  "sync": {
    "batch_size": 5000,
    "sql_files": ["FA.sql", "PH.sql", "SKPP.sql", "SKPV.sql"]
  },
  "sentry": {
    "dsn": "your_sentry_dsn",
    "environment": "production"
  }
}
```

---

## 📅 Automatické spouštění (Cron)

```bash
# Otevři crontab
crontab -e

# Přidej řádek (každý den ve 2:00)
0 2 * * * cd /path/to/project && .venv/bin/python sync_pohoda_to_bigquery.py >> cron.log 2>&1
```

**Další příklady:**
- Každých 6 hodin: `0 */6 * * *`
- Každý pracovní den v 8:00: `0 8 * * 1-5`
- Každou hodinu (8-18h): `0 8-18 * * 1-5`

---

## 📈 Monitoring

### Kontrola stavu

```bash
# Zobrazení stavu poslední synchronizace
make status
# nebo: python check_status.py
```

### Sledování logů

```bash
# Živé sledování
make logs
# nebo: tail -f sync.log

# Posledních 50 řádků
make logs-tail
# nebo: tail -n 50 sync.log

# Jen chyby
make logs-errors
# nebo: grep ERROR sync.log
```

### Sentry.io

- Všechny chyby jsou automaticky odesílány do Sentry
- Dashboard: [https://sentry.io](https://sentry.io)
- Real-time alerting při chybách

---

## 🛠️ Makefile příkazy

| Příkaz | Popis |
|--------|-------|
| `make help` | Zobrazí nápovědu |
| `make config` | Konfigurace připojení |
| `make test-conn` | Test připojení k databázím |
| `make test-sync` | Testovací synchronizace |
| `make sync` | Spuštění synchronizace |
| `make status` | Stav poslední synchronizace |
| `make logs` | Živé sledování logů |
| `make logs-tail` | Posledních 50 řádků |
| `make logs-errors` | Jen chyby |
| `make clean` | Vyčištění logů a cache |

---

## 🐛 Troubleshooting

### ODBC Driver nenalezen

**Ubuntu/Debian:**
```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

### Tabulka "companies" nenalezena

Ujisti se, že databáze obsahuje tabulku `companies` s poli:
- `linked_server` (varchar)
- `database` (varchar)

### BigQuery oprávnění

Service account potřebuje tyto role:
- BigQuery Data Editor
- BigQuery Job User

---

## 📚 Dokumentace

- [README](README.md) - Kompletní dokumentace
- [QUICKSTART](QUICKSTART.md) - Rychlý průvodce
- [ARCHITECTURE](ARCHITECTURE.md) - Architektura systému
- [STRUCTURE](STRUCTURE.md) - Struktura projektu

---

## 📦 Požadavky

- Python 3.12+
- MS SQL Server (nebo linked server)
- Google Cloud BigQuery
- ODBC Driver 17/18 for SQL Server

### Python závislosti

```
pyodbc==5.0.1
google-cloud-bigquery==3.14.1
pandas==2.1.4
sentry-sdk==1.39.2
python-dotenv==1.0.0
pyarrow>=10.0.0
```

---

## 🤝 Přispívání

Příspěvky jsou vítány! Prosím:

1. Forkni repozitář
2. Vytvoř feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit změny (`git commit -m 'Add AmazingFeature'`)
4. Push do branch (`git push origin feature/AmazingFeature`)
5. Otevři Pull Request

---

## 📄 Licence

Tento projekt je licencován pod MIT licencí - viz [LICENSE](LICENSE) soubor.

---

## 👨‍💻 Autor

**Robert**

- GitHub: [@robertjunek](https://github.com/robertjunek)

---

## 🙏 Poděkování

- [Google Cloud BigQuery](https://cloud.google.com/bigquery)
- [Sentry.io](https://sentry.io)
- [PyODBC](https://github.com/mkleehammer/pyodbc)
- [Pandas](https://pandas.pydata.org/)

---

## 📞 Podpora

Máš problém? Otevři [issue](https://github.com/robertjunek/pohoda_bigquery_uploader/issues) na GitHubu.

---

<div align="center">
  <p>Vytvořeno s ❤️ pro automatizaci datových toků</p>
  <p>
    <a href="#-pohoda--bigquery-synchronizace">Nahoru ↑</a>
  </p>
</div>
