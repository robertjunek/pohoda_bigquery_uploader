.PHONY: help install install-odbc install-odbc-alt finish-odbc config test-conn test-sync test-sync-incremental test-sync-full sync sync-incremental sync-full status logs clean diagnose

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
	@echo "🚀 Spouštění:"
	@echo "  make test-sync      - Testovací spuštění synchronizace (current mode)"
	@echo "  make test-sync-full - Testovací spuštění (full mode)"
	@echo "  make test-sync-inc  - Testovací spuštění (incremental mode)"
	@echo "  make sync           - Spuštění synchronizace (current mode)"
	@echo "  make sync-full      - Spuštění (full mode)"
	@echo "  make sync-inc       - Spuštění (incremental mode)"
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
	@echo "  1. make install-odbc (nebo install-odbc-alt pro Debian 12)"
	@echo "  2. make finish-odbc (pokud manuální instalace)"
	@echo "  3. make install"
	@echo "  4. make config"
	@echo "  5. make test-conn"
	@echo "  6. make test-sync"
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

test-sync-full:
	@echo "🧪 Testovací synchronizace (FULL mode)..."
	@echo "⚙️  Dočasně nastavuji mode na 'full'..."
	@cp config.json config.json.backup
	@sed 's/"mode": "[^"]*"/"mode": "full"/g' config.json > config.json.tmp && mv config.json.tmp config.json
	@./test_sync.sh
	@mv config.json.backup config.json

test-sync-inc:
	@echo "🧪 Testovací synchronizace (INCREMENTAL mode)..."
	@echo "⚙️  Dočasně nastavuji mode na 'incremental'..."
	@cp config.json config.json.backup
	@sed 's/"mode": "[^"]*"/"mode": "incremental"/g' config.json > config.json.tmp && mv config.json.tmp config.json
	@./test_sync.sh
	@mv config.json.backup config.json

sync:
	@echo "🚀 Spouštím synchronizaci..."
	@.venv/bin/python sync_pohoda_to_bigquery.py

sync-full:
	@echo "🚀 Spouštím synchronizaci (FULL mode)..."
	@echo "⚙️  Dočasně nastavuji mode na 'full'..."
	@cp config.json config.json.backup
	@sed 's/"mode": "[^"]*"/"mode": "full"/g' config.json > config.json.tmp && mv config.json.tmp config.json
	@.venv/bin/python sync_pohoda_to_bigquery.py
	@mv config.json.backup config.json

sync-inc:
	@echo "🚀 Spouštím synchronizaci (INCREMENTAL mode)..."
	@echo "⚙️  Dočasně nastavuji mode na 'incremental'..."
	@cp config.json config.json.backup
	@sed 's/"mode": "[^"]*"/"mode": "incremental"/g' config.json > config.json.tmp && mv config.json.tmp config.json
	@.venv/bin/python sync_pohoda_to_bigquery.py
	@mv config.json.backup config.json

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

diagnose:
	@echo "🩺 ODBC diagnostika..."
	@python3 diagnose_odbc.py
