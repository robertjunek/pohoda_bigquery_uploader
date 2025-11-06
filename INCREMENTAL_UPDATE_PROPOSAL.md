# 💡 Implementace Incremental Update

## 🔍 Současný problém

Váš skript **NEŘEŠÍ skutečný incremental update**:

1. **❌ Přepisuje celé tabulky** - používá `WRITE_TRUNCATE`
2. **❌ Stahuje mnoho dat zbytečně** - `days_back: 4000` = cca 11 let
3. **❌ Žádná logika pro UPDATE** - jen INSERT celé tabulky znovu
4. **❌ Nepoužívá ID pro detekci změn**

## ✅ Co by měl dělat skutečný incremental update

### 1. **Detekce změněných záznamů**
```sql
-- Místo tohoto (současný stav):
WHERE COALESCE(h.DatSave, h.DatCreate ) >= GETDATE() - 4000

-- Mělo by být toto:
WHERE COALESCE(h.DatSave, h.DatCreate) > @last_sync_timestamp
OR h.ID IN (SELECT id FROM changed_records)
```

### 2. **MERGE místo TRUNCATE**
```sql
-- BigQuery MERGE statement
MERGE dataset.table_name T
USING temp_new_data S
ON T.ID = S.ID
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

### 3. **Tracking posledního synchronizačního času**
```python
# Uložení timestamp poslední synchronizace
def save_last_sync_time(table_name: str, timestamp: datetime):
    # Uložit do metadata tabulky nebo samostatné tabulky
```

## 🚀 Návrh implementace

### Krok 1: Přidání sync metadata

```python
def create_sync_metadata_table(self):
    """Vytvoří tabulku pro tracking synchronizace."""
    query = """
    CREATE TABLE IF NOT EXISTS `{project}.{dataset}._sync_metadata` (
        table_name STRING,
        last_sync_timestamp TIMESTAMP,
        last_sync_max_id STRING,
        records_synced INT64,
        sync_mode STRING,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
    )
    """
```

### Krok 2: Modifikace SQL dotazů

```python
def modify_sql_for_incremental(self, sql_content: str, table_name: str) -> str:
    """Upraví SQL pro incremental sync."""
    
    # Získej poslední sync timestamp
    last_sync = self.get_last_sync_timestamp(table_name)
    
    if last_sync:
        # Přidej podmínku pro jen nové/upravené záznamy
        incremental_condition = f"""
        AND (
            COALESCE(h.DatSave, h.DatCreate) > '{last_sync}'
            OR h.ID > (SELECT COALESCE(MAX(last_max_id), 0) FROM sync_metadata WHERE table_name = '{table_name}')
        )
        """
        sql_content = sql_content.replace(
            'WHERE r.Kod IS NOT NULL',
            f'WHERE r.Kod IS NOT NULL {incremental_condition}'
        )
    
    return sql_content
```

### Krok 3: MERGE místo TRUNCATE

```python
def upload_incremental(self, df: pd.DataFrame, table_name: str):
    """Nahraje data s MERGE logikou."""
    
    # 1. Vytvoř dočasnou tabulku
    temp_table = f"temp_{table_name}_{int(time.time())}"
    
    # 2. Nahraj data do temp tabulky
    self.upload_to_temp_table(df, temp_table)
    
    # 3. Proveď MERGE
    merge_query = f"""
    MERGE `{self.project}.{self.dataset}.{table_name}` T
    USING `{self.project}.{self.dataset}.{temp_table}` S
    ON T.ID = S.ID
    WHEN MATCHED THEN 
        UPDATE SET * EXCEPT(ID)
    WHEN NOT MATCHED THEN 
        INSERT *
    """
    
    # 4. Spusť MERGE
    self.bq_client.query(merge_query).result()
    
    # 5. Smaž temp tabulku
    self.drop_temp_table(temp_table)
```

## 📋 Konfigurace pro incremental

### Rozšířit config.json:

```json
{
  "sync": {
    "mode": "incremental",  // "full" nebo "incremental"
    "batch_size": 5000,
    "days_back": 7,         // Pro first run nebo full sync
    "incremental_field": "DatSave",  // Pole pro tracking změn
    "merge_strategy": "upsert"       // "upsert", "append", "replace"
  }
}
```

## 🛠️ Implementace do současného kódu

### 1. Upravit upload_to_bigquery metodu:

```python
def upload_to_bigquery(self, df: pd.DataFrame, table_name: str, batch_size: int):
    """Upravená verze s incremental podporou."""
    
    sync_mode = self.config['sync'].get('mode', 'full')
    
    if sync_mode == 'incremental' and self.table_exists(table_name):
        # Incremental update
        self.upload_incremental(df, table_name)
        self.update_sync_metadata(table_name, df)
    else:
        # Full refresh (současná logika)
        self.upload_full_refresh(df, table_name, batch_size)
```

### 2. Snížit days_back pro běžný provoz:

```python
# V _add_table_prefix metodě:
if self.sync_mode == 'incremental':
    days_back = 3  # Jen poslední 3 dny pro bezpečnost
else:
    days_back = self.config['sync'].get('days_back', 14)
```

## ⚡ Výhody incremental update

1. **🚀 Rychlost** - stahuje jen nová/změněná data
2. **💾 Úspora zdrojů** - méně dat přes síť
3. **📊 Historické záznamy** - nemazáním celé tabulky
4. **🔄 Častější sync** - může běžet každou hodinu
5. **💰 Nižší náklady** - méně BigQuery operací

## 📝 Doporučení

### Okamžité:
```bash
# Snižte days_back pro současný provoz
"days_back": 7   # místo 4000
```

### Dlouhodobé:
1. Implementujte MERGE logiku
2. Přidejte sync metadata tracking
3. Nastavte incremental mode jako default
4. Přidejte monitoring a alerting

## 🧪 Testování

```bash
# Test full sync
make test-sync

# Test incremental (po implementaci)
make test-sync-incremental

# Monitoring velikosti dat
make sync-stats
```

---

**Závěr:** Současný kód dělá jen "full refresh", ne skutečný incremental update. Pro efektivní provoz byste měli implementovat MERGE logiku a metadata tracking.