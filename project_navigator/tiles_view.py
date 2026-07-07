"""Reusable pieces for a project's quick-access folder tiles and recent files."""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QListView, QListWidget, QListWidgetItem,
    QStyledItemDelegate, QToolButton, QVBoxLayout, QWidget,
)

from .icons import FOLDER_ICON, format_relative_time, tint

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
            badge_bg = QColor(0, 0, 0)
            badge_bg.setAlpha(176)
            painter.setBrush(badge_bg)
            painter.drawEllipse(badge_rect)
            painter.setPen(QColor("#ffffff"))
            badge_font = painter.font()
            badge_font.setPointSize(9)
            badge_font.setBold(True)
            painter.setFont(badge_font)
            painter.drawText(badge_rect, Qt.AlignCenter, str(hotkey))

        painter.restore()


class FolderTileList(QListWidget):
    """A row/grid of quick-access folder tiles. Used both at a project's home
    view and pinned above the file browser so saved locations are always
    one click away."""

    folderActivated = Signal(str)
    reordered = Signal(list)

    def __init__(self, parent=None, wrap: bool = True):
        super().__init__(parent)
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(wrap)
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
        # The delegate paints its own selection/hover look; suppress the
        # app-wide QSS selection tint so it doesn't show through as a
        # mismatched color underneath the tile.
        self.setStyleSheet(
            "QListWidget::item { border: none; }"
            "QListWidget::item:selected, QListWidget::item:hover { background: transparent; }"
        )
        if not wrap:
            self.setFixedHeight(TILE_SIZE.height() + 16)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

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
        self.setStyleSheet(f"background: {tint(color, 48)}; border-radius: 6px;")

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
        pass  # overridden per-instance via signal connection from ProjectView


class EmptyStateView(QWidget):
    """Shown in the main area when no project is selected."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.title = QLabel()
        self.title.setStyleSheet("color: #888; font-size: 18px;")
        self.title.setAlignment(Qt.AlignCenter)
        self.hint = QLabel()
        self.hint.setStyleSheet("color: #666; font-size: 13px;")
        self.hint.setAlignment(Qt.AlignCenter)
        layout.addStretch()
        layout.addWidget(self.title)
        layout.addWidget(self.hint)
        layout.addStretch()

    def set_text(self, title: str, hint: str) -> None:
        self.title.setText(title)
        self.hint.setText(hint)
