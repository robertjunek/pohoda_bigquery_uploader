.PHONY: help install install-odbc config test-conn test-sync sync status logs clean

# Výchozí cíl
help:
	@echo "📋 Dostupné příkazy:"
	@echo ""
	@echo "🔧 Instalace:"
	@echo "  make install-odbc - Instalace ODBC Driver (vyžaduje sudo)"
	@echo "  make install      - Instalace závislostí do venv"
	@echo ""
	@echo "⚙️  Konfigurace:"
	@echo "  make config       - Konfigurace MS SQL připojení"
	@echo "  make test-conn    - Test připojení k databázím"
	@echo ""
	@echo "🚀 Spouštění:"
	@echo "  make test-sync    - Testovací spuštění synchronizace"
	@echo "  make sync         - Spuštění synchronizace"
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
	@echo "🚀 Rychlý start na novém serveru:"
	@echo "  1. make install-odbc"
	@echo "  2. make install"
	@echo "  3. make config"
	@echo "  4. make test-conn"
	@echo "  5. make test-sync"
	@echo ""

install-odbc:
	@echo "🔧 Instalace ODBC Driver..."
	@echo "⚠️  Tento příkaz vyžaduje sudo práva!"
	@./install_odbc.sh

install:
	@echo "📦 Instalace závislostí..."
	@.venv/bin/pip install -r requirements.txt

config:
	@echo "⚙️  Konfigurace..."
	@.venv/bin/python setup_config.py

test-conn:
	@echo "🔌 Test připojení..."
	@.venv/bin/python test_connections.py

test-sync:
	@echo "🧪 Testovací synchronizace..."
	@./test_sync.sh

sync:
	@echo "🚀 Spouštím synchronizaci..."
	@.venv/bin/python sync_pohoda_to_bigquery.py

status:
	@.venv/bin/python check_status.py

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
