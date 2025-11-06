#!/bin/bash
# Skript pro vyčištění problematického Microsoft repository

echo "🧹 Čištění Microsoft repository..."

# Odstraň problematický repository soubor
if [ -f /etc/apt/sources.list.d/mssql-release.list ]; then
    echo "📝 Odstraňuji starý Microsoft repository..."
    sudo rm /etc/apt/sources.list.d/mssql-release.list
fi

# Aktualizuj package cache
echo "📦 Aktualizace package cache..."
sudo apt-get update

echo "✅ Repository vyčištěn!"
echo "💡 Nyní můžete spustit: make install-odbc-alt"