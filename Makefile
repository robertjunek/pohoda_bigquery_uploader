.PHONY: help install install-odbc install-odbc-alt finish-odbc config test-conn test run backfill backfill-db status logs logs-tail logs-errors clean diagnose

PY := .venv/bin/python

# Výchozí cíl
help:
	@echo "📋 Dostupné příkazy:"
	@echo ""
	@echo "🔧 Instalace:"
	@echo "  make install-odbc     - Instalace ODBC Driver (vyžaduje sudo)"
	@echo "  make install-odbc-alt - Alternativní instalace ODBC (pro Debian 12)"
	@echo "  make finish-odbc      - Dokončení ODBC instalace (po manuálním stažení)"
	@echo "  make install          - Instalace závislostí do venv"
	@echo ""
	@echo "⚙️  Konfigurace:"
	@echo "  make config       - Konfigurace MS SQL připojení"
	@echo "  make test-conn    - Test připojení k databázím"
	@echo "  make diagnose     - Diagnostika ODBC problémů"
	@echo ""
	@echo "🧪 Testy:"
	@echo "  make test         - Spuštění unit testů (pytest, bez živých připojení)"
	@echo ""
	@echo "🚀 Spouštění:"
	@echo "  make run                  - Synchronizace aktuálních dat (všechny bloky)"
	@echo "  make backfill             - Backfill historie (current zpracován poslední)"
	@echo "  make backfill-db DB=<db>  - Backfill jedné konkrétní databáze"
	@echo ""
	@echo "📊 Monitoring:"
	@echo "  make status       - Zobrazení stavu poslední synchronizace"
	@echo "  make logs         - Živé sledování logů"
	@echo "  make logs-tail    - Posledních 50 řádků logu"
	@echo "  make logs-errors  - Jen chyby z logu"
	@echo ""
	@echo "🧹 Údržba:"
	@echo "  make clean        - Vyčištění logů a cache"
	@echo ""

install-odbc:
	@echo "🔧 Instalace ODBC Driver..."
	@echo "⚠️  Tento příkaz vyžaduje sudo práva!"
	@./install_odbc.sh

install-odbc-alt:
	@echo "🔧 Alternativní instalace ODBC Driver..."
	@echo "⚠️  Tento příkaz vyžaduje sudo práva!"
	@echo "💡 Použije přímé stažení .deb balíčků"
	@./install_odbc_alternative.sh

finish-odbc:
	@echo "🔧 Dokončení ODBC instalace..."
	@echo "⚠️  Tento příkaz vyžaduje sudo práva!"
	@sudo ./finish_odbc_install.sh

install:
	@echo "📦 Instalace závislostí..."
	@$(PY) -m pip install -r requirements.txt

config:
	@echo "⚙️  Konfigurace..."
	@$(PY) setup_config.py

test-conn:
	@echo "🔌 Test připojení..."
	@$(PY) test_connections.py

test:
	@echo "🧪 Unit testy..."
	@$(PY) -m pytest -q

run:
	@echo "🚀 Synchronizace aktuálních dat..."
	@$(PY) sync_pohoda_to_bigquery.py

backfill:
	@echo "🕰️  Backfill historie (current poslední)..."
	@$(PY) sync_pohoda_to_bigquery.py --backfill

backfill-db:
	@if [ -z "$(DB)" ]; then echo "❌ Použij: make backfill-db DB=nazev_databaze"; exit 1; fi
	@echo "🕰️  Backfill databáze $(DB)..."
	@$(PY) sync_pohoda_to_bigquery.py --backfill --database $(DB)

status:
	@$(PY) check_status.py

logs:
	@echo "📜 Živé sledování logů (Ctrl+C pro ukončení)..."
	@tail -f sync.log

logs-tail:
	@echo "📜 Posledních 50 řádků logu:"
	@tail -n 50 sync.log

logs-errors:
	@echo "⚠️  Chyby v logu:"
	@grep ERROR sync.log || echo "Žádné chyby nenalezeny ✅"

clean:
	@echo "🧹 Čištění..."
	@rm -f sync.log* cron.log
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "✅ Vyčištěno"

diagnose:
	@echo "🩺 ODBC diagnostika..."
	@python3 diagnose_odbc.py
