import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import BACKUP_DIR, CATEGORY_MAPPINGS, USER_APPS_DIR
from parser import DesktopEntry

logger = logging.getLogger(__name__)


class DesktopFileWriter:
    """Safely writes .desktop files to user directory with backups."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.modified_files: List[str] = []

    def _get_backup_path(self, filename: str) -> Path:
        backup_subdir = BACKUP_DIR / self.backup_timestamp
        backup_subdir.mkdir(parents=True, exist_ok=True)
        return backup_subdir / filename

    def _backup_file(self, filepath: Path) -> bool:
        try:
            shutil.copy2(filepath, self._get_backup_path(filepath.name))
            return True
        except Exception as e:
            logger.error(f"Failed to backup {filepath}: {e}")
            return False

    def _ensure_user_copy(self, entry: DesktopEntry) -> Path:
        user_file = USER_APPS_DIR / entry.filename
        if user_file.exists():
            return user_file
        if entry.filepath.exists():
            shutil.copy2(entry.filepath, user_file)
            return user_file
        raise FileNotFoundError(f"Source file not found: {entry.filepath}")

    def _update_categories(self, filepath: Path, categories: List[str]) -> bool:
        try:
            content = filepath.read_text(encoding="utf-8")
            lines = content.splitlines()

            standard_keys = [
                "Name", "Exec", "Icon", "Type", "Comment", "GenericName",
                "Categories", "Terminal", "NoDisplay", "Keywords",
                "StartupNotify", "StartupWMClass", "MimeType", "Path",
                "Actions", "OnlyShowIn", "NotShowIn", "Hidden", "TryExec",
            ]
            key_map = {k.lower(): k for k in standard_keys}

            categories_str = ";".join(categories) + ";"
            new_lines = []
            categories_updated = False

            for line in lines:
                if "=" in line and not line.startswith("#") and not line.startswith("["):
                    key, value = line.split("=", 1)
                    key_lower = key.strip().lower()
                    if key_lower == "categories":
                        new_lines.append(f"Categories={categories_str}")
                        categories_updated = True
                        continue
                    key_fixed = key_map.get(key_lower, key.strip())
                    new_lines.append(f"{key_fixed}={value}")
                else:
                    new_lines.append(line)

            if not categories_updated:
                final_lines = []
                inserted = False
                for line in new_lines:
                    final_lines.append(line)
                    if line.strip() == "[Desktop Entry]" and not inserted:
                        final_lines.append(f"Categories={categories_str}")
                        inserted = True
                new_lines = final_lines

            new_content = "\n".join(new_lines) + ("\n" if content.endswith("\n") else "")
            filepath.write_text(new_content, encoding="utf-8")
            return True
        except Exception as e:
            logger.error(f"Failed to update {filepath}: {e}")
            return False

    def apply_categorization(
        self, entries: Dict[str, DesktopEntry], categorization: Dict[str, str]
    ) -> Dict[str, bool]:
        results = {}
        for filename, category in categorization.items():
            if filename not in entries:
                results[filename] = False
                continue

            entry = entries[filename]
            desktop_category = CATEGORY_MAPPINGS.get(category, category)

            if self.dry_run:
                results[filename] = True
                continue

            try:
                user_file = self._ensure_user_copy(entry)
                if user_file.exists():
                    self._backup_file(user_file)

                new_categories = list(entry.categories)
                if desktop_category not in new_categories:
                    new_categories.insert(0, desktop_category)

                success = self._update_categories(user_file, new_categories)
                if success:
                    self.modified_files.append(filename)
                results[filename] = success
            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
                results[filename] = False

        return results

    def rollback(self, backup_timestamp: Optional[str] = None) -> bool:
        try:
            if backup_timestamp:
                backup_dir = BACKUP_DIR / backup_timestamp
            else:
                backups = sorted(BACKUP_DIR.glob("*"), reverse=True)
                if not backups:
                    logger.error("No backups found")
                    return False
                backup_dir = backups[0]

            if not backup_dir.exists():
                logger.error(f"Backup not found: {backup_dir}")
                return False

            restored = 0
            for backup_file in backup_dir.glob("*.desktop"):
                shutil.copy2(backup_file, USER_APPS_DIR / backup_file.name)
                restored += 1

            logger.info(f"Restored {restored} files from {backup_dir.name}")
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def list_backups(self) -> List[str]:
        backups = sorted(BACKUP_DIR.glob("*"), reverse=True)
        return [b.name for b in backups if b.is_dir()]
