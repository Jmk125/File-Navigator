"""Top-level window: sidebar + main content area, global keyboard shortcuts, toasts."""
from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication, QDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QSplitter, QStackedWidget, QTextEdit,
)

from . import storage, theme
from .dialogs import ProjectDialog, QuickAccessDialog
from .project_view import ProjectView
from .settings import load_settings, save_settings
from .settings_dialog import SettingsDialog
from .sidebar import SidebarWidget
from .state import NavigatorState
from .tiles_view import EmptyStateView

TEXT_INPUT_TYPES = (QLineEdit, QPlainTextEdit, QTextEdit)
HOTKEY_ID_SHOW_HIDE = 0x504E46
WM_HOTKEY = 0x0312


def _windows_hotkey_parts(sequence: str) -> tuple[int, int] | None:
    if sys.platform != "win32" or not sequence:
        return None
    key_sequence = QKeySequence(sequence)
    if key_sequence.isEmpty():
        return None
    combo = key_sequence[0]
    modifiers = combo.keyboardModifiers()
    key = combo.key()
    mod_flags = 0
    if modifiers & Qt.KeyboardModifier.AltModifier:
        mod_flags |= 0x0001
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        mod_flags |= 0x0002
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        mod_flags |= 0x0004
    if modifiers & Qt.KeyboardModifier.MetaModifier:
        mod_flags |= 0x0008
    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z or Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        vk = key
    else:
        mapped = {Qt.Key.Key_F1 + i: 0x70 + i for i in range(24)}
        vk = mapped.get(key)
    if not vk:
        return None
    return mod_flags, int(vk)


def _basename(path: str) -> str:
    return os.path.basename(path.rstrip("\\/")) or path


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Navigator")
        self.resize(1250, 850)

        self.state = NavigatorState()
        self.state.load()

        self.settings = load_settings()
        self.hotkeys = self.settings["hotkeys"]
        self._registered_hotkey = False

        self.sidebar = SidebarWidget()
        self.sidebar.setMinimumWidth(200)
        self.sidebar.setMaximumWidth(360)

        self.empty_state = EmptyStateView()
        self.project_view = ProjectView()
        self.project_view.set_split_sizes(self.settings["splitter_sizes"])

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
        self._register_summon_hotkey()

    # ---- wiring -----------------------------------------------------------------
    def _connect_signals(self) -> None:
        self.sidebar.addProjectClicked.connect(self.on_add_project)
        self.sidebar.settingsClicked.connect(self.on_open_settings)
        self.sidebar.list.projectActivated.connect(self.on_project_selected)
        self.sidebar.list.editRequested.connect(self.on_edit_project)
        self.sidebar.list.duplicateRequested.connect(self.on_duplicate_project)
        self.sidebar.list.deleteRequested.connect(self.on_delete_project)
        self.sidebar.list.reordered.connect(self.on_projects_reordered)

        self.project_view.folderActivated.connect(self.on_folder_activated)
        self.project_view.foldersReordered.connect(self.on_folders_reordered)
        self.project_view.recentFileOpened.connect(self.on_open_file)
        self.project_view.recentFileRemoved.connect(self.on_remove_recent)
        self.project_view.splitSizesChanged.connect(self.on_split_sizes_changed)

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
        self.project_view.show_project(
            project, browsing, self.state.get_recent_files(pid),
            self._active_quick_folder_path(project) if browsing else None,
        )
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

    def _active_quick_folder_path(self, project: dict) -> str | None:
        current = self.state.browse_path.get(project["id"])
        if not current:
            return None
        current_norm = storage.normalize_path(current)
        matches = []
        for folder in project.get("quickFolders", []):
            folder_path = storage.normalize_path(folder["path"])
            folder_prefix = folder_path.rstrip("\\/")
            if current_norm == folder_path or current_norm.startswith(folder_prefix + "\\") or current_norm.startswith(folder_prefix + "/"):
                matches.append(folder_path)
        return max(matches, key=len) if matches else None

    def _open_single_quick_folder_if_enabled(self, project_id: str) -> bool:
        if not self.settings.get("auto_open_single_quick_folder", True):
            return False
        project = self.state.find_project(project_id)
        folders = project.get("quickFolders", []) if project else []
        if len(folders) != 1:
            return False
        self.state.browse_to(project_id, storage.normalize_path(folders[0]["path"]))
        return True

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
        self._open_single_quick_folder_if_enabled(project_id)
        self.refresh_sidebar()
        self.render_content()
        self._register_summon_hotkey()

    # ---- settings ---------------------------------------------------------------------
    def on_open_settings(self) -> None:
        dialog = SettingsDialog(
            self, theme=self.settings["theme"], hotkeys=self.hotkeys,
            auto_open_single_quick_folder=self.settings.get("auto_open_single_quick_folder", True),
            summon_hotkey_enabled=self.settings.get("summon_hotkey_enabled", True),
            summon_hotkey=self.settings.get("summon_hotkey", "Ctrl+Alt+F"),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_theme, new_hotkeys, auto_open_single, summon_enabled, summon_hotkey = dialog.values()
            self.settings["theme"] = new_theme
            self.settings["hotkeys"] = new_hotkeys
            self.settings["auto_open_single_quick_folder"] = auto_open_single
            self.settings["summon_hotkey_enabled"] = summon_enabled
            self.settings["summon_hotkey"] = summon_hotkey
            self.hotkeys = new_hotkeys
            save_settings(self.settings)
            self._register_summon_hotkey()

            app = QApplication.instance()
            if app is not None:
                theme.apply_theme(app, new_theme)
            # Custom-painted delegates read colors at paint time but won't
            # repaint on their own - force a rebuild so the new theme shows.
            self.refresh_sidebar()
            self.render_content()

    def on_split_sizes_changed(self, sizes: list) -> None:
        self.settings["splitter_sizes"] = list(sizes)
        save_settings(self.settings)

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

    # ---- global keyboard handling -------------------------------------------------------
    # Escape backs out one step at a time; 1-9 jump into a quick access folder;
    # a handful of other actions (back/up/add-to-quick-access) are rebindable
    # via Settings - see settings.DEFAULT_HOTKEYS.
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
        if pid is None:
            # Nothing selected - 1-9 jump to a project instead, matching the
            # numbers now shown on the sidebar rows.
            index = digit - 1
            if 0 <= index < len(self.state.projects):
                self.on_project_selected(self.state.projects[index]["id"])
                return True
            return False
        if pid in self.state.browse_path:
            return False
        return self.project_view.open_by_hotkey(digit)

    def _key_matches(self, event, action: str) -> bool:
        sequence_str = self.hotkeys.get(action)
        if not sequence_str:
            return False
        return QKeySequence(event.keyCombination()) == QKeySequence(sequence_str)

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            screen = self.screen() or QApplication.screenAt(self.frameGeometry().center())
            if screen is not None:
                self.setGeometry(screen.availableGeometry())
            self.showFullScreen()
            QTimer.singleShot(0, self._fit_fullscreen_to_current_screen)

    def _fit_fullscreen_to_current_screen(self) -> None:
        if not self.isFullScreen():
            return
        screen = self.screen() or QApplication.screenAt(self.frameGeometry().center())
        if screen is not None:
            self.setGeometry(screen.geometry())

    def show_or_hide_from_hotkey(self) -> None:
        if self.isVisible() and self.isActiveWindow():
            self.hide()
            return
        self.show()
        self.raise_()
        self.activateWindow()

    def _register_summon_hotkey(self) -> None:
        if sys.platform != "win32" or self.winId() is None:
            return
        hwnd = int(self.winId())
        if self._registered_hotkey:
            ctypes.windll.user32.UnregisterHotKey(hwnd, HOTKEY_ID_SHOW_HIDE)
            self._registered_hotkey = False
        if not self.settings.get("summon_hotkey_enabled", True):
            return
        parts = _windows_hotkey_parts(self.settings.get("summon_hotkey", "Ctrl+Alt+F"))
        if not parts:
            return
        modifiers, vk = parts
        self._registered_hotkey = bool(ctypes.windll.user32.RegisterHotKey(hwnd, HOTKEY_ID_SHOW_HIDE, modifiers, vk))

    def nativeEvent(self, event_type, message):
        if sys.platform == "win32":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID_SHOW_HIDE:
                self.show_or_hide_from_hotkey()
                return True, 0
        return super().nativeEvent(event_type, message)

    def closeEvent(self, event) -> None:
        reply = QMessageBox.question(
            self, "Close Project Navigator",
            "Do you want to exit Project Navigator completely? Choose No to hide it instead.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return
        if reply == QMessageBox.StandardButton.No:
            event.ignore()
            self.hide()
            return
        if sys.platform == "win32" and self._registered_hotkey:
            ctypes.windll.user32.UnregisterHotKey(int(self.winId()), HOTKEY_ID_SHOW_HIDE)
            self._registered_hotkey = False
        event.accept()

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            if QApplication.activeModalWidget() is not None:
                return super().eventFilter(obj, event)

            key = event.key()
            focus_widget = QApplication.focusWidget()
            is_text_input = isinstance(focus_widget, TEXT_INPUT_TYPES)
            tree = self.project_view.browser.tree
            filter_edit = self.project_view.browser.filter_edit
            pid = self.state.selected_project_id
            browsing = pid is not None and pid in self.state.browse_path

            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.AltModifier:
                self.toggle_fullscreen()
                return True

            if self._key_matches(event, "back_out"):
                self.handle_escape()
                return True

            if not is_text_input and Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
                digit = key - Qt.Key.Key_0
                if self.handle_digit_hotkey(digit):
                    return True

            if self._key_matches(event, "navigate_back"):
                # Let it delete a character if there's filter text to delete;
                # otherwise (or outside any text field) it means "go back".
                if not is_text_input or (focus_widget is filter_edit and not filter_edit.text()):
                    self.on_navigate_back()
                    return True

            if self._key_matches(event, "add_quick_access") and not is_text_input:
                self.on_add_to_quick_access()
                return True

            # Type-ahead: if browsing and the file list (not a text box) has focus,
            # forward the first keystroke to the filter box instead of requiring a click.
            if (
                browsing
                and not is_text_input
                and focus_widget is tree
                and event.text()
                and event.text().isprintable()
                and not event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
            ):
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
