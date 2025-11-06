#!/bin/bash
# Skript pro dokončení ODBC instalace na serveru

echo "========================================"
echo "🔧 Dokončení ODBC instalace"
echo "========================================"
echo ""

# Nainstalovat chybějící závislosti
echo "📦 Instalace chybějících ODBC balíčků..."
apt-get install -y unixodbc unixodbc-dev odbcinst

echo ""
echo "🔧 Dokončení instalace MS SQL ODBC driveru..."

# Dokončit instalaci ODBC driveru
if [ -f "msodbcsql18_18.4.1.1-1_amd64.deb" ]; then
    echo "📦 Dokončuji instalaci msodbcsql18..."
    ACCEPT_EULA=Y dpkg -i msodbcsql18_18.4.1.1-1_amd64.deb
else
    echo "❌ Soubor msodbcsql18_18.4.1.1-1_amd64.deb nenalezen"
    echo "💡 Stáhnu jej znovu..."
    wget https://packages.microsoft.com/debian/11/prod/pool/main/m/msodbcsql18/msodbcsql18_18.4.1.1-1_amd64.deb
    ACCEPT_EULA=Y dpkg -i msodbcsql18_18.4.1.1-1_amd64.deb
fi

echo ""
echo "🧹 Úklid..."
rm -f msodbcsql18_18.4.1.1-1_amd64.deb

echo ""
echo "🔍 Ověření instalace..."

# Kontrola dostupných ODBC driverů
echo "📋 Dostupné ODBC drivery:"
odbcinst -q -d

echo ""

# Kontrola konkrétního driveru
if odbcinst -q -d | grep -q "ODBC Driver 18 for SQL Server"; then
    echo "✅ ODBC Driver 18 for SQL Server je nainstalován"
else
    echo "❌ ODBC Driver 18 for SQL Server nebyl nalezen"
    exit 1
fi

# Kontrola libodbc.so.2
echo "🔍 Kontrola libodbc.so.2..."
if ldconfig -p | grep -q "libodbc.so.2"; then
    echo "✅ libodbc.so.2 je dostupný"
    libodbc_path=$(ldconfig -p | grep "libodbc.so.2" | awk '{print $NF}' | head -1)
    echo "   Cesta: $libodbc_path"
else
    echo "❌ libodbc.so.2 nebyl nalezen"
    echo "💡 Spouštím ldconfig..."
    ldconfig
    if ldconfig -p | grep -q "libodbc.so.2"; then
        echo "✅ libodbc.so.2 je nyní dostupný po ldconfig"
    else
        echo "❌ libodbc.so.2 stále není dostupný"
    fi
fi

echo ""
echo "========================================"
echo "🎉 ODBC instalace dokončena!"
echo "========================================"
echo ""
echo "📝 Další kroky:"
echo "1. Spusťte test připojení: make test-conn"
echo "2. Spusťte synchronizaci: make test-sync"
echo ""