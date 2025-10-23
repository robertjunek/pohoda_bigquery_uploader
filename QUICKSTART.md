# 🚀 Rychlý start

## 1. Konfigurace MS SQL připojení

```bash
source .venv/bin/activate
python setup_config.py
```

Zadej:
- Adresu MS SQL serveru
- Databázi (obvykle "master")
- Username a password
- Sentry DSN (volitelné)

## 2. Test synchronizace

```bash
./test_sync.sh
```

Nebo přímo:
```bash
source .venv/bin/activate
python sync_pohoda_to_bigquery.py
```

## 3. Nastavení automatického spouštění (cron)

Otevři crontab:
```bash
crontab -e
```

Přidej (např. každý den ve 2:00):
```cron
0 2 * * * cd /home/robert/projekty/apoteka_veverka && .venv/bin/python sync_pohoda_to_bigquery.py >> cron.log 2>&1
```

## Co dělá skript?

1. ✅ Připojí se k MS SQL serveru
2. ✅ Zjistí linked_server a database z tabulky `companies`
3. ✅ Načte SQL soubory (FA.sql, PH.sql, SKPP.sql, SKPV.sql)
4. ✅ Přidá správné prefixy k tabulkám (`[linked_server].[database].dbo.`)
5. ✅ Stáhne data po dávkách (5000 záznamů)
6. ✅ Nahraje je do BigQuery (dataset: `pohoda`)
7. ✅ Loguje vše do `sync.log`
8. ✅ Odesílá chyby do Sentry.io

## Kontrola logů

```bash
# Živé sledování logů
tail -f sync.log

# Posledních 50 řádků
tail -n 50 sync.log

# Cron logy
tail -f cron.log
```

## Struktura BigQuery

```
havlikova-apoteka (projekt)
└── pohoda (dataset)
    ├── FA (faktury)
    ├── PH (prodejky)
    ├── SKPP (příjemky)
    └── SKPV (výdejky)
```

## Troubleshooting

### "companies" tabulka nenalezena
Ujisti se, že databáze v config.json obsahuje tabulku `companies` s poli:
- `linked_server` (varchar)
- `database` (varchar)

### ODBC Driver nenalezen
Nainstaluj ODBC driver:
```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17
```

### BigQuery oprávnění
Service account v `veverka.json` potřebuje role:
- BigQuery Data Editor
- BigQuery Job User

## Užitečné příkazy

```bash
# Kontrola, zda běží cron job
grep CRON /var/log/syslog | tail

# Test BigQuery připojení
source .venv/bin/activate
python -c "from google.cloud import bigquery; client = bigquery.Client(project='havlikova-apoteka'); print('✅ BigQuery OK')"

# Zobrazení tabulek v datasetu
bq ls pohoda
```
