#!/usr/bin/env python3
"""
ViciCat - Automated application & game categorization for Vicinae using Local & Cloud LLMs
"""

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

from categorizer import AppCategorizer
from config import (
    DEFAULT_CATEGORIES,
    PROVIDER,
    REVERSE_CATEGORY_MAPPING,
    STATE_FILE,
    VICINAE_EXT_DIR,
    XDG_CONFIG_HOME,
)
from menu_generator import MenuGenerator
from parser import DesktopEntry, DesktopFileParser
from writer import DesktopFileWriter

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _map_desktop_category(entry: DesktopEntry) -> Optional[str]:
    if entry.is_obvious_game():
        return "Games"
    if "WebBrowser" in entry.categories:
        return "Browser"
    for cat in entry.categories:
        if cat in REVERSE_CATEGORY_MAPPING:
            return REVERSE_CATEGORY_MAPPING[cat]
    return None


def _compute_fingerprint(entries: Dict[str, DesktopEntry]) -> str:
    items = sorted(
        f"{fname}:{','.join(sorted(e.categories))}:{e.name}" for fname, e in entries.items()
    )
    return hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()


def cmd_scan(args) -> int:
    parser = DesktopFileParser()
    entries = parser.scan_all()

    if args.uncategorized:
        entries = {f: e for f, e in entries.items() if not _map_desktop_category(e)}
    elif args.category:
        entries = {
            f: e
            for f, e in entries.items()
            if _map_desktop_category(e) == args.category or args.category in e.categories
        }

    print(f"Found {len(entries)} application(s):\n")
    for i, (filename, entry) in enumerate(entries.items(), 1):
        if args.limit and i > args.limit:
            print(f"... and {len(entries) - args.limit} more")
            break
        mapped = _map_desktop_category(entry) or "(uncategorized)"
        print(f"{i}. {entry.name} [{mapped}] ({filename})")
    return 0


def cmd_categorize(args) -> int:
    parser = DesktopFileParser()
    entries = parser.scan_all()

    if args.recategorize:
        target_entries = entries
    else:
        target_entries = {f: e for f, e in entries.items() if not _map_desktop_category(e)}

    if not target_entries:
        logger.info("All applications already have valid categories.")
        return 0

    if args.limit:
        target_entries = dict(list(target_entries.items())[: args.limit])

    try:
        categorizer = AppCategorizer(
            provider=args.provider,
            model=args.model,
            local_url=args.local_url,
        )
    except Exception as e:
        logger.error(str(e))
        return 1

    categorization = categorizer.categorize(target_entries, batch_size=args.batch_size)
    if not categorization:
        logger.error("Categorization returned no results.")
        return 1

    print(f"\nCategorized {len(categorization)} application(s):")
    for filename, category in categorization.items():
        entry = target_entries[filename]
        old_cats = ", ".join(entry.categories) if entry.categories else "None"
        print(f"  - {entry.name}: {old_cats} -> {category}")

    if args.dry_run:
        print("\n[DRY RUN] No files modified.")
        return 0

    if not args.yes:
        confirm = input("\nApply changes to ~/.local/share/applications? [y/N] ")
        if confirm.strip().lower() != "y":
            print("Cancelled.")
            return 0

    writer = DesktopFileWriter(dry_run=False)
    results = writer.apply_categorization(target_entries, categorization)
    ok = sum(1 for v in results.values() if v)
    print(f"Updated {ok}/{len(results)} .desktop files (backup: {writer.backup_timestamp}).")
    return 0


def cmd_menus(args) -> int:
    gen = MenuGenerator()
    if args.clean:
        gen.cleanup(restart=not args.no_restart)
        print("Removed ViciCat extension and favorites from Vicinae.")
        return 0

    parser = DesktopFileParser()
    entries = parser.scan_all()

    categorized: Dict[str, str] = {}
    uncategorized_count = 0
    for filename, entry in entries.items():
        cat = _map_desktop_category(entry)
        if cat:
            categorized[filename] = cat
        else:
            uncategorized_count += 1

    if not categorized:
        logger.error("No categorized applications found. Run 'vicicat categorize --yes' first.")
        return 1

    if uncategorized_count > 0 and not args.quiet:
        logger.info(
            f"{uncategorized_count} uncategorized app(s) skipped (run 'vicicat categorize -y' to classify)."
        )

    if gen.generate(
        categorized,
        entries,
        dry_run=args.dry_run,
        restart=not args.no_restart and not args.dry_run,
    ):
        if not args.quiet and not args.dry_run:
            print(f"Generated Vicinae extension at {VICINAE_EXT_DIR}")
        return 0
    return 1


def cmd_auto(args) -> int:
    """Automated non-interactive categorize + menu sync with loop guard."""
    parser = DesktopFileParser()
    entries = parser.scan_all()
    fp = _compute_fingerprint(entries)

    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            state = {}

    if not args.force and state.get("fingerprint") == fp and (VICINAE_EXT_DIR / "package.json").exists():
        return 0

    uncategorized = {f: e for f, e in entries.items() if not _map_desktop_category(e)}
    if uncategorized:
        try:
            categorizer = AppCategorizer(provider=args.provider, model=args.model)
            categorization = categorizer.categorize(uncategorized)
            if categorization:
                writer = DesktopFileWriter(dry_run=False)
                writer.apply_categorization(uncategorized, categorization)
                entries = parser.scan_all()
                fp = _compute_fingerprint(entries)
        except Exception as e:
            logger.warning(f"Auto-categorization skipped ({e}); syncing existing categories.")

    # Save fingerprint before restarting/finishing so path watcher does not loop
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"fingerprint": fp}), encoding="utf-8")

    categorized = {
        f: _map_desktop_category(e) for f, e in entries.items() if _map_desktop_category(e)
    }
    if categorized:
        gen = MenuGenerator()
        gen.generate(categorized, entries, dry_run=False, restart=True)
    return 0


def cmd_service(args) -> int:
    systemd_dir = XDG_CONFIG_HOME / "systemd/user"
    systemd_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = Path(__file__).resolve().parent
    vicicat_bin = repo_dir / "vicicat"

    units = {
        "vicicat-watcher.path": f"""[Unit]
Description=Watch application directories for new games/apps (ViciCat)

[Path]
PathChanged=/usr/share/applications
PathChanged=%h/.local/share/applications
Unit=vicicat-sync.service

[Install]
WantedBy=default.target
""",
        "vicicat-sync.timer": f"""[Unit]
Description=Periodic ViciCat category & usage sync timer

[Timer]
OnBootSec=2min
OnUnitActiveSec=30min
Persistent=true
Unit=vicicat-sync.service

[Install]
WantedBy=timers.target
""",
        "vicicat-sync.service": f"""[Unit]
Description=ViciCat automatic app categorizer and Vicinae group generator

[Service]
Type=oneshot
ExecStart={vicicat_bin} auto
""",
    }

    if args.action == "install":
        for name, content in units.items():
            (systemd_dir / name).write_text(content, encoding="utf-8")
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(
            ["systemctl", "--user", "enable", "--now", "vicicat-watcher.path", "vicicat-sync.timer"],
            check=True,
        )
        print("Installed and enabled vicicat-watcher.path and vicicat-sync.timer.")
        return 0
    elif args.action == "uninstall":
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", "vicicat-watcher.path", "vicicat-sync.timer"],
            check=False,
        )
        print("Disabled vicicat systemd units.")
        return 0
    else:
        subprocess.run(
            ["systemctl", "--user", "status", "vicicat-watcher.path", "vicicat-sync.timer", "--no-pager"],
            check=False,
        )
        return 0


def cmd_rollback(args) -> int:
    writer = DesktopFileWriter()
    if args.list:
        for i, b in enumerate(writer.list_backups(), 1):
            print(f"  {i}. {b}")
        return 0
    return 0 if writer.rollback(args.timestamp) else 1


def cmd_categories(_args) -> int:
    for i, c in enumerate(DEFAULT_CATEGORIES, 1):
        print(f"  {i}. {c}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ViciCat - Automated app & game groups for Vicinae with Local/Cloud LLM"
    )
    sub = parser.add_subparsers(dest="command")

    p_scan = sub.add_parser("scan", help="Scan .desktop applications")
    p_scan.add_argument("-u", "--uncategorized", action="store_true")
    p_scan.add_argument("-c", "--category", type=str)
    p_scan.add_argument("-l", "--limit", type=int)

    p_cat = sub.add_parser("categorize", help="Categorize apps via Local or Cloud LLM")
    p_cat.add_argument("--dry-run", action="store_true")
    p_cat.add_argument("-y", "--yes", "--apply", action="store_true", dest="yes")
    p_cat.add_argument("-r", "--recategorize", action="store_true")
    p_cat.add_argument("-l", "--limit", type=int)
    p_cat.add_argument("-b", "--batch-size", type=int, default=30)
    p_cat.add_argument("--provider", choices=["auto", "local", "cloud"], default=PROVIDER)
    p_cat.add_argument("--model", type=str, default=None)
    p_cat.add_argument("--local-url", type=str, default="http://127.0.0.1:11434")

    p_menu = sub.add_parser("menus", help="Generate native Vicinae category extension")
    p_menu.add_argument("--dry-run", action="store_true")
    p_menu.add_argument("--clean", action="store_true")
    p_menu.add_argument("-q", "--quiet", action="store_true")
    p_menu.add_argument("--no-restart", action="store_true")

    p_auto = sub.add_parser("auto", help="Non-interactive categorize + menu sync")
    p_auto.add_argument("-f", "--force", action="store_true")
    p_auto.add_argument("--provider", choices=["auto", "local", "cloud"], default=PROVIDER)
    p_auto.add_argument("--model", type=str, default=None)

    p_svc = sub.add_parser("service", help="Manage systemd user watcher & timer")
    p_svc.add_argument("action", choices=["install", "uninstall", "status"], default="status", nargs="?")

    p_rb = sub.add_parser("rollback", help="Rollback .desktop file changes")
    p_rb.add_argument("-l", "--list", action="store_true")
    p_rb.add_argument("-t", "--timestamp", type=str)

    sub.add_parser("categories", help="List supported categories")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    dispatch = {
        "scan": cmd_scan,
        "categorize": cmd_categorize,
        "menus": cmd_menus,
        "auto": cmd_auto,
        "service": cmd_service,
        "rollback": cmd_rollback,
        "categories": cmd_categories,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
