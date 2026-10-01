"""Filesystem + JSON persistence helpers. No GUI code lives here."""
from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any


def app_data_dir() -> Path:
    """Return a writable user-specific data folder, same layout as the old web version."""
    if platform.system() == "Windows":
        root = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        folder = Path(root) / "ProjectNavigator"
    elif platform.system() == "Darwin":
        folder = Path.home() / "Library" / "Application Support" / "ProjectNavigator"
    else:
        folder = Path.home() / ".project-navigator"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


DATA_DIR = app_data_dir()
PROJECTS_FILE = DATA_DIR / "projects.json"
RECENTS_FILE = DATA_DIR / "recent_files.json"


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # If a file gets corrupted, don't crash the app. Keep the file for manual recovery.
        pass
    return default


def write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_projects() -> list:
    return read_json(PROJECTS_FILE, [])


def save_projects(projects: list) -> None:
    write_json(PROJECTS_FILE, projects)


def load_recent_files() -> dict:
    return read_json(RECENTS_FILE, {})


def save_recent_files(recent_files: dict) -> None:
    write_json(RECENTS_FILE, recent_files)


def normalize_path(input_path: str) -> str:
    # Preserve UNC paths on Windows.
    return os.path.normpath(input_path.strip())


def parent_path(path: str) -> str | None:
    """Return the parent directory of path, or None if already at a root."""
    stripped = path.rstrip("\\/")
    if len(stripped) == 2 and stripped[1] == ":":
        return None  # already a drive root such as "C:\\"
    parent = os.path.dirname(stripped)
    if not parent or parent == stripped or parent == path:
        return None
    if len(parent) == 2 and parent[1] == ":":
        # "C:" alone means "current directory on C:"; the drive root is "C:\\".
        parent += os.sep
    return parent


def ancestors(path: str) -> list[str]:
    """Return [root, ..., path] - every folder from the drive/share root down to path."""
    chain = [path]
    while True:
        parent = parent_path(chain[0])
        if not parent or parent in chain:
            break
        chain.insert(0, parent)
    return chain


def list_drives() -> list[str]:
    """Return root paths of local/mapped drives (Windows letters; mount points elsewhere)."""
    if platform.system() == "Windows":
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()  # type: ignore[attr-defined]
        return [f"{chr(65 + i)}:\\" for i in range(26) if mask & (1 << i)]
    if platform.system() == "Darwin":
        volumes = Path("/Volumes")
        return ["/"] + (sorted(str(p) for p in volumes.iterdir()) if volumes.is_dir() else [])
    return ["/"]


def list_dir(dir_path: str) -> list[dict]:
    """List directory contents, directories first, alphabetical. Raises OSError on failure."""
    items = []
    with os.scandir(dir_path) as entries:
        for entry in entries:
            try:
                stat = entry.stat(follow_symlinks=False)
                items.append({
                    "name": entry.name,
                    "path": entry.path,
                    "isDirectory": entry.is_dir(follow_symlinks=False),
                    "size": stat.st_size,
                    "modified": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
                })
            except OSError:
                continue
    items.sort(key=lambda item: (not item["isDirectory"], item["name"].lower()))
    return items


def open_path(path_to_open: str) -> None:
    system = platform.system()
    if system == "Windows":
        os.startfile(path_to_open)  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.Popen(["open", path_to_open])
    else:
        subprocess.Popen(["xdg-open", path_to_open])
