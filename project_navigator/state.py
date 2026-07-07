"""In-memory application state and the operations that mutate it."""
from __future__ import annotations

import time
import uuid
from typing import Optional

from . import storage

MAX_RECENT_FILES = 10


class NavigatorState:
    def __init__(self) -> None:
        self.projects: list[dict] = []
        self.recent_files: dict[str, list[dict]] = {}
        self.selected_project_id: Optional[str] = None
        self.browse_path: dict[str, str] = {}
        self.browse_history: dict[str, list[str]] = {}
        self.edit_mode: bool = False

    # ---- persistence ----------------------------------------------------
    def load(self) -> None:
        self.projects = storage.load_projects()
        self.recent_files = storage.load_recent_files()

    def save_projects(self) -> None:
        storage.save_projects(self.projects)

    def save_recent_files(self) -> None:
        storage.save_recent_files(self.recent_files)

    # ---- project lookups -------------------------------------------------
    def find_project(self, project_id: str) -> Optional[dict]:
        return next((p for p in self.projects if p["id"] == project_id), None)

    @property
    def selected_project(self) -> Optional[dict]:
        if self.selected_project_id is None:
            return None
        return self.find_project(self.selected_project_id)

    # ---- project CRUD -----------------------------------------------------
    def add_project(self, name: str, color: str, quick_folders: list[dict]) -> dict:
        project = {
            "id": uuid.uuid4().hex,
            "name": name,
            "color": color,
            "quickFolders": quick_folders,
        }
        self.projects.append(project)
        self.save_projects()
        return project

    def update_project(self, project_id: str, name: str, color: str, quick_folders: list[dict]) -> None:
        project = self.find_project(project_id)
        if not project:
            return
        project["name"] = name
        project["color"] = color
        project["quickFolders"] = quick_folders
        self.save_projects()

    def duplicate_project(self, project_id: str, new_name: str) -> Optional[dict]:
        project = self.find_project(project_id)
        if not project:
            return None
        return self.add_project(new_name, project["color"], [dict(f) for f in project.get("quickFolders", [])])

    def delete_project(self, project_id: str) -> None:
        self.projects = [p for p in self.projects if p["id"] != project_id]
        self.browse_path.pop(project_id, None)
        self.browse_history.pop(project_id, None)
        if self.selected_project_id == project_id:
            self.selected_project_id = None
        self.save_projects()

    def reorder_projects(self, new_order_ids: list[str]) -> None:
        by_id = {p["id"]: p for p in self.projects}
        self.projects = [by_id[pid] for pid in new_order_ids if pid in by_id]
        self.save_projects()

    # ---- quick folders ------------------------------------------------------
    def reorder_quick_folders(self, project_id: str, new_order_paths: list[str]) -> None:
        project = self.find_project(project_id)
        if not project:
            return
        by_path = {f["path"]: f for f in project.get("quickFolders", [])}
        project["quickFolders"] = [by_path[p] for p in new_order_paths if p in by_path]
        self.save_projects()

    def add_quick_folder(self, project_id: str, name: str, path: str) -> bool:
        project = self.find_project(project_id)
        if not project:
            return False
        project.setdefault("quickFolders", [])
        if any(f["path"] == path for f in project["quickFolders"]):
            return False
        project["quickFolders"].append({"name": name, "path": path})
        self.save_projects()
        return True

    # ---- browsing -----------------------------------------------------------
    def browse_to(self, project_id: str, folder_path: str) -> None:
        self.browse_path[project_id] = folder_path
        self.browse_history[project_id] = [folder_path]

    def navigate_into(self, project_id: str, folder_path: str) -> None:
        self.browse_path[project_id] = folder_path
        self.browse_history.setdefault(project_id, []).append(folder_path)

    def navigate_back(self, project_id: str) -> bool:
        history = self.browse_history.get(project_id, [])
        if len(history) <= 1:
            return False
        history.pop()
        self.browse_path[project_id] = history[-1]
        return True

    def navigate_to_breadcrumb(self, project_id: str, index: int) -> None:
        history = self.browse_history.get(project_id, [])
        if index >= len(history):
            return
        self.browse_history[project_id] = history[: index + 1]
        self.browse_path[project_id] = self.browse_history[project_id][-1]

    def close_browser(self, project_id: str) -> None:
        self.browse_path.pop(project_id, None)
        self.browse_history.pop(project_id, None)

    # ---- recent files ---------------------------------------------------------
    def track_recent_file(self, project_id: str, file_path: str, file_name: str) -> None:
        files = self.recent_files.setdefault(project_id, [])
        files[:] = [f for f in files if f["path"] != file_path]
        files.insert(0, {"path": file_path, "name": file_name, "timestamp": int(time.time() * 1000)})
        del files[MAX_RECENT_FILES:]
        self.save_recent_files()

    def remove_recent_file(self, project_id: str, index: int) -> None:
        files = self.recent_files.get(project_id, [])
        if 0 <= index < len(files):
            files.pop(index)
            self.save_recent_files()

    def get_recent_files(self, project_id: str) -> list[dict]:
        return self.recent_files.get(project_id, [])
