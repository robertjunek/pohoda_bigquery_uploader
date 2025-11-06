# 🔄 Incremental Update - Implementace dokončena!

## ✅ Nové funkce implementované

### 1. **Dual Sync Mode Support**
```json
{
  "sync": {
    "mode": "full",              // "full" nebo "incremental"
    "days_back": 7,             // pro incremental mode
    "full_sync_days_back": 4000 // pro full mode
  }
}
```

### 2. **Metadata Tracking**
- Automatické vytvoření tabulky `_sync_metadata`
- Tracking posledního sync timestamp a max date
- Sledování počtu synchronizovaných záznamů

### 3. **MERGE Operace**
- Skutečný incremental update pomocí BigQuery MERGE
- UPDATE existujících záznamů podle ID
- INSERT nových záznamů
- Statistiky MERGE operace

### 4. **Inteligentní SQL Modifikace**
- Pro **incremental mode**: filtruje jen nová/změněná data od posledního sync
- Pro **full mode**: používá celé časové okno z konfigurace
- Automatické přidání datum filtru pro incremental sync

## 🚀 Použití

### Full Sync Mode (původní chování)
```bash
# Nastaví mode: "full" v config.json
make sync-full

# Nebo přímo v config.json:
{
  "sync": {
    "mode": "full",
    "full_sync_days_back": 4000  // stáhne všechna data
  }
}
```

### Incremental Sync Mode (nové!)
```bash
# Nastaví mode: "incremental" v config.json  
make sync-inc

# Nebo přímo v config.json:
{
  "sync": {
    "mode": "incremental",
    "days_back": 7  // bezpečnostní okno
  }
}
```

### Testovací spuštění
```bash
make test-sync-full    # Test full mode
make test-sync-inc     # Test incremental mode
make test-sync         # Test current mode z config.json
```

## 🔍 Jak funguje Incremental Mode

### První spuštění (tabulka neexistuje)
1. Vytvoří novou tabulku (full sync)
2. Stáhne všechna data podle `days_back`
3. Uloží metadata do `_sync_metadata`

### Následná spuštění (incremental)
1. Zjistí datum posledního sync z metadata
2. Přidá filtr: `AND CAST(h.Datum AS DATE) >= CAST('2025-11-01' AS DATE)`
3. Stáhne jen nová/změněná data
4. Provede MERGE operaci:
   - UPDATE existujících záznamů (podle ID)
   - INSERT nových záznamů
5. Aktualizuje metadata

### MERGE SQL Příklad
```sql
MERGE `project.dataset.FA` T
USING `project.dataset.FA_temp_123456` S
ON T.ID = S.ID
WHEN MATCHED THEN 
    UPDATE SET T.Agenda = S.Agenda, T.CisloDokladu = S.CisloDokladu, ...
WHEN NOT MATCHED THEN 
    INSERT (ID, Agenda, CisloDokladu, ...)
    VALUES (S.ID, S.Agenda, S.CisloDokladu, ...)
```

## 📊 Výhody Incremental Mode

### Rychlost
- **Full mode**: stáhne 11 let dat (4000 dní)
- **Incremental**: stáhne jen posledních 7 dní + nová data

### Efektivita
- Menší objem dat přes síť
- Rychlejší BigQuery operace
- Možnost častějšího spouštění (každou hodinu)

### Náklady
- Méně BigQuery slot hodin
- Menší data transfer poplatky
- Optimalizované využití zdrojů

## 🛠️ Konfigurace

### Doporučené nastavení pro produkci
```json
{
  "sync": {
    "mode": "incremental",
    "batch_size": 20000,
    "days_back": 3,             // bezpečnostní okno
    "full_sync_days_back": 4000 // pro občasný full refresh
  }
}
```

### Pro vývoj/testování
```json
{
  "sync": {
    "mode": "incremental", 
    "days_back": 1,             // jen včerejší data
    "full_sync_days_back": 30   // méně dat pro testy
  }
}
```

## 📝 Metadata Tabulka

### Schema `_sync_metadata`
```sql
CREATE TABLE _sync_metadata (
  table_name STRING,           -- např. "FA", "PH"
  last_sync_timestamp TIMESTAMP,
  last_max_date DATE,         -- nejnovější datum v tabulce
  records_synced INTEGER,     -- počet záznamů v posledním sync
  sync_mode STRING,           -- "full" nebo "incremental"
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
```

### Dotaz na stav sync
```sql
SELECT * FROM `project.dataset._sync_metadata`
ORDER BY updated_at DESC
```

## 🔧 Monitoring a Troubleshooting

### Kontrola stavu synchronizace
```bash
# Zobrazí metadata všech tabulek
bq query --use_legacy_sql=false "
SELECT 
  table_name,
  last_sync_timestamp,
  last_max_date,
  records_synced,
  sync_mode
FROM \`havlikova-apoteka.pohoda._sync_metadata\`
ORDER BY updated_at DESC
"
```

### Reset na full sync
```bash
# Smaže metadata pro force full sync
bq query --use_legacy_sql=false "
DELETE FROM \`havlikova-apoteka.pohoda._sync_metadata\`
WHERE table_name = 'FA'
"
```

### Log monitoring
```bash
# Sleduj logy pro MERGE statistiky
tail -f sync.log | grep -E "(MERGE|Vloženo|Aktualizováno)"
```

## 🎯 Doporučené workflow

### Denní produkční provoz
1. **Morning**: incremental sync (rychlý)
   ```bash
   # Crontab: 0 6 * * * cd /var/projekt && make sync-inc
   ```

2. **Weekly**: full sync (kompletní refresh)
   ```bash  
   # Crontab: 0 2 * * 0 cd /var/projekt && make sync-full
   ```

### První nasazení
1. Spusť full sync pro historická data
2. Nastav incremental mode pro běžný provoz
3. Monitruj metadata tabulku

---

**Závěr**: Implementace je hotová! Máte nyní skutečný incremental update s MERGE operací, metadata tracking a optimalizované filtrování dat. 🎉