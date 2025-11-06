#!/bin/bash
# Instalační skript pro ODBC driver a systémové závislosti

set -e  # Ukončit při chybě

echo "========================================"
echo "🔧 Instalace ODBC Driver pro MS SQL Server"
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

# Instalace podle distribuce
if [[ $OS == *"Ubuntu"* ]] || [[ $OS == *"Debian"* ]]; then
    echo "🐧 Instalace pro Ubuntu/Debian..."
    echo ""
    
    # Aktualizace package seznamu
    echo "📦 Aktualizace package seznamu..."
    sudo apt-get update
    
    # Instalace základních závislostí
    echo "📦 Instalace základních závislostí..."
    sudo apt-get install -y curl gnupg2 apt-transport-https
    
    # Přidání Microsoft repository klíče
    echo "🔑 Přidání Microsoft repository klíče..."
    curl -sSL https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
    
    # Přidání Microsoft repository
    echo "📋 Přidání Microsoft repository..."
    if [[ $OS == *"Ubuntu"* ]]; then
        UBUNTU_VERSION=$(lsb_release -rs)
        echo "deb [arch=amd64] https://packages.microsoft.com/ubuntu/${UBUNTU_VERSION}/prod ${UBUNTU_VERSION} main" | \
            sudo tee /etc/apt/sources.list.d/mssql-release.list
    else
        # Debian
        DEBIAN_VERSION=$(echo $VERSION | cut -d'.' -f1)
        echo "deb [arch=amd64] https://packages.microsoft.com/debian/${DEBIAN_VERSION}/prod ${DEBIAN_VERSION} main" | \
            sudo tee /etc/apt/sources.list.d/mssql-release.list
    fi
    
    # Aktualizace s novým repository
    echo "📦 Aktualizace s Microsoft repository..."
    sudo apt-get update
    
    # Instalace ODBC Driver
    echo "🔧 Instalace ODBC Driver 18 for SQL Server..."
    sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
    
    # Instalace unixODBC development headers (pro pyodbc)
    echo "🔧 Instalace unixODBC development tools..."
    sudo apt-get install -y unixodbc-dev
    
    # Volitelně - mssql-tools
    echo "🛠️  Instalace MSSQL tools (sqlcmd, bcp)..."
    sudo ACCEPT_EULA=Y apt-get install -y mssql-tools18
    
    # Přidání tools do PATH
    echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.bashrc
    echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.zshrc

elif [[ $OS == *"CentOS"* ]] || [[ $OS == *"Red Hat"* ]] || [[ $OS == *"Rocky"* ]] || [[ $OS == *"AlmaLinux"* ]]; then
    echo "🎩 Instalace pro RHEL/CentOS/Rocky/AlmaLinux..."
    echo ""
    
    # Instalace základních závislostí
    echo "📦 Instalace základních závislostí..."
    sudo yum install -y curl
    
    # Přidání Microsoft repository
    echo "📋 Přidání Microsoft repository..."
    sudo curl -o /etc/yum.repos.d/mssql-release.repo https://packages.microsoft.com/config/rhel/8/mssql-release.repo
    
    # Aktualizace
    echo "📦 Aktualizace package cache..."
    sudo yum makecache
    
    # Instalace ODBC Driver
    echo "🔧 Instalace ODBC Driver 18 for SQL Server..."
    sudo ACCEPT_EULA=Y yum install -y msodbcsql18
    
    # Instalace unixODBC development headers
    echo "🔧 Instalace unixODBC development tools..."
    sudo yum install -y unixODBC-devel
    
    # Volitelně - mssql-tools
    echo "🛠️  Instalace MSSQL tools (sqlcmd, bcp)..."
    sudo ACCEPT_EULA=Y yum install -y mssql-tools18
    
    # Přidání tools do PATH
    echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.bashrc
    echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.zshrc

else
    echo "❌ Nepodporovaná distribuce: $OS"
    echo "💡 Manuálně nainstalujte ODBC Driver 18 for SQL Server"
    echo "   Viz: https://docs.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server"
    exit 1
fi

echo ""
echo "✅ ODBC Driver nainstalován!"
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
echo "🎉 Instalace dokončena!"
echo "========================================"
echo ""
echo "📝 Další kroky:"
echo "1. Restartujte terminál nebo spusťte: source ~/.bashrc"
echo "2. Spusťte test připojení: make test-conn"
echo "3. Pokud máte stále problémy, restartujte systém"
echo ""
echo "💡 Tipy:"
echo "- sqlcmd je nyní dostupný v /opt/mssql-tools18/bin/"
echo "- Pro trvalé přidání do PATH restartujte terminál"
echo ""