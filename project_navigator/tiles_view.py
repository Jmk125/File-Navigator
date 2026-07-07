"""Main-area view for a selected project: quick-access folder tiles + recent files."""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QListView, QListWidget, QListWidgetItem,
    QStyledItemDelegate, QToolButton, QVBoxLayout, QWidget,
)

from .icons import FOLDER_ICON, format_relative_time

PATH_ROLE = Qt.UserRole
NAME_ROLE = Qt.UserRole + 1
TILE_SIZE = QSize(128, 92)


class FolderTileDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = "#2d5f9f"

    def sizeHint(self, option, index):
        return TILE_SIZE

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = option.rect.adjusted(4, 4, -4, -4)
        color = QColor(self.color)

        bg = QColor(color)
        bg.setAlpha(28)
        painter.setPen(color)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 8, 8)

        icon_font = painter.font()
        icon_font.setPointSize(22)
        painter.setFont(icon_font)
        painter.setPen(QColor("#f0f0f0"))
        icon_rect = QRect(rect.left(), rect.top() + 8, rect.width(), 30)
        painter.drawText(icon_rect, Qt.AlignCenter, FOLDER_ICON)

        name_font = painter.font()
        name_font.setPointSize(9)
        painter.setFont(name_font)
        metrics = QFontMetrics(name_font)
        name = index.data(NAME_ROLE) or ""
        name_rect = QRect(rect.left() + 4, rect.top() + 42, rect.width() - 8, rect.height() - 46)
        elided = metrics.elidedText(name, Qt.ElideRight, name_rect.width())
        painter.drawText(name_rect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, elided)

        hotkey = index.row() + 1
        if hotkey <= 9:
            badge_rect = QRect(rect.left() + 4, rect.top() + 4, 18, 18)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#000000b0"))
            painter.drawEllipse(badge_rect)
            painter.setPen(QColor("#ffffff"))
            badge_font = painter.font()
            badge_font.setPointSize(9)
            badge_font.setBold(True)
            painter.setFont(badge_font)
            painter.drawText(badge_rect, Qt.AlignCenter, str(hotkey))

        painter.restore()


class FolderTileList(QListWidget):
    folderActivated = Signal(str)
    reordered = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSpacing(6)
        self.setUniformItemSizes(True)
        self.setFrameShape(self.Shape.NoFrame)
        self._delegate = FolderTileDelegate(self)
        self.setItemDelegate(self._delegate)
        self.itemClicked.connect(lambda item: self.folderActivated.emit(item.data(PATH_ROLE)))

    def set_color(self, color: str) -> None:
        self._delegate.color = color
        self.viewport().update()

    def set_folders(self, folders: list[dict]) -> None:
        self.clear()
        for folder in folders:
            item = QListWidgetItem()
            item.setData(PATH_ROLE, folder["path"])
            item.setData(NAME_ROLE, folder["name"])
            self.addItem(item)

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        paths = [self.item(i).data(PATH_ROLE) for i in range(self.count())]
        self.reordered.emit(paths)

    def open_by_hotkey(self, digit: int) -> bool:
        index = digit - 1
        if 0 <= index < self.count():
            self.folderActivated.emit(self.item(index).data(PATH_ROLE))
            return True
        return False


class RecentFileRow(QWidget):
    def __init__(self, file_entry: dict, color: str, parent=None):
        super().__init__(parent)
        self.path = file_entry["path"]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        self.setStyleSheet(f"background: {color}30; border-radius: 6px;")

        text = QLabel(f"\U0001F4C4 {file_entry['name']}")
        text.setStyleSheet("font-weight: 500;")
        path_label = QLabel(file_entry["path"])
        path_label.setStyleSheet("color: #888; font-size: 11px;")

        text_col = QVBoxLayout()
        text_col.addWidget(text)
        text_col.addWidget(path_label)
        layout.addLayout(text_col, 1)

        time_label = QLabel(format_relative_time(file_entry["timestamp"]))
        time_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(time_label)

        self.remove_button = QToolButton()
        self.remove_button.setText("✕")
        self.remove_button.setAutoRaise(True)
        self.remove_button.setStyleSheet("color: #c42b1c;")
        layout.addWidget(self.remove_button)

    def mousePressEvent(self, event) -> None:
        # Only reached for clicks on the row's own background; child widgets
        # (like remove_button) receive their own events directly.
        self.openRequested(self.path)
        super().mousePressEvent(event)

    def openRequested(self, path: str) -> None:
        pass  # overridden per-instance via signal connection from ProjectTilesView


class ProjectTilesView(QWidget):
    folderActivated = Signal(str)
    foldersReordered = Signal(list)
    recentFileOpened = Signal(str)
    recentFileRemoved = Signal(int)
    addProjectClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(20, 20, 20, 20)
        self.layout_.setSpacing(16)

    def clear(self) -> None:
        while self.layout_.count():
            child = self.layout_.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def show_empty_state(self) -> None:
        self._show_placeholder("No projects yet", 'Click "+" in the Projects pane to get started')

    def show_select_prompt(self) -> None:
        self._show_placeholder("Select a project", "Choose a project on the left to see its quick access folders")

    def _show_placeholder(self, title: str, hint_text: str) -> None:
        self.clear()
        label = QLabel(title)
        label.setStyleSheet("color: #888; font-size: 18px;")
        label.setAlignment(Qt.AlignCenter)
        hint = QLabel(hint_text)
        hint.setStyleSheet("color: #666; font-size: 13px;")
        hint.setAlignment(Qt.AlignCenter)
        self.layout_.addStretch()
        self.layout_.addWidget(label)
        self.layout_.addWidget(hint)
        self.layout_.addStretch()

    def show_project(self, project: dict, recent_files: list[dict]) -> None:
        self.clear()
        color = project["color"]

        section_title = QLabel("QUICK ACCESS LOCATIONS")
        section_title.setStyleSheet("color: #aaa; font-size: 12px; font-weight: 600; letter-spacing: 0.5px;")
        self.layout_.addWidget(section_title)

        folders = project.get("quickFolders", [])
        if folders:
            self.tile_list = FolderTileList()
            self.tile_list.set_color(color)
            self.tile_list.set_folders(folders)
            self.tile_list.folderActivated.connect(self.folderActivated)
            self.tile_list.reordered.connect(self.foldersReordered)
            row_count = -(-len(folders) // max(1, self.width() // 140)) if self.width() else 1
            self.tile_list.setMinimumHeight(110 * max(1, row_count))
            self.layout_.addWidget(self.tile_list)
        else:
            empty = QLabel('No quick access locations yet. Toggle "✎" in the Projects pane and click Edit to add some.')
            empty.setStyleSheet("color: #666; padding: 16px;")
            empty.setWordWrap(True)
            self.layout_.addWidget(empty)

        if recent_files:
            recent_title = QLabel("RECENT FILES")
            recent_title.setStyleSheet("color: #aaa; font-size: 12px; font-weight: 600; letter-spacing: 0.5px; margin-top: 8px;")
            self.layout_.addWidget(recent_title)

            for index, entry in enumerate(recent_files):
                row = RecentFileRow(entry, color)
                row.openRequested = lambda path, i=index: self.recentFileOpened.emit(path)
                row.remove_button.clicked.connect(lambda checked=False, i=index: self.recentFileRemoved.emit(i))
                self.layout_.addWidget(row)

        self.layout_.addStretch()

    def open_by_hotkey(self, digit: int) -> bool:
        tile_list = getattr(self, "tile_list", None)
        if tile_list is None:
            return False
        return tile_list.open_by_hotkey(digit)
