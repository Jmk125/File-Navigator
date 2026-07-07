"""Persisted user preferences: theme, hotkeys, splitter layout."""
from __future__ import annotations

from . import storage

SETTINGS_FILE = storage.DATA_DIR / "settings.json"

THEME_NAMES = ("dark", "medium", "light")

# The 1-9 folder-jump keys aren't listed here - their "binding" is the
# folder's position, which you already control by dragging tiles to reorder.
DEFAULT_HOTKEYS = {
    "back_out": "Esc",
    "navigate_back": "Backspace",
    "navigate_up": "Up",
    "add_quick_access": "+",
    "cycle_selection": "Tab",
}

HOTKEY_LABELS = {
    "back_out": "Back out (clear filter, then close browser, then deselect project)",
    "navigate_back": "Navigate back",
    "navigate_up": "Navigate up one folder",
    "add_quick_access": "Add current folder to quick access",
    "cycle_selection": "Cycle file/folder selector (Shift+ reverses)",
}

DEFAULT_SETTINGS = {
    "theme": "dark",
    "hotkeys": dict(DEFAULT_HOTKEYS),
    "splitter_sizes": [300, 300],
}


def load_settings() -> dict:
    data = storage.read_json(SETTINGS_FILE, {})
    merged = {
        "theme": DEFAULT_SETTINGS["theme"],
        "hotkeys": dict(DEFAULT_HOTKEYS),
        "splitter_sizes": list(DEFAULT_SETTINGS["splitter_sizes"]),
    }
    if isinstance(data, dict):
        if data.get("theme") in THEME_NAMES:
            merged["theme"] = data["theme"]
        sizes = data.get("splitter_sizes")
        if isinstance(sizes, list) and len(sizes) == 2 and all(isinstance(n, (int, float)) for n in sizes):
            merged["splitter_sizes"] = [int(sizes[0]), int(sizes[1])]
        hotkeys = data.get("hotkeys")
        if isinstance(hotkeys, dict):
            for action in DEFAULT_HOTKEYS:
                if action in hotkeys and isinstance(hotkeys[action], str):
                    merged["hotkeys"][action] = hotkeys[action]
    return merged


def save_settings(settings: dict) -> None:
    storage.write_json(SETTINGS_FILE, settings)
