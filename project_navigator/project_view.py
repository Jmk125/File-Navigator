"""Unified per-project panel: quick-access tiles pinned at top, then a
resizable split between the file browser (while navigating) and recent files."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QSplitter, QVBoxLayout, QWidget

from .file_browser_view import FileBrowserView
from .tiles_view import FolderTileList, RecentFilesPanel


class ProjectView(QWidget):
    folderActivated = Signal(str)
    foldersReordered = Signal(list)
    recentFileOpened = Signal(str)
    recentFileRemoved = Signal(int)
    splitSizesChanged = Signal(list)

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
        self._browse_sizes = [300, 300]

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

        self.split = QSplitter(Qt.Orientation.Vertical)
        self.split.setChildrenCollapsible(False)
        self.split.setHandleWidth(8)

        self.browser = FileBrowserView()
        self.browser.navigateInto.connect(self.navigateInto)
        self.browser.navigateUp.connect(self.navigateUp)
        self.browser.navigateBack.connect(self.navigateBack)
        self.browser.navigateBreadcrumb.connect(self.navigateBreadcrumb)
        self.browser.closeBrowser.connect(self.closeBrowser)
        self.browser.openFile.connect(self.openFile)
        self.browser.openInExplorer.connect(self.openInExplorer)
        self.browser.addToQuickAccess.connect(self.addToQuickAccess)
        self.split.addWidget(self.browser)

        self.recent_panel = RecentFilesPanel()
        self.recent_panel.recentFileOpened.connect(self.recentFileOpened)
        self.recent_panel.recentFileRemoved.connect(self.recentFileRemoved)
        self.split.addWidget(self.recent_panel)

        self.split.splitterMoved.connect(self._on_splitter_moved)
        layout.addWidget(self.split, 1)

    def _on_splitter_moved(self, pos: int, index: int) -> None:
        if self.browser.isVisible():
            self._browse_sizes = self.split.sizes()
            self.splitSizesChanged.emit(self._browse_sizes)

    def set_split_sizes(self, sizes: list[int]) -> None:
        if sizes and len(sizes) == 2 and all(sizes):
            self._browse_sizes = list(sizes)
            if self.browser.isVisible():
                self.split.setSizes(self._browse_sizes)

    def show_project(self, project: dict, browsing: bool, recent_files: list[dict]) -> None:
        color = project["color"]
        folders = project.get("quickFolders", [])

        self.tile_list.set_color(color)
        self.tile_list.set_folders(folders)
        self.tile_list.setVisible(bool(folders))
        self.empty_quick_label.setVisible(not folders)

        self.browser.setVisible(browsing)
        self.split.handle(1).setEnabled(browsing)
        if browsing:
            self.split.setSizes(self._browse_sizes)
        else:
            total = sum(self.split.sizes()) or sum(self._browse_sizes) or 600
            self.split.setSizes([0, total])

        self.recent_panel.set_recent(recent_files, color)

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
