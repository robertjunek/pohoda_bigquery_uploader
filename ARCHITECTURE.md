# Architektura synchronizace Pohoda → BigQuery

```
┌─────────────────────────────────────────────────────────────────┐
│                         CRON JOB                                │
│  (každý den ve 4:00 nebo dle nastavení)                         │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│              sync_pohoda_to_bigquery.py                         │
│  (Python skript s error handling + logging)                     │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                  ┌───────────────┼───────────────┐
                  │               │               │
                  ▼               ▼               ▼
         ┌────────────┐  ┌────────────┐  ┌────────────┐
         │ config.json│  │veverka.json│  │  SQL files │
         │            │  │            │  │  (4 ks)    │
         │ MS SQL     │  │ BigQuery   │  │            │
         │ credentials│  │ credentials│  │ FA.sql     │
         │ Sentry DSN │  │            │  │ PH.sql     │
         └────────────┘  └────────────┘  │ SKPP.sql   │
                                         │ SKPV.sql   │
                                         └────────────┘
                                  │
                  ┌───────────────┴───────────────┐
                  │                               │
                  ▼                               ▼
         ┌─────────────────┐           ┌─────────────────┐
         │   MS SQL Server │           │  Google BigQuery│
         │                 │           │                 │
         │ 1. Dotaz na     │           │ Dataset: pohoda │
         │    companies    │           │                 │
         │    tabulku      │           │ Tabulky:        │
         │                 │           │  - FA           │
         │ 2. Získání      │           │  - PH           │
         │    linked_server│           │  - SKPP         │
         │    & database   │           │  - SKPV         │
         │                 │           │                 │
         │ 3. Přidání      │           │ Mode:           │
         │    prefixů      │           │ WRITE_TRUNCATE  │
         │    k tabulkám   │           │ (přepis dat)    │
         │                 │           │                 │
         │ 4. Stažení dat  │─────────▶ │ 5. Upload dat   │
         │    (batch 5000) │           │    (batch 5000) │
         └─────────────────┘           └─────────────────┘
                  │                               │
                  │                               │
                  ▼                               ▼
         ┌─────────────────┐           ┌─────────────────┐
         │    sync.log     │           │   Sentry.io     │
         │  (rotační log)  │           │ (error tracking)│
         │                 │           │                 │
         │ - INFO          │           │ - Exceptions    │
         │ - WARNING       │           │ - Messages      │
         │ - ERROR         │           │ - Context       │
         │ - DEBUG         │           │                 │
         └─────────────────┘           └─────────────────┘
```

## Tok dat

1. **Inicializace:**
   - Načte config.json (MS SQL credentials, batch size, atd.)
   - Připojí se k MS SQL serveru
   - Připojí se k BigQuery (pomocí veverka.json)
   - Inicializuje Sentry error tracking

2. **Získání connection info:**
   ```sql
   SELECT TOP 1 linked_server, [database] FROM companies
   ```
   → Zjistí: `linked_server='SERVER1'`, `database='POHODA_DB'`

3. **Příprava SQL dotazů:**
   - Načte FA.sql, PH.sql, SKPP.sql, SKPV.sql
   - Přidá prefixy k tabulkám:
     ```
     FROM FA → FROM [SERVER1].[POHODA_DB].dbo.FA
     JOIN AD → JOIN [SERVER1].[POHODA_DB].dbo.AD
     ```

4. **Stahování dat:**
   - Provede upravený SQL dotaz
   - Načte všechna data do pandas DataFrame
   - Loguje počet záznamů

5. **Upload do BigQuery:**
   - První batch: WRITE_TRUNCATE (smaže starou tabulku a vytvoří novou)
   - Další batche: WRITE_APPEND (přidává data)
   - Batch size: 5000 záznamů
   - Progress logging po každém batchi

6. **Error handling:**
   - Všechny výjimky jsou zachyceny
   - Logují se do sync.log
   - Odesílají se do Sentry.io
   - Exit code: 0 = úspěch, 1 = chyba

7. **Cleanup:**
   - Uzavření MS SQL připojení
   - Uzavření BigQuery klienta
   - Finální log message

## Bezpečnost

- ✅ Credentials v config.json (gitignore)
- ✅ Service account pro BigQuery (veverka.json)
- ✅ Connection timeout (30s)
- ✅ Error tracking přes Sentry
- ✅ Rotační logy (max 10 MB × 5 souborů)

## Monitoring

```bash
# Živé sledování logů
tail -f sync.log

# Kontrola cron jobů
grep CRON /var/log/syslog | tail

# Sentry dashboard
https://sentry.io
```
