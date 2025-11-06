# 🚨 Řešení chyby libodbc.so.2

Pokud dostáváte chybu:
```
ImportError: libodbc.so.2: cannot open shared object file: No such file or directory
```

## Rychlé řešení

### 1. Automatická instalace (doporučeno)
```bash
make install-odbc
```

### 2. Pro Debian 12 (pokud základní instalace selže)
```bash
make install-odbc-alt
```

### 3. Manuální instalace
```bash
sudo ./install_odbc.sh
# nebo pro Debian 12
sudo ./install_odbc_alternative.sh
```

### 4. Diagnostika problému
```bash
make diagnose
```

## Co se instaluje

- **ODBC Driver 18 for SQL Server** - ovladač pro připojení k MS SQL
- **unixODBC development libraries** - systémové knihovny pro pyodbc
- **mssql-tools18** - sqlcmd a bcp nástroje (volitelně)

## Po instalaci

1. **Restartujte terminál** nebo spusťte:
   ```bash
   source ~/.bashrc
   ```

2. **Ověřte instalaci**:
   ```bash
   make test-conn
   ```

3. **Spusťte synchronizaci**:
   ```bash
   make test-sync
   ```

## Řešení problémů

### Chyba: "Repository not found" (Debian 12)
Microsoft zatím neposkytuje oficiální repository pro Debian 12. Použijte:
```bash
make install-odbc-alt
```

### Chyba: "odbcinst command not found"
```bash
# Ubuntu/Debian
sudo apt-get install unixodbc-dev

# RHEL/CentOS
sudo yum install unixODBC-devel
```

### Chyba: "ACCEPT_EULA required"
Instalační skript automaticky přijímá EULA. Pokud instalujete ručně:
```bash
sudo ACCEPT_EULA=Y apt-get install msodbcsql18
```

### Chyba: "Repository not found"
Aktualizujte package cache:
```bash
# Ubuntu/Debian
sudo apt-get update

# RHEL/CentOS  
sudo yum makecache
```

### Stále nefunguje?
1. Restartujte systém
2. Zkontrolujte LD_LIBRARY_PATH
3. Spusťte kompletní diagnostiku: `make diagnose`

## Podporované systémy

- ✅ Ubuntu 18.04, 20.04, 22.04, 24.04
- ✅ Debian 10, 11, 12
- ✅ RHEL/CentOS 7, 8, 9
- ✅ Rocky Linux 8, 9
- ✅ AlmaLinux 8, 9

## Další informace

- [Oficiální dokumentace](https://docs.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server)
- [Detailní instalační průvodce](docs/installation.md)