"""Unified per-project panel: quick-access tiles pinned at top, then either the
file browser (while navigating) or nothing, then recent files."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .file_browser_view import FileBrowserView
from .tiles_view import FolderTileList, RecentFileRow


class ProjectView(QWidget):
    folderActivated = Signal(str)
    foldersReordered = Signal(list)
    recentFileOpened = Signal(str)
    recentFileRemoved = Signal(int)

    navigateInto = Signal(str)
    navigateUp = Signal()
    navigateBack = Signal()
    navigateBreadcrumb = Signal(int)
    closeBrowser = Signal()
    openFile = Signal(str)
    openInExplorer = Signal()
    addToQuickAccess = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(10)

        quick_title = QLabel("QUICK ACCESS LOCATIONS")
        quick_title.setObjectName("sectionTitle")
        layout.addWidget(quick_title)

        self.tile_list = FolderTileList(wrap=False)
        self.tile_list.folderActivated.connect(self.folderActivated)
        self.tile_list.reordered.connect(self.foldersReordered)
        layout.addWidget(self.tile_list)

        self.empty_quick_label = QLabel(
            'No quick access locations yet. Toggle "✎" in the Projects pane and click Edit to add some.'
        )
        self.empty_quick_label.setObjectName("mutedHint")
        self.empty_quick_label.setWordWrap(True)
        layout.addWidget(self.empty_quick_label)

        self.browser = FileBrowserView()
        self.browser.navigateInto.connect(self.navigateInto)
        self.browser.navigateUp.connect(self.navigateUp)
        self.browser.navigateBack.connect(self.navigateBack)
        self.browser.navigateBreadcrumb.connect(self.navigateBreadcrumb)
        self.browser.closeBrowser.connect(self.closeBrowser)
        self.browser.openFile.connect(self.openFile)
        self.browser.openInExplorer.connect(self.openInExplorer)
        self.browser.addToQuickAccess.connect(self.addToQuickAccess)
        layout.addWidget(self.browser, 1)

        self.recent_title = QLabel("RECENT FILES")
        self.recent_title.setObjectName("sectionTitle")
        layout.addWidget(self.recent_title)

        self.recent_container = QWidget()
        self.recent_layout = QVBoxLayout(self.recent_container)
        self.recent_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_layout.setSpacing(8)
        layout.addWidget(self.recent_container)

        layout.addStretch()

    def show_project(self, project: dict, browsing: bool, recent_files: list[dict]) -> None:
        color = project["color"]
        folders = project.get("quickFolders", [])

        self.tile_list.set_color(color)
        self.tile_list.set_folders(folders)
        self.tile_list.setVisible(bool(folders))
        self.empty_quick_label.setVisible(not folders)

        self.browser.setVisible(browsing)

        while self.recent_layout.count():
            child = self.recent_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.recent_title.setVisible(bool(recent_files))
        for index, entry in enumerate(recent_files):
            row = RecentFileRow(entry, color)
            row.openRequested = lambda path, i=index: self.recentFileOpened.emit(path)
            row.remove_button.clicked.connect(lambda checked=False, i=index: self.recentFileRemoved.emit(i))
            self.recent_layout.addWidget(row)

    def load_browse_data(self, history: list[str], items: list[dict], color: str) -> None:
        self.browser.set_data(history, items, color)

    def show_browse_error(self, history: list[str], message: str, color: str) -> None:
        self.browser.set_data(history, [], color)
        self.browser.show_error(message)

    def focus_filter(self) -> None:
        self.browser.focus_filter()

    def clear_filter(self) -> None:
        self.browser.clear_filter()

    def has_filter_text(self) -> bool:
        return self.browser.has_filter_text()

    def open_by_hotkey(self, digit: int) -> bool:
        return self.tile_list.open_by_hotkey(digit)
