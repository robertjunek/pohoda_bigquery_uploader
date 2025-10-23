# GitHub Pages Setup

Tento projekt má připravenou dokumentaci pro GitHub Pages.

## Aktivace GitHub Pages

1. **Push do GitHubu:**
   ```bash
   git add .
   git commit -m "Add GitHub Pages documentation"
   git push origin main
   ```

2. **Aktivuj GitHub Pages:**
   - Jdi na GitHub repozitář
   - Settings → Pages
   - Source: Deploy from a branch
   - Branch: `main` / `docs` (root)
   - Save

3. **Počkej pár minut** - GitHub automaticky sestaví stránky

4. **Otevři dokumentaci:**
   ```
   https://tvuj-username.github.io/apoteka-veverka/
   ```

## Struktura dokumentace

```
apoteka_veverka/
├── _config.yml           # Jekyll konfigurace
├── index.md              # Hlavní stránka (README)
└── docs/
    ├── installation.md   # Instalace
    ├── usage.md          # Použití
    ├── configuration.md  # Konfigurace
    └── troubleshooting.md # Troubleshooting
```

## Theme

Používá **Cayman theme** - moderní, čistý vzhled.

Můžeš změnit v `_config.yml`:
- `jekyll-theme-minimal`
- `jekyll-theme-slate`
- `jekyll-theme-architect`
- `jekyll-theme-cayman` (aktuální)
- `jekyll-theme-hacker`

## Vlastní doména (volitelné)

1. Vytvoř soubor `CNAME`:
   ```
   docs.tvoje-domena.cz
   ```

2. Nastav DNS:
   ```
   docs  CNAME  tvuj-username.github.io
   ```

3. V GitHub Settings → Pages nastav custom domain

## Lokální náhled

```bash
# Instalace Jekyll
gem install bundler jekyll

# Vytvoření Gemfile
bundle init
bundle add jekyll

# Spuštění
bundle exec jekyll serve

# Otevři http://localhost:4000
```

## Tips

- Badge generátor: https://shields.io/
- Emoji: https://gist.github.com/rxaviers/7360908
- Markdown guide: https://guides.github.com/features/mastering-markdown/
