#!/bin/bash
# Testovací skript pro ověření funkčnosti synchronizace

echo "==================================="
echo "Test synchronizace Pohoda → BigQuery"
echo "==================================="
echo ""

# Změna do složky projektu
cd "$(dirname "$0")" || exit 1

# Kontrola virtual environment
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment .venv nenalezen!"
    exit 1
fi

# Kontrola konfiguračních souborů
if [ ! -f "config.json" ]; then
    echo "❌ Konfigurační soubor config.json nenalezen!"
    exit 1
fi

if [ ! -f "veverka.json" ]; then
    echo "❌ Credentials veverka.json nenalezen!"
    exit 1
fi

# Aktivace venv a spuštění
echo "🚀 Spouštím synchronizaci..."
echo ""

.venv/bin/python sync_pohoda_to_bigquery.py

EXIT_CODE=$?

echo ""
echo "==================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Synchronizace dokončena úspěšně"
else
    echo "❌ Synchronizace selhala (exit code: $EXIT_CODE)"
fi
echo "==================================="

exit $EXIT_CODE
