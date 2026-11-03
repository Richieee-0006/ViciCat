import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from config import (
    DEFAULT_CATEGORIES,
    VICINAE_CONFIG_PATH,
    VICINAE_EXT_AUTHOR,
    VICINAE_EXT_DIR,
    VICINAE_EXT_ID,
    VICINAE_METADATA_PATH,
    XDG_DATA_HOME,
)
from parser import DesktopEntry

logger = logging.getLogger(__name__)

CATEGORY_META = {
    "Games": {"icon": "GameController", "color": "#cba6f7", "svg_symbol": "gamepad"},
    "Development": {"icon": "CodeBlock", "color": "#89b4fa", "svg_symbol": "code"},
    "Browser": {"icon": "Globe01", "color": "#74c7ec", "svg_symbol": "globe"},
    "Internet": {"icon": "Globe01", "color": "#89dceb", "svg_symbol": "network"},
    "Media": {"icon": "PlayFilled", "color": "#f38ba8", "svg_symbol": "play"},
    "Graphics": {"icon": "Brush", "color": "#fab387", "svg_symbol": "brush"},
    "Office": {"icon": "BlankDocument", "color": "#f9e2af", "svg_symbol": "doc"},
    "Education": {"icon": "Book", "color": "#a6e3a1", "svg_symbol": "book"},
    "Utility": {"icon": "WrenchScrewdriver", "color": "#94e2d5", "svg_symbol": "wrench"},
    "System": {"icon": "Terminal", "color": "#b4befe", "svg_symbol": "terminal"},
    "Settings": {"icon": "Cog", "color": "#cdd6f4", "svg_symbol": "cog"},
}

SVG_PATHS = {
    "apps": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "gamepad": '<rect x="2" y="6" width="20" height="12" rx="6"/><path d="M6 12h4M8 10v4"/><circle cx="15" cy="11" r="1"/><circle cx="17" cy="13" r="1"/>',
    "code": '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "network": '<circle cx="12" cy="5" r="3"/><circle cx="5" cy="19" r="3"/><circle cx="19" cy="19" r="3"/><line x1="10.5" y1="7.5" x2="6.5" y2="16.5"/><line x1="13.5" y1="7.5" x2="17.5" y2="16.5"/>',
    "play": '<polygon points="5 3 19 12 5 21 5 3"/>',
    "brush": '<path d="M18.37 2.63 14 7l-1.59-1.59a2 2 0 0 0-2.82 0L8 7l9 9 1.59-1.59a2 2 0 0 0 0-2.82L17 10l4.37-4.37a2.12 2.12 0 1 0-3-3Z"/><path d="M9 8c-2 3-4 3.5-7 4l8 10c2-1 6-5 6-7"/>',
    "doc": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
    "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
    "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    "terminal": '<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>',
    "cog": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
}

SHARED_JS_CODE = r"""
"use strict";
const api = require("@vicinae/api");
const jsx = require("react/jsx-runtime");
const react = require("react");
const fs = require("node:fs");
const path = require("node:path");
const child_process = require("node:child_process");

const DATA_FILE = path.join(__dirname, "categories.json");
const METADATA_FILE = path.join(
  process.env.XDG_DATA_HOME || path.join(process.env.HOME || "", ".local/share"),
  "vicinae/metadata.json"
);

function loadData() {
  try {
    return JSON.parse(fs.readFileSync(DATA_FILE, "utf8"));
  } catch {
    return { categoriesOrder: [], appsByCategory: {} };
  }
}

function loadUsage() {
  try {
    const raw = JSON.parse(fs.readFileSync(METADATA_FILE, "utf8"));
    return raw.visited || {};
  } catch {
    return {};
  }
}

function sortApps(apps, visited) {
  return [...apps].sort((a, b) => {
    const uA = visited["applications:" + a.id] || { visit_count: 0, last_visited_at: 0 };
    const uB = visited["applications:" + b.id] || { visit_count: 0, last_visited_at: 0 };
    if ((uB.visit_count || 0) !== (uA.visit_count || 0)) {
      return (uB.visit_count || 0) - (uA.visit_count || 0);
    }
    if ((uB.last_visited_at || 0) !== (uA.last_visited_at || 0)) {
      return (uB.last_visited_at || 0) - (uA.last_visited_at || 0);
    }
    return a.name.localeCompare(b.name);
  });
}

async function launchApp(app, newInstance = false) {
  await api.closeMainWindow();
  const args = ["app", "launch"];
  if (newInstance) args.push("--new");
  args.push(app.id);
  const child = child_process.spawn("vicinae", args, {
    detached: true,
    stdio: "ignore",
  });
  child.on("error", () => {
    if (app.exec) {
      child_process.spawn("sh", ["-c", app.exec], {
        detached: true,
        stdio: "ignore",
      }).unref();
    }
  });
  child.unref();
}

function renderAppItem(app, visited, fallbackIcon) {
  const stats = visited["applications:" + app.id];
  const accessories = [];
  if (app.category) {
    accessories.push({ tag: { value: app.category, color: api.Color.Blue } });
  }
  if (stats && stats.visit_count > 0) {
    accessories.push({ text: `${stats.visit_count}x` });
  }
  const icon = app.iconPath || api.Icon[fallbackIcon] || api.Icon.AppWindow;

  return jsx.jsx(
    api.List.Item,
    {
      title: app.name,
      subtitle: app.comment || "",
      icon: icon,
      keywords: [app.id, app.category || "", app.genericName || ""].filter(Boolean),
      accessories: accessories,
      actions: jsx.jsxs(api.ActionPanel, {
        children: [
          jsx.jsx(api.Action, {
            title: "Launch Application",
            icon: api.Icon.Play,
            onAction: () => launchApp(app, false),
          }),
          jsx.jsx(api.Action, {
            title: "Launch New Instance",
            icon: api.Icon.Plus,
            shortcut: api.Keyboard.Shortcut.Common.New,
            onAction: () => launchApp(app, true),
          }),
          jsx.jsx(api.Action.CopyToClipboard, {
            title: "Copy Desktop File Name",
            content: app.filename,
            shortcut: api.Keyboard.Shortcut.Common.CopyName,
          }),
        ],
      }),
    },
    app.filename
  );
}

function createCategoryView(categoryName, fallbackIcon) {
  return function CategoryCommand() {
    const [{ apps, visited }] = react.useState(() => {
      const data = loadData();
      const vis = loadUsage();
      const rawApps = (data.appsByCategory && data.appsByCategory[categoryName]) || [];
      return { apps: sortApps(rawApps, vis), visited: vis };
    });

    return jsx.jsx(api.List, {
      searchBarPlaceholder: `Search ${categoryName}...`,
      navigationTitle: categoryName,
      children:
        apps.length === 0
          ? jsx.jsx(api.List.EmptyView, {
              icon: api.Icon[fallbackIcon] || api.Icon.AppWindow,
              title: `No applications in ${categoryName}`,
              description: "Run 'vicicat categorize && vicicat menus' to update.",
            })
          : jsx.jsx(api.List.Section, {
              title: categoryName,
              subtitle: `${apps.length} apps`,
              children: apps.map((app) => renderAppItem(app, visited, fallbackIcon)),
            }),
    });
  };
}

function createAllCategoriesView() {
  return function AllCategoriesCommand() {
    const [selectedCat, setSelectedCat] = react.useState("all");
    const [{ data, visited }] = react.useState(() => ({
      data: loadData(),
      visited: loadUsage(),
    }));

    const categories = data.categoriesOrder || [];
    const visibleCategories =
      selectedCat === "all" ? categories : categories.filter((c) => c === selectedCat);

    const dropdown = jsx.jsxs(api.List.Dropdown, {
      tooltip: "Filter Category",
      value: selectedCat,
      onChange: setSelectedCat,
      children: [
        jsx.jsx(api.List.Dropdown.Item, { title: "All Categories", value: "all" }, "all"),
        categories.map((cat) => {
          const count = ((data.appsByCategory && data.appsByCategory[cat]) || []).length;
          return jsx.jsx(
            api.List.Dropdown.Item,
            { title: `${cat} (${count})`, value: cat },
            cat
          );
        }),
      ],
    });

    return jsx.jsx(api.List, {
      searchBarPlaceholder: "Search applications across categories...",
      navigationTitle: "Applications by Category",
      searchBarAccessory: dropdown,
      children: visibleCategories.map((cat) => {
        const apps = sortApps((data.appsByCategory && data.appsByCategory[cat]) || [], visited);
        const fallbackIcon = (data.categoryIcons && data.categoryIcons[cat]) || "AppWindow";
        return jsx.jsx(
          api.List.Section,
          {
            title: cat,
            subtitle: `${apps.length} apps`,
            children: apps.map((app) =>
              renderAppItem({ ...app, category: cat }, visited, fallbackIcon)
            ),
          },
          cat
        );
      }),
    });
  };
}

module.exports = { createCategoryView, createAllCategoriesView };
""".lstrip()


class MenuGenerator:
    """Generates native Vicinae extension and updates Vicinae settings.json."""

    SKIP_DESKTOP_CATEGORIES = {"X-LSP-Plugins"}
    SKIP_APP_NAMES = {"Steamworks SDK Redist", "Steamworks Common Redistributables", "Proton"}

    def __init__(self):
        self._icon_cache: Dict[str, Optional[str]] = {}
        self._icon_search_dirs = self._build_icon_search_dirs()

    def _get_disabled_apps(self) -> set:
        disabled = set()
        if not VICINAE_CONFIG_PATH.exists():
            return disabled
        try:
            raw = self._strip_jsonc_comments(VICINAE_CONFIG_PATH.read_text(encoding="utf-8"))
            cfg = json.loads(raw)
            eps = cfg.get("providers", {}).get("applications", {}).get("entrypoints", {})
            for app_id, meta in eps.items():
                if isinstance(meta, dict) and meta.get("enabled") is False:
                    disabled.add(app_id)
        except Exception:
            pass
        return disabled

    def _build_icon_search_dirs(self) -> List[Path]:
        dirs = []
        bases = [
            XDG_DATA_HOME / "icons",
            Path.home() / ".icons",
            Path("/usr/share/icons"),
        ]
        themes = ["hicolor", "breeze-dark", "breeze", "Adwaita", "Papirus-Dark", "Papirus"]
        sizes = ["scalable", "256x256", "128x128", "64x64", "48x48", "32x32", "apps"]
        for base in bases:
            if not base.exists():
                continue
            for theme in themes:
                tdir = base / theme
                if not tdir.exists():
                    continue
                for size in sizes:
                    for sub in (tdir / size / "apps", tdir / "apps" / size, tdir / size):
                        if sub.is_dir():
                            dirs.append(sub)
        if Path("/usr/share/pixmaps").is_dir():
            dirs.append(Path("/usr/share/pixmaps"))
        return dirs

    def _resolve_icon_path(self, icon_name: str) -> Optional[str]:
        if not icon_name:
            return None
        if icon_name in self._icon_cache:
            return self._icon_cache[icon_name]

        p = Path(icon_name)
        if p.is_absolute() and p.exists():
            self._icon_cache[icon_name] = str(p)
            return str(p)

        for d in self._icon_search_dirs:
            for ext in (".svg", ".png", ".xpm", ""):
                candidate = d / f"{icon_name}{ext}"
                if candidate.is_file():
                    self._icon_cache[icon_name] = str(candidate)
                    return str(candidate)

        self._icon_cache[icon_name] = None
        return None

    def _sanitize_slug(self, category: str) -> str:
        return category.lower().replace(" ", "-")

    def _clean_exec(self, exec_cmd: str) -> str:
        for code in ["%u", "%U", "%f", "%F", "%d", "%D", "%n", "%N", "%i", "%c", "%k", "%v", "%m"]:
            exec_cmd = exec_cmd.replace(code, "")
        return exec_cmd.strip()

    def get_usage_data(self) -> Dict[str, Dict]:
        """Load app visit counts directly from Vicinae's metadata.json."""
        usage: Dict[str, Dict] = {}
        if not VICINAE_METADATA_PATH.exists():
            return usage
        try:
            raw = json.loads(VICINAE_METADATA_PATH.read_text(encoding="utf-8"))
            visited = raw.get("visited", {})
            for key, stats in visited.items():
                if key.startswith("applications:"):
                    app_id = key.split("applications:", 1)[1]
                    usage[f"{app_id}.desktop"] = {
                        "count": int(stats.get("visit_count", 0)),
                        "last_used": int(stats.get("last_visited_at", 0)),
                    }
        except Exception as e:
            logger.debug(f"Could not read Vicinae metadata.json: {e}")
        return usage

    def _write_svg_icon(self, path: Path, symbol_key: str, color: str) -> None:
        inner = SVG_PATHS.get(symbol_key, SVG_PATHS["apps"])
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" '
            f'viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            f"{inner}</svg>\n"
        )
        path.write_text(svg, encoding="utf-8")

    def generate(
        self,
        categorized: Dict[str, str],
        entries: Dict[str, DesktopEntry],
        dry_run: bool = False,
        restart: bool = True,
    ) -> bool:
        disabled_apps = self._get_disabled_apps()
        by_category: Dict[str, List[DesktopEntry]] = {}
        for filename, category in categorized.items():
            entry = entries.get(filename)
            if not entry:
                continue
            if entry.app_id in disabled_apps:
                continue
            if any(c in self.SKIP_DESKTOP_CATEGORIES for c in entry.categories):
                continue
            if any(skip.lower() in entry.name.lower() for skip in self.SKIP_APP_NAMES):
                continue
            by_category.setdefault(category, []).append(entry)

        usage_data = self.get_usage_data()

        def get_count(filename: str) -> int:
            return usage_data.get(filename, {}).get("count", 0)

        for cat in by_category:
            by_category[cat].sort(key=lambda e: (-get_count(e.filename), e.name.lower()))
            # Deduplicate identical display names within same category (keep highest-usage entry)
            seen_names = set()
            deduped = []
            for e in by_category[cat]:
                norm = e.name.strip().lower()
                if norm not in seen_names:
                    seen_names.add(norm)
                    deduped.append(e)
            by_category[cat] = deduped

        category_list = list(by_category.keys())
        category_list.sort(
            key=lambda c: (
                -sum(get_count(e.filename) for e in by_category[c]),
                DEFAULT_CATEGORIES.index(c) if c in DEFAULT_CATEGORIES else len(DEFAULT_CATEGORIES),
            )
        )

        if dry_run:
            print(f"\n[DRY RUN] Would generate Vicinae extension in: {VICINAE_EXT_DIR}")
            for cat in category_list:
                apps = by_category[cat]
                total_u = sum(get_count(e.filename) for e in apps)
                names = ", ".join(e.name for e in apps[:5])
                if len(apps) > 5:
                    names += f", ... (+{len(apps) - 5})"
                print(f"  - {cat}: {len(apps)} apps (usage: {total_u}) [{names}]")
            return True

        assets_dir = VICINAE_EXT_DIR / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        # Write extension icon + category SVG icons
        self._write_svg_icon(assets_dir / "apps.svg", "apps", "#cba6f7")

        commands_manifest = [
            {
                "name": "apps",
                "title": "Apps (Categories)",
                "subtitle": "Browse all categorized applications",
                "description": "Browse applications grouped by category",
                "icon": "apps.svg",
                "mode": "view",
            }
        ]

        apps_by_category_payload: Dict[str, List[Dict]] = {}
        category_icons_payload: Dict[str, str] = {}

        for cat in category_list:
            slug = self._sanitize_slug(cat)
            meta = CATEGORY_META.get(
                cat, {"icon": "AppWindow", "color": "#cdd6f4", "svg_symbol": "apps"}
            )
            icon_filename = f"{slug}.svg"
            self._write_svg_icon(assets_dir / icon_filename, meta["svg_symbol"], meta["color"])
            category_icons_payload[cat] = meta["icon"]

            app_entries = by_category[cat]
            commands_manifest.append(
                {
                    "name": slug,
                    "title": cat,
                    "subtitle": f"{len(app_entries)} applications",
                    "description": f"Launch {cat} applications",
                    "icon": icon_filename,
                    "mode": "view",
                }
            )

            apps_by_category_payload[cat] = [
                {
                    "id": e.app_id,
                    "filename": e.filename,
                    "name": e.name,
                    "comment": e.comment,
                    "genericName": e.generic_name,
                    "exec": self._clean_exec(e.exec_cmd),
                    "iconPath": self._resolve_icon_path(e.icon),
                }
                for e in app_entries
            ]

            # Write entrypoint JS for this category
            cmd_js = (
                '"use strict";\n'
                'const { createCategoryView } = require("./shared.js");\n'
                f'module.exports = {{ default: createCategoryView({json.dumps(cat)}, {json.dumps(meta["icon"])}) }};\n'
            )
            (VICINAE_EXT_DIR / f"{slug}.js").write_text(cmd_js, encoding="utf-8")

        # Write apps.js & shared.js & categories.json & package.json
        (VICINAE_EXT_DIR / "shared.js").write_text(SHARED_JS_CODE, encoding="utf-8")
        (VICINAE_EXT_DIR / "apps.js").write_text(
            '"use strict";\nconst { createAllCategoriesView } = require("./shared.js");\nmodule.exports = { default: createAllCategoriesView() };\n',
            encoding="utf-8",
        )
        (VICINAE_EXT_DIR / "categories.json").write_text(
            json.dumps(
                {
                    "categoriesOrder": category_list,
                    "categoryIcons": category_icons_payload,
                    "appsByCategory": apps_by_category_payload,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        pkg_json = {
            "$schema": "https://raw.githubusercontent.com/vicinaehq/vicinae/refs/heads/main/extra/schemas/extension.json",
            "name": "vicicat",
            "title": "ViciCat Categories",
            "description": "Automated application & game category groups for Vicinae.",
            "categories": ["Productivity", "Applications"],
            "license": "MIT",
            "author": VICINAE_EXT_AUTHOR,
            "icon": "apps.svg",
            "commands": commands_manifest,
        }
        (VICINAE_EXT_DIR / "package.json").write_text(
            json.dumps(pkg_json, indent=2), encoding="utf-8"
        )

        self.update_vicinae_config(category_list)
        if restart:
            self.restart_vicinae()
        return True

    def _strip_jsonc_comments(self, text: str) -> str:
        out = []
        for line in text.splitlines():
            if line.lstrip().startswith("//"):
                continue
            out.append(line)
        return "\n".join(out)

    def update_vicinae_config(self, categories: List[str]) -> bool:
        """Pin all non-empty category commands to favorites in ~/.config/vicinae/settings.json."""
        if not VICINAE_CONFIG_PATH.exists():
            logger.warning(f"Vicinae config not found at {VICINAE_CONFIG_PATH}")
            return False

        try:
            shutil.copy2(VICINAE_CONFIG_PATH, VICINAE_CONFIG_PATH.with_suffix(".json.bak"))
            raw_text = VICINAE_CONFIG_PATH.read_text(encoding="utf-8")
            config = json.loads(self._strip_jsonc_comments(raw_text))

            prefix = f"@{VICINAE_EXT_AUTHOR}/{VICINAE_EXT_ID}:"
            existing_favs = [
                f for f in config.get("favorites", []) if not str(f).startswith(prefix)
            ]
            cat_favs = [f"{prefix}{self._sanitize_slug(c)}" for c in categories]
            cat_favs.append(f"{prefix}apps")

            config["favorites"] = cat_favs + existing_favs
            VICINAE_CONFIG_PATH.write_text(json.dumps(config, indent=3) + "\n", encoding="utf-8")
            logger.info(f"Updated favorites in {VICINAE_CONFIG_PATH}")
            return True
        except Exception as e:
            logger.error(f"Failed to update Vicinae config: {e}")
            return False

    def cleanup(self, restart: bool = True) -> bool:
        try:
            if VICINAE_EXT_DIR.exists():
                for f in VICINAE_EXT_DIR.glob("*.js"):
                    f.unlink()
                for f in VICINAE_EXT_DIR.glob("*.json"):
                    f.unlink()
                assets = VICINAE_EXT_DIR / "assets"
                if assets.exists():
                    for f in assets.glob("*"):
                        f.unlink()
                    assets.rmdir()
                VICINAE_EXT_DIR.rmdir()

            if VICINAE_CONFIG_PATH.exists():
                shutil.copy2(VICINAE_CONFIG_PATH, VICINAE_CONFIG_PATH.with_suffix(".json.bak"))
                raw_text = VICINAE_CONFIG_PATH.read_text(encoding="utf-8")
                config = json.loads(self._strip_jsonc_comments(raw_text))
                prefix = f"@{VICINAE_EXT_AUTHOR}/{VICINAE_EXT_ID}:"
                if "favorites" in config:
                    config["favorites"] = [
                        f for f in config["favorites"] if not str(f).startswith(prefix)
                    ]
                VICINAE_CONFIG_PATH.write_text(
                    json.dumps(config, indent=3) + "\n", encoding="utf-8"
                )
            if restart:
                self.restart_vicinae()
            return True
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return False

    def restart_vicinae(self) -> None:
        try:
            res = subprocess.run(
                ["systemctl", "--user", "is-active", "vicinae.service"],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                subprocess.run(["systemctl", "--user", "restart", "vicinae.service"], check=False)
                return
            subprocess.Popen(
                ["vicinae", "server"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as e:
            logger.debug(f"Could not restart vicinae: {e}")
