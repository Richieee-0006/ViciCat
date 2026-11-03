# ViciCat

Automated application & game categorizer for **Vicinae** using **Local LLMs** (Ollama / OpenAI-compatible `llama-swap` / `llama-server`) with **Cloud LLM** (Google Gemini / Gemma REST API) fallback.

Forked and reworked from [CatWalker](https://github.com/Richieee-0006/CatWalker) specifically for the [Vicinae](https://vicinae.com) launcher.

## Features

- **Native Vicinae Extension**: Generates a native `@vicinae/api` extension (`~/.local/share/vicinae/extensions/store.vicinae.vicicat`) with dedicated commands for every category (`Games`, `Development`, `Browser`, `Internet`, `Media`, `Graphics`, `Office`, `Education`, `Utility`, `System`, `Settings`) plus a combined `Apps (Categories)` browser with a category dropdown filter.
- **Pinned Root Favorites**: Automatically pins all non-empty categories (sorted by usage) to the top of Vicinae's root view (`favorites` in `~/.config/vicinae/settings.json`) while keeping individual apps searchable when typing.
- **Live Usage Sorting**: Reads `~/.local/share/vicinae/metadata.json` directly so both category order and apps inside `Games` (and every other group) are sorted by real launch frequency and recency.
- **Local-First + Cloud Fallback**:
  1. **Local LLM (default primary)**: Auto-detects running [Ollama](https://ollama.com) (`http://127.0.0.1:11434`, default model `gemma4:26b-a4b-it-qat` or first available local model) or any OpenAI-compatible server (`http://127.0.0.1:8080/v1`, e.g. `llama-swap`).
  2. **Cloud LLM (fallback)**: Falls back to Google's Gemini/Gemma REST API (`gemma-3-27b-it`) if `GEMINI_API_KEY` is set.
  3. **Zero-Token Game Fast-Path**: Automatically detects Steam (`steam://rungameid/`), Lutris (`lutris:rungame`), and Heroic (`heroic://launch`) `.desktop` shortcuts as `Games` instantly.
- **Automated Watcher & Timer**: Includes `systemd --user` `.path` watcher (monitoring `/usr/share/applications` and `~/.local/share/applications`) and `.timer` so newly installed Steam/Heroic/pacman games are grouped automatically.

## Replicable Setup

### 1. Clone & Install

```bash
git clone https://github.com/Richieee-0006/ViciCat.git ~/Projects/ViciCat
cd ~/Projects/ViciCat

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

chmod +x vicicat main.py
ln -sf "$(pwd)/vicicat" ~/.local/bin/vicicat
```

### 2. Configure Local and/or Cloud LLM

#### Option A: Local LLM via Ollama (Recommended, zero API key required)
```bash
# Install & start Ollama, then pull Gemma 4 (or any instruction model):
ollama pull gemma4:26b-a4b-it-qat
```
*(If a different model is installed in Ollama, ViciCat auto-detects it via `/api/tags`, or you can set `VICICAT_LOCAL_MODEL` in `.env`.)*

#### Option B: Local OpenAI-Compatible Server (`llama-swap` / `llama-server`)
```bash
export VICICAT_LOCAL_URL="http://127.0.0.1:8080"
export VICICAT_LOCAL_MODEL="coder-pro"
```

#### Option C: Cloud LLM via Google Gemini REST API
```bash
cat << 'EOF' > ~/Projects/ViciCat/.env
GEMINI_API_KEY="your-google-ai-studio-key"
VICICAT_PROVIDER="auto"   # auto (local-first -> cloud) | local | cloud
EOF
```

### 3. Categorize & Generate Vicinae Groups

```bash
# Scan uncategorized desktop apps
vicicat scan --uncategorized

# Categorize uncategorized apps (Local-first -> Cloud fallback) and generate Vicinae extension
vicicat categorize --yes
vicicat menus

# Or run both non-interactively in one step:
vicicat auto --force
```

### 4. Enable Automatic Background Grouping (`systemd --user`)

Automatically categorize and group new games/apps whenever Steam, Heroic, Lutris, Flatpak, or `pacman` adds a `.desktop` file:

```bash
vicicat service install
vicicat service status
```

## CLI Reference

```bash
vicicat scan [-u|--uncategorized] [-c|--category Games] [-l|--limit 20]
vicicat categorize [-y|--yes] [--dry-run] [-r|--recategorize] [--provider auto|local|cloud] [--model MODEL]
vicicat menus [--dry-run] [--clean]
vicicat auto [-f|--force]
vicicat service [install|uninstall|status]
vicicat rollback [-l|--list] [-t|--timestamp TS]
```
