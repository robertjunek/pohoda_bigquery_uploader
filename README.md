# Pohoda → BigQuery Synchronizace

Skript pro automatickou synchronizaci dat z MS SQL (Pohoda) do Google BigQuery.

## � Rychlé řešení chyby libodbc.so.2

Pokud dostáváte chybu s `libodbc.so.2`, spusťte:
```bash
make install-odbc
```
Více detailů: [ODBC_FIX.md](ODBC_FIX.md)

## �🚀 Rychlý start

### 1. Instalace ODBC Driver (pouze jednou)
```bash
make install-odbc
```

### 2. Instalace Python závislostí
```bash
make install
```

### 3. Konfigurace
```bash
make config
```

### 4. Test připojení
```bash
make test-conn
```

### 5. Spuštění synchronizace
```bash
make test-sync
```

## Konfigurace

1. **Upravit `config.json`:**
   - Doplnit přihlašovací údaje k MS SQL serveru
   - Doplnit Sentry DSN (pokud chceš používat error tracking)

2. **Zkontrolovat `pohoda_bigquery_uploader.json`:**
   - Měl by obsahovat Google Cloud credentials (už je připraven)

## Použití

### Manuální spuštění
```bash
python sync_pohoda_to_bigquery.py
```

### Automatické spuštění přes cron

Otevři crontab:
```bash
crontab -e
```

Přidej řádek (např. každý den ve 2:00):
```cron
0 2 * * * cd /home/robert/projekty/pohoda_bigquery_uploader && .venv/bin/python sync_pohoda_to_bigquery.py >> cron.log 2>&1
```

Nebo každých 6 hodin:
```cron
0 */6 * * * cd /home/robert/projekty/pohoda_bigquery_uploader && .venv/bin/python sync_pohoda_to_bigquery.py >> cron.log 2>&1
```

## Struktura projektu

```
.
├── .pohoda_dokumentace
│   ├── dokumentace.zip            # Oficiální dokumentace Pohody
├── config.json                    # Konfigurace (MS SQL, BigQuery, Sentry)
├── pohoda_bigquery_uploader.json                   # Google Cloud credentials
├── sync_pohoda_to_bigquery.py     # Hlavní skript
├── requirements.txt               # Python závislosti
├── FA.sql                         # SQL dotaz pro faktury
├── PH.sql                         # SQL dotaz pro prodejky
├── SKPP.sql                       # SQL dotaz pro příjemky
├── SKPV.sql                       # SQL dotaz pro výdejky
├── sync.log                       # Log soubor (generovaný)
└── README.md                      # Tento soubor
```

## Logování

- Logy se ukládají do `sync.log`
- Rotace logů: max 10 MB, 5 backup souborů
- Chyby se odesílají do Sentry (pokud je nakonfigurováno)

## Troubleshooting

### ODBC Driver chyba
Pokud dostaneš chybu s ODBC driverem, nainstaluj ho:

**Ubuntu/Debian:**
```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17
```

**Pokud máš jinou verzi driveru**, uprav v `config.json`:
```json
"driver": "ODBC Driver 18 for SQL Server"
```

### Chyba připojení k MS SQL
- Zkontroluj, že server je dostupný
- Ověř username/password v `config.json`
- Zkontroluj firewall pravidla

### BigQuery chyba
- Ověř, že json pro BigQuery má správná oprávnění
- Service account musí mít role: BigQuery Data Editor, BigQuery Job User

## Monitorování

1. **Logy:** `tail -f sync.log`
2. **Cron logy:** `tail -f cron.log`
3. **Sentry:** https://sentry.io/organizations/your-org/issues/

## Funkce skriptu

1. ✅ Připojení k MS SQL a získání linked_server/database info
2. ✅ Načtení SQL dotazů a přidání prefixů k tabulkám
3. ✅ Stahování dat po dávkách (5000 záznamů)
4. ✅ Nahrávání do BigQuery s přepisem dat (TRUNCATE & LOAD)
5. ✅ Rotační logování do souboru
6. ✅ Error tracking přes Sentry
7. ✅ Ošetření všech chyb (připojení, SQL, upload)
8. ✅ Správný exit code pro cron
