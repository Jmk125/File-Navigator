"""
Project Navigator - local desktop version

Runs your existing Project Navigator UI inside a native desktop window using pywebview,
with a small local Flask backend for browsing folders, opening files, and storing
projects/recent files in JSON instead of browser localStorage.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
from waitress import serve

try:
    import webview
except ImportError:  # lets app.py still be used with --browser if pywebview isn't installed
    webview = None

APP_NAME = "Project Navigator"
HOST = "127.0.0.1"
PORT = 3050
BASE_DIR = Path(__file__).resolve().parent


def app_data_dir() -> Path:
    """Return a writable user-specific data folder."""
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

flask_app = Flask(__name__)


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


def normalize_path(input_path: str) -> str:
    # Preserve UNC paths on Windows. The front end already uses Windows paths heavily.
    return os.path.normpath(input_path.strip())


def open_path(path_to_open: str) -> None:
    system = platform.system()
    if system == "Windows":
        os.startfile(path_to_open)  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.Popen(["open", path_to_open])
    else:
        subprocess.Popen(["xdg-open", path_to_open])


@flask_app.get("/")
def index() -> Any:
    return send_from_directory(BASE_DIR, "index.html")


@flask_app.get("/api/projects")
def get_projects() -> Any:
    return jsonify(read_json(PROJECTS_FILE, []))


@flask_app.post("/api/projects")
def set_projects() -> Any:
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        return jsonify(error="Expected a JSON array of projects"), 400
    write_json(PROJECTS_FILE, data)
    return jsonify(success=True)


@flask_app.get("/api/recent-files")
def get_recent_files() -> Any:
    return jsonify(read_json(RECENTS_FILE, {}))


@flask_app.post("/api/recent-files")
def set_recent_files() -> Any:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Expected a JSON object of recent files"), 400
    write_json(RECENTS_FILE, data)
    return jsonify(success=True)


@flask_app.post("/api/browse")
def browse() -> Any:
    data = request.get_json(silent=True) or {}
    dir_path = data.get("dirPath")
    if not dir_path:
        return jsonify(error="Directory path required"), 400

    normalized = normalize_path(str(dir_path))
    if not os.path.isdir(normalized):
        return jsonify(error="Folder not found", details=normalized), 404

    items = []
    try:
        with os.scandir(normalized) as entries:
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
                    # Skip inaccessible files rather than failing the entire folder.
                    continue
    except OSError as exc:
        return jsonify(error="Failed to read directory", details=str(exc)), 500

    items.sort(key=lambda item: (not item["isDirectory"], item["name"].lower()))
    return jsonify(path=normalized, items=items)


@flask_app.post("/api/open")
def open_file() -> Any:
    data = request.get_json(silent=True) or {}
    file_path = data.get("filePath")
    if not file_path:
        return jsonify(error="File path required"), 400

    normalized = normalize_path(str(file_path))
    if not os.path.exists(normalized):
        return jsonify(error="File not found", details=normalized), 404

    try:
        open_path(normalized)
        return jsonify(success=True, message="File opened")
    except Exception as exc:
        return jsonify(error="Failed to open file", details=str(exc)), 500


@flask_app.post("/api/open-folder")
def open_folder() -> Any:
    data = request.get_json(silent=True) or {}
    folder_path = data.get("folderPath")
    if not folder_path:
        return jsonify(error="Folder path required"), 400

    normalized = normalize_path(str(folder_path))
    if not os.path.isdir(normalized):
        return jsonify(error="Folder not found", details=normalized), 404

    try:
        open_path(normalized)
        return jsonify(success=True, message="Folder opened")
    except Exception as exc:
        return jsonify(error="Failed to open folder", details=str(exc)), 500


def run_server() -> None:
    serve(flask_app, host=HOST, port=PORT, threads=8)


def main() -> None:
    url = f"http://{HOST}:{PORT}"
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Let the server bind before opening the UI.
    time.sleep(0.5)

    if "--browser" in sys.argv or webview is None:
        webbrowser.open(url)
        print(f"{APP_NAME} running at {url}")
        print(f"Data folder: {DATA_DIR}")
        while True:
            time.sleep(3600)

    window = webview.create_window(APP_NAME, url, width=1250, height=850, min_size=(900, 600))
    webview.start()


if __name__ == "__main__":
    main()
