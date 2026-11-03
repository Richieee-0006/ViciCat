import os
from pathlib import Path

# LLM Configuration (Local-first with Cloud fallback)
PROVIDER = os.getenv("VICICAT_PROVIDER", "auto")  # auto | local | cloud

# Local LLM (Ollama or OpenAI-compatible like llama-swap)
LOCAL_API_URL = os.getenv("VICICAT_LOCAL_URL", "http://127.0.0.1:11434")
LOCAL_MODEL = os.getenv("VICICAT_LOCAL_MODEL", "gemma4:26b-a4b-it-qat")

# Cloud LLM (Google Gemini / Gemma REST API)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
CLOUD_MODEL = os.getenv("VICICAT_CLOUD_MODEL", "gemma-3-27b-it")

MAX_RETRIES = 3
TIMEOUT = 120

# Paths
XDG_DATA_HOME = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local/share"))
XDG_CONFIG_HOME = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))

SYSTEM_APPS_DIR = Path("/usr/share/applications")
USER_APPS_DIR = XDG_DATA_HOME / "applications"
APP_DATA_DIR = XDG_DATA_HOME / "vicicat"
BACKUP_DIR = APP_DATA_DIR / "backups"
STATE_FILE = APP_DATA_DIR / "state.json"

VICINAE_CONFIG_PATH = XDG_CONFIG_HOME / "vicinae/settings.json"
VICINAE_DATA_DIR = XDG_DATA_HOME / "vicinae"
VICINAE_METADATA_PATH = VICINAE_DATA_DIR / "metadata.json"
VICINAE_EXT_ID = "store.vicinae.vicicat"
VICINAE_EXT_AUTHOR = "vicicat"
VICINAE_EXT_DIR = VICINAE_DATA_DIR / "extensions" / VICINAE_EXT_ID

USER_APPS_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CATEGORIES = [
    "Games",
    "Development",
    "Browser",
    "Internet",
    "Media",
    "Graphics",
    "Office",
    "Education",
    "Utility",
    "System",
    "Settings",
]

CATEGORY_MAPPINGS = {
    "Development": "Development",
    "System": "System",
    "Media": "AudioVideo",
    "Office": "Office",
    "Games": "Game",
    "Browser": "WebBrowser",
    "Internet": "Network",
    "Graphics": "Graphics",
    "Utility": "Utility",
    "Settings": "Settings",
    "Education": "Education",
}

REVERSE_CATEGORY_MAPPING = {
    "WebBrowser": "Browser",
    "Development": "Development",
    "System": "System",
    "AudioVideo": "Media",
    "Audio": "Media",
    "Video": "Media",
    "Office": "Office",
    "Game": "Games",
    "Network": "Internet",
    "Graphics": "Graphics",
    "Utility": "Utility",
    "Settings": "Settings",
    "Education": "Education",
}

CATEGORIZATION_PROMPT = """You are an expert at categorizing Linux desktop applications.

Categorize each application into ONE of these categories:
{categories}

Rules:
- Choose the MOST appropriate single category
- Steam, Lutris, Heroic, Prism Launcher, Minecraft, and video games MUST be categorized as "Games"
- If unsure, use "Utility"
- Return ONLY valid JSON format with no markdown explanation

Format:
{{
  "app_filename.desktop": "Category"
}}

Applications:
{applications}"""
