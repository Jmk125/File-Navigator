"""Top-level window: sidebar + main content area, global keyboard shortcuts, toasts."""
from __future__ import annotations

import os

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QSplitter, QStackedWidget, QTextEdit,
)

from . import storage
from .dialogs import ProjectDialog, QuickAccessDialog
from .project_view import ProjectView
from .sidebar import SidebarWidget
from .state import NavigatorState
from .tiles_view import EmptyStateView

TEXT_INPUT_TYPES = (QLineEdit, QPlainTextEdit, QTextEdit)


def _basename(path: str) -> str:
    return os.path.basename(path.rstrip("\\/")) or path


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Navigator")
        self.resize(1250, 850)

        self.state = NavigatorState()
        self.state.load()

        self.sidebar = SidebarWidget()
        self.sidebar.setMinimumWidth(200)
        self.sidebar.setMaximumWidth(360)

        self.empty_state = EmptyStateView()
        self.project_view = ProjectView()

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.empty_state)
        self.content_stack.addWidget(self.project_view)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.content_stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 990])
        self.setCentralWidget(splitter)

        self._connect_signals()

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        self.refresh_sidebar()
        self.render_content()

    # ---- wiring -----------------------------------------------------------------
    def _connect_signals(self) -> None:
        self.sidebar.addProjectClicked.connect(self.on_add_project)
        self.sidebar.list.projectActivated.connect(self.on_project_selected)
        self.sidebar.list.editRequested.connect(self.on_edit_project)
        self.sidebar.list.duplicateRequested.connect(self.on_duplicate_project)
        self.sidebar.list.deleteRequested.connect(self.on_delete_project)
        self.sidebar.list.reordered.connect(self.on_projects_reordered)

        self.project_view.folderActivated.connect(self.on_folder_activated)
        self.project_view.foldersReordered.connect(self.on_folders_reordered)
        self.project_view.recentFileOpened.connect(self.on_open_file)
        self.project_view.recentFileRemoved.connect(self.on_remove_recent)

        self.project_view.navigateInto.connect(self.on_navigate_into)
        self.project_view.navigateUp.connect(self.on_navigate_up)
        self.project_view.navigateBack.connect(self.on_navigate_back)
        self.project_view.navigateBreadcrumb.connect(self.on_navigate_breadcrumb)
        self.project_view.closeBrowser.connect(self.on_close_browser)
        self.project_view.openFile.connect(self.on_open_file)
        self.project_view.openInExplorer.connect(self.on_open_in_explorer)
        self.project_view.addToQuickAccess.connect(self.on_add_to_quick_access)

    # ---- rendering ----------------------------------------------------------------
    def refresh_sidebar(self) -> None:
        self.sidebar.set_projects(self.state.projects, self.state.selected_project_id)

    def render_content(self) -> None:
        pid = self.state.selected_project_id
        if pid is None:
            self.content_stack.setCurrentWidget(self.empty_state)
            if self.state.projects:
                self.empty_state.set_text(
                    "Select a project", "Choose a project on the left to see its quick access folders",
                )
            else:
                self.empty_state.set_text("No projects yet", 'Click "+" in the Projects pane to get started')
            return

        project = self.state.find_project(pid)
        if project is None:
            self.state.selected_project_id = None
            self.render_content()
            return

        self.content_stack.setCurrentWidget(self.project_view)
        browsing = pid in self.state.browse_path
        self.project_view.show_project(project, browsing, self.state.get_recent_files(pid))
        if browsing:
            self._load_browse_view(pid, project)
        else:
            self.project_view.clear_filter()

    def _load_browse_view(self, pid: str, project: dict) -> None:
        path = self.state.browse_path[pid]
        history = self.state.browse_history.get(pid, [path])
        self.project_view.clear_filter()
        try:
            items = storage.list_dir(path)
            self.project_view.load_browse_data(history, items, project["color"])
        except OSError as exc:
            self.project_view.show_browse_error(history, str(exc), project["color"])
        self.project_view.focus_filter()

    # ---- project actions -----------------------------------------------------------
    def on_add_project(self) -> None:
        dialog = ProjectDialog(self, title="Add Project")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, color, folders = dialog.values()
            project = self.state.add_project(name, color, folders)
            self.state.selected_project_id = project["id"]
            self.refresh_sidebar()
            self.render_content()

    def on_edit_project(self, project_id: str) -> None:
        project = self.state.find_project(project_id)
        if not project:
            return
        dialog = ProjectDialog(
            self, title="Edit Project", name=project["name"], color=project["color"],
            folders=project.get("quickFolders", []),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, color, folders = dialog.values()
            self.state.update_project(project_id, name, color, folders)
            self.refresh_sidebar()
            if self.state.selected_project_id == project_id:
                self.render_content()

    def on_duplicate_project(self, project_id: str) -> None:
        project = self.state.find_project(project_id)
        if not project:
            return
        self.state.duplicate_project(project_id, project["name"] + " (Copy)")
        self.refresh_sidebar()
        self.show_toast(f'Duplicated "{project["name"]}"')

    def on_delete_project(self, project_id: str) -> None:
        project = self.state.find_project(project_id)
        if not project:
            return
        reply = QMessageBox.question(
            self, "Delete Project", f'Are you sure you want to delete "{project["name"]}"?',
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.state.delete_project(project_id)
            self.refresh_sidebar()
            self.render_content()

    def on_projects_reordered(self, ids: list) -> None:
        self.state.reorder_projects(ids)

    def on_project_selected(self, project_id: str) -> None:
        self.state.selected_project_id = project_id
        # Selecting a project from the sidebar always lands on its home view
        # (quick access + recents), not wherever you last left off browsing.
        self.state.close_browser(project_id)
        self.refresh_sidebar()
        self.render_content()

    # ---- folder / browsing actions --------------------------------------------------
    def on_folder_activated(self, path: str) -> None:
        pid = self.state.selected_project_id
        if not pid:
            return
        self.state.browse_to(pid, storage.normalize_path(path))
        self.render_content()

    def on_folders_reordered(self, paths: list) -> None:
        pid = self.state.selected_project_id
        if pid:
            self.state.reorder_quick_folders(pid, paths)

    def on_navigate_into(self, path: str) -> None:
        pid = self.state.selected_project_id
        if not pid:
            return
        self.state.navigate_into(pid, path)
        self.render_content()

    def on_navigate_up(self) -> None:
        pid = self.state.selected_project_id
        if not pid:
            return
        current = self.state.browse_path.get(pid)
        if not current:
            return
        parent = storage.parent_path(current)
        if parent:
            self.state.navigate_into(pid, parent)
            self.render_content()

    def on_navigate_back(self) -> None:
        pid = self.state.selected_project_id
        if pid and self.state.navigate_back(pid):
            self.render_content()

    def on_navigate_breadcrumb(self, index: int) -> None:
        pid = self.state.selected_project_id
        if not pid:
            return
        self.state.navigate_to_breadcrumb(pid, index)
        self.render_content()

    def on_close_browser(self) -> None:
        pid = self.state.selected_project_id
        if not pid:
            return
        self.state.close_browser(pid)
        self.render_content()

    def on_open_in_explorer(self) -> None:
        pid = self.state.selected_project_id
        path = self.state.browse_path.get(pid) if pid else None
        if not path:
            self.show_toast("No location currently being browsed", error=True)
            return
        try:
            storage.open_path(path)
            self.show_toast(f"Opened in Explorer: {_basename(path)}")
        except Exception as exc:
            self.show_toast(f"Error: {exc}", error=True)

    def on_add_to_quick_access(self) -> None:
        pid = self.state.selected_project_id
        path = self.state.browse_path.get(pid) if pid else None
        if not path:
            self.show_toast("No location currently being browsed", error=True)
            return
        dialog = QuickAccessDialog(
            self, suggested_name=_basename(path), path=path,
            projects=self.state.projects, current_project_id=pid,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, target_id = dialog.values()
            if not self.state.add_quick_folder(target_id, name, path):
                self.show_toast("This location is already in quick access for this project", error=True)
                return
            target = self.state.find_project(target_id)
            self.show_toast(f'Added "{name}" to {target["name"]}')

    # ---- files ------------------------------------------------------------------------
    def on_open_file(self, path: str) -> None:
        pid = self.state.selected_project_id
        if not pid:
            return
        name = _basename(path)
        self.state.track_recent_file(pid, path, name)
        try:
            storage.open_path(path)
            self.show_toast(f"Opening: {name}")
        except Exception as exc:
            self.show_toast(f"Error: {exc}", error=True)
        if pid not in self.state.browse_path:
            self.render_content()

    def on_remove_recent(self, index: int) -> None:
        pid = self.state.selected_project_id
        if not pid:
            return
        self.state.remove_recent_file(pid, index)
        self.render_content()

    # ---- global keyboard handling: Escape backs out, 1-9 jump into folders ------------
    def handle_escape(self) -> None:
        pid = self.state.selected_project_id
        if pid and pid in self.state.browse_path:
            if self.project_view.has_filter_text():
                self.project_view.clear_filter()
            else:
                self.state.close_browser(pid)
                self.render_content()
        elif pid:
            self.state.selected_project_id = None
            self.refresh_sidebar()
            self.render_content()

    def handle_digit_hotkey(self, digit: int) -> bool:
        pid = self.state.selected_project_id
        if not pid or pid in self.state.browse_path:
            return False
        return self.project_view.open_by_hotkey(digit)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            if QApplication.activeModalWidget() is not None:
                return super().eventFilter(obj, event)

            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.handle_escape()
                return True

            focus_widget = QApplication.focusWidget()
            is_text_input = isinstance(focus_widget, TEXT_INPUT_TYPES)

            if not is_text_input and Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
                digit = key - Qt.Key.Key_0
                if self.handle_digit_hotkey(digit):
                    return True

            # Type-ahead: if browsing and the file list (not a text box) has focus,
            # forward the first keystroke to the filter box instead of requiring a click.
            pid = self.state.selected_project_id
            browsing = pid is not None and pid in self.state.browse_path
            if (
                browsing
                and not is_text_input
                and focus_widget is self.project_view.browser.tree
                and event.text()
                and event.text().isprintable()
                and not event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
            ):
                filter_edit = self.project_view.browser.filter_edit
                filter_edit.setFocus()
                filter_edit.setText(filter_edit.text() + event.text())
                return True

        return super().eventFilter(obj, event)

    # ---- toast notifications -------------------------------------------------------------
    def show_toast(self, message: str, error: bool = False) -> None:
        label = QLabel(message, self)
        color = "#c42b1c" if error else "#2d5f9f"
        label.setStyleSheet(
            f"background: {color}; color: white; padding: 12px 20px; border-radius: 6px; font-size: 13px;"
        )
        label.setWordWrap(True)
        label.setFixedWidth(min(380, max(200, label.fontMetrics().horizontalAdvance(message) + 40)))
        label.adjustSize()
        label.move(self.width() - label.width() - 24, self.height() - label.height() - 24)
        label.show()
        label.raise_()
        QTimer.singleShot(3000, label.deleteLater)
