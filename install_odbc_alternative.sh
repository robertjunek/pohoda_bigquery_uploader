#!/bin/bash
# Alternativní instalační skript pro ODBC driver - přímé stažení .deb balíčků

set -e  # Ukončit při chybě

echo "========================================"
echo "🔧 Alternativní instalace ODBC Driver"
echo "========================================"
echo ""

# Detekce distribuce
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VERSION=$VERSION_ID
else
    echo "❌ Nepodařilo se detekovat operační systém"
    exit 1
fi

echo "📋 Detekovaný systém: $OS $VERSION"
echo ""

# Kontrola práv sudo
if ! sudo -v; then
    echo "❌ Tento skript vyžaduje sudo práva"
    exit 1
fi

# Práce s dočasnou složkou
TMP_DIR=$(mktemp -d)
cd "$TMP_DIR"

echo "📁 Pracovní složka: $TMP_DIR"
echo ""

if [[ $OS == *"Ubuntu"* ]] || [[ $OS == *"Debian"* ]]; then
    echo "🐧 Alternativní instalace pro Ubuntu/Debian..."
    echo ""
    
    # Aktualizace package seznamu
    echo "📦 Aktualizace package seznamu..."
    sudo apt-get update
    
    # Instalace základních závislostí
    echo "📦 Instalace základních závislostí..."
    sudo apt-get install -y curl wget gnupg2 apt-transport-https unixodbc unixodbc-dev odbcinst
    
    # Detekce architektury
    ARCH=$(dpkg --print-architecture)
    echo "🏗️  Architektura: $ARCH"
    
    # URL pro nejnovější ODBC driver
    ODBC_URL="https://packages.microsoft.com/debian/11/prod/pool/main/m/msodbcsql18"
    
    echo "🔍 Hledání nejnovější verze ODBC driveru..."
    
    # Stažení seznamu balíčků
    PACKAGES_LIST=$(curl -s "https://packages.microsoft.com/debian/11/prod/dists/11/main/binary-${ARCH}/Packages" | grep "^Filename:" | grep "msodbcsql18")
    
    if [ -z "$PACKAGES_LIST" ]; then
        echo "❌ Nepodařilo se najít ODBC driver balíček"
        echo "💡 Zkusím přímé URL..."
        
        # Fallback - zkusíme známé verze
        KNOWN_VERSIONS=(
            "msodbcsql18_18.4.1.1-1_amd64.deb"
            "msodbcsql18_18.3.3.1-1_amd64.deb"
            "msodbcsql18_18.3.2.1-1_amd64.deb"
        )
        
        for version in "${KNOWN_VERSIONS[@]}"; do
            echo "🔍 Zkouším verzi: $version"
            if curl --head --silent --fail "${ODBC_URL}/${version}" > /dev/null; then
                PACKAGE_FILE="$version"
                break
            fi
        done
        
        if [ -z "$PACKAGE_FILE" ]; then
            echo "❌ Nepodařilo se najít žádnou funkční verzi"
            exit 1
        fi
    else
        # Extrahujeme nejnovější balíček
        PACKAGE_FILE=$(echo "$PACKAGES_LIST" | head -1 | awk '{print $2}')
        echo "✅ Nalezen balíček: $PACKAGE_FILE"
    fi
    
    # Stažení ODBC driver
    echo "📥 Stahování ODBC driver: $PACKAGE_FILE"
    DOWNLOAD_URL="${ODBC_URL}/${PACKAGE_FILE}"
    
    if ! wget "$DOWNLOAD_URL"; then
        echo "❌ Stahování selhalo z: $DOWNLOAD_URL"
        exit 1
    fi
    
    # Instalace ODBC driver
    echo "🔧 Instalace ODBC driver..."
    sudo ACCEPT_EULA=Y dpkg -i "$PACKAGE_FILE" || {
        echo "⚠️  Opravování závislostí..."
        sudo apt-get install -f -y
        sudo ACCEPT_EULA=Y dpkg -i "$PACKAGE_FILE"
    }
    
    # Pokus o instalace mssql-tools
    echo "🛠️  Pokus o instalaci mssql-tools..."
    TOOLS_URL="https://packages.microsoft.com/debian/11/prod/pool/main/m/mssql-tools18"
    
    # Hledání mssql-tools
    TOOLS_LIST=$(curl -s "https://packages.microsoft.com/debian/11/prod/dists/11/main/binary-${ARCH}/Packages" | grep "^Filename:" | grep "mssql-tools18" | head -1)
    
    if [ ! -z "$TOOLS_LIST" ]; then
        TOOLS_FILE=$(echo "$TOOLS_LIST" | awk '{print $2}')
        echo "📥 Stahování mssql-tools: $TOOLS_FILE"
        
        if wget "${TOOLS_URL}/${TOOLS_FILE}"; then
            echo "🔧 Instalace mssql-tools..."
            sudo ACCEPT_EULA=Y dpkg -i "$TOOLS_FILE" || {
                echo "⚠️  Opravování závislostí pro mssql-tools..."
                sudo apt-get install -f -y
                sudo ACCEPT_EULA=Y dpkg -i "$TOOLS_FILE" || echo "❌ mssql-tools se nepodařilo nainstalovat"
            }
            
            # Přidání tools do PATH
            echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.bashrc
            echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.zshrc
        else
            echo "⚠️  mssql-tools se nepodařilo stáhnout"
        fi
    else
        echo "⚠️  mssql-tools balíček nenalezen"
    fi

else
    echo "❌ Alternativní instalace podporuje pouze Ubuntu/Debian"
    echo "💡 Pro RHEL/CentOS použijte původní install_odbc.sh"
    exit 1
fi

# Úklid
cd /
rm -rf "$TMP_DIR"

echo ""
echo "✅ Alternativní instalace dokončena!"
echo ""

# Ověření instalace
echo "🔍 Ověření instalace..."
echo ""

# Kontrola dostupných ODBC driverů
echo "📋 Dostupné ODBC drivery:"
odbcinst -q -d

echo ""

# Kontrola konkrétního driveru
if odbcinst -q -d | grep -q "ODBC Driver 18 for SQL Server"; then
    echo "✅ ODBC Driver 18 for SQL Server je nainstalován"
else
    echo "❌ ODBC Driver 18 for SQL Server nebyl nalezen"
fi

echo ""

# Kontrola libodbc.so.2
echo "🔍 Kontrola libodbc.so.2..."
if ldconfig -p | grep -q "libodbc.so.2"; then
    echo "✅ libodbc.so.2 je dostupný"
    libodbc_path=$(ldconfig -p | grep "libodbc.so.2" | awk '{print $NF}' | head -1)
    echo "   Cesta: $libodbc_path"
else
    echo "❌ libodbc.so.2 nebyl nalezen"
    echo "💡 Možná je potřeba restartovat systém nebo upravit LD_LIBRARY_PATH"
fi

echo ""
echo "========================================"
echo "🎉 Alternativní instalace dokončena!"
echo "========================================"
echo ""
echo "📝 Další kroky:"
echo "1. Restartujte terminál nebo spusťte: source ~/.bashrc"
echo "2. Spusťte test připojení: make test-conn"
echo "3. Pokud máte stále problémy, restartujte systém"
echo ""