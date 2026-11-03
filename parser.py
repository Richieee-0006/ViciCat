import configparser
import logging
from pathlib import Path
from typing import Dict, List, Optional

from config import SYSTEM_APPS_DIR, USER_APPS_DIR

logger = logging.getLogger(__name__)


class DesktopEntry:
    """Represents a parsed .desktop file"""

    def __init__(self, filename: str, filepath: Path):
        self.filename = filename
        self.filepath = filepath
        self.name: str = ""
        self.comment: str = ""
        self.generic_name: str = ""
        self.categories: List[str] = []
        self.icon: str = ""
        self.exec_cmd: str = ""
        self.no_display: bool = False

    @property
    def app_id(self) -> str:
        return Path(self.filename).stem

    def is_obvious_game(self) -> bool:
        exec_lower = self.exec_cmd.lower()
        comment_lower = self.comment.lower()
        return (
            "steam://rungameid/" in exec_lower
            or "lutris:rungame" in exec_lower
            or "heroic://launch" in exec_lower
            or "play this game on steam" in comment_lower
            or "Game" in self.categories
        )

    def get_context(self) -> str:
        context_parts = [self.name]
        if self.generic_name and self.generic_name != self.name:
            context_parts.append(f"({self.generic_name})")
        if self.comment:
            context_parts.append(f"- {self.comment}")
        if "steam" in self.exec_cmd.lower():
            context_parts.append("[Steam]")
        return " ".join(context_parts)


class DesktopFileParser:
    """Parser for .desktop files"""

    def __init__(self):
        self.entries: Dict[str, DesktopEntry] = {}

    def parse_file(self, filepath: Path) -> Optional[DesktopEntry]:
        try:
            config = configparser.ConfigParser(strict=False, interpolation=None)
            config.read(filepath, encoding="utf-8")

            if "Desktop Entry" not in config:
                return None

            section = config["Desktop Entry"]
            if section.get("NoDisplay", "").lower() == "true":
                return None
            if section.get("Hidden", "").lower() == "true":
                return None
            if section.get("Type", "").lower() != "application":
                return None

            entry = DesktopEntry(filepath.name, filepath)
            entry.name = section.get("Name", filepath.stem)
            entry.comment = section.get("Comment", "")
            entry.generic_name = section.get("GenericName", "")
            entry.icon = section.get("Icon", "")
            entry.exec_cmd = section.get("Exec", "")

            categories_str = section.get("Categories", "")
            if categories_str:
                entry.categories = [c.strip() for c in categories_str.split(";") if c.strip()]

            return entry
        except Exception as e:
            logger.error(f"Error parsing {filepath}: {e}")
            return None

    def scan_directories(self, directories: List[Path]) -> Dict[str, DesktopEntry]:
        entries = {}
        for directory in directories:
            if not directory.exists():
                continue
            for filepath in sorted(directory.glob("*.desktop")):
                entry = self.parse_file(filepath)
                if entry:
                    entries[filepath.name] = entry
        return entries

    def scan_all(self) -> Dict[str, DesktopEntry]:
        self.entries = self.scan_directories([SYSTEM_APPS_DIR, USER_APPS_DIR])
        return self.entries

    def get_uncategorized(self) -> Dict[str, DesktopEntry]:
        return {f: e for f, e in self.entries.items() if not e.categories}

    def get_by_category(self, category: str) -> Dict[str, DesktopEntry]:
        return {f: e for f, e in self.entries.items() if category in e.categories}

    def get_system_only(self) -> Dict[str, DesktopEntry]:
        return {
            f: e for f, e in self.entries.items() if not (USER_APPS_DIR / f).exists()
        }
