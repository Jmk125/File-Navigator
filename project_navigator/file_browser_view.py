"""Main-area view when browsing into a folder: breadcrumb, type-to-filter, file list."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import theme
from .icons import darken, file_icon, format_file_size, format_modified

PATH_ROLE = Qt.UserRole
IS_DIR_ROLE = Qt.UserRole + 1


def _is_light(hex_color: str) -> bool:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return False
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return luminance > 0.6


class Breadcrumb(QWidget):
    segmentClicked = Signal(int)
    backClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_ = QHBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(4)

    def set_history(self, history: list[str]) -> None:
        while self.layout_.count():
            child = self.layout_.takeAt(0)
            widget = child.widget()
            if widget:
                widget.hide()
                widget.deleteLater()

        colors = theme.current()
        for index, path in enumerate(history):
            name = os.path.basename(path.rstrip("\\/")) or path
            label = QLabel(("\U0001F3E0 " if index == 0 else "") + name)
            label.setStyleSheet(f"color: {colors['ACCENT']};")
            label.setCursor(Qt.PointingHandCursor)
            label.mousePressEvent = lambda e, i=index: self.segmentClicked.emit(i)
            self.layout_.addWidget(label)
            if index < len(history) - 1:
                sep = QLabel("›")
                sep.setStyleSheet(f"color: {colors['MUTED']};")
                self.layout_.addWidget(sep)

        if len(history) > 1:
            back_btn = QPushButton("← Back")
            back_btn.setStyleSheet("padding: 2px 10px; font-size: 12px;")
            back_btn.clicked.connect(self.backClicked)
            self.layout_.addSpacing(10)
            self.layout_.addWidget(back_btn)

        self.layout_.addStretch()


class FileBrowserView(QWidget):
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

        top_bar = QHBoxLayout()
        self.breadcrumb = Breadcrumb()
        self.breadcrumb.segmentClicked.connect(self.navigateBreadcrumb)
        self.breadcrumb.backClicked.connect(self.navigateBack)
        top_bar.addWidget(self.breadcrumb, 1)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Type to filter...")
        self.filter_edit.setFixedWidth(220)
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.filter_edit.installEventFilter(self)
        top_bar.addWidget(self.filter_edit)

        add_qa_btn = QToolButton()
        add_qa_btn.setText("+ Quick Access")
        add_qa_btn.setToolTip("Add current location to quick access")
        add_qa_btn.clicked.connect(self.addToQuickAccess)
        top_bar.addWidget(add_qa_btn)

        up_btn = QToolButton()
        up_btn.setText("↑ Up")
        up_btn.clicked.connect(self.navigateUp)
        top_bar.addWidget(up_btn)

        close_btn = QToolButton()
        close_btn.setText("✕ Close")
        close_btn.clicked.connect(self.closeBrowser)
        top_bar.addWidget(close_btn)

        explorer_btn = QToolButton()
        explorer_btn.setText("↗")
        explorer_btn.setToolTip("Open in File Explorer")
        explorer_btn.clicked.connect(self.openInExplorer)
        top_bar.addWidget(explorer_btn)

        layout.addLayout(top_bar)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Name", "Size", "Modified"])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.tree.setColumnWidth(0, 380)
        self.tree.itemClicked.connect(self._activate_item)
        self.tree.installEventFilter(self)
        layout.addWidget(self.tree, 1)

    def set_data(self, history: list[str], items: list[dict], color: str) -> None:
        self.breadcrumb.set_history(history)
        self._apply_header_color(color)
        self._apply_selection_style(color)
        self.tree.clear()
        for entry in items:
            icon = "\U0001F4C1" if entry["isDirectory"] else file_icon(entry["name"])
            size_str = "" if entry["isDirectory"] else format_file_size(entry["size"])
            modified_str = format_modified(entry["modified"]) if entry.get("modified") else ""
            tree_item = QTreeWidgetItem([f"{icon}  {entry['name']}", size_str, modified_str])
            tree_item.setData(0, PATH_ROLE, entry["path"])
            tree_item.setData(0, IS_DIR_ROLE, entry["isDirectory"])
            self.tree.addTopLevelItem(tree_item)
        self._apply_filter(self.filter_edit.text())

    def _apply_header_color(self, color: str) -> None:
        text_color = "#1a1a1a" if _is_light(color) else "#ffffff"
        self.tree.header().setStyleSheet(
            f"QHeaderView::section {{"
            f" background-color: {color};"
            f" color: {text_color};"
            f" padding: 4px 8px;"
            f" border: none;"
            f" font-weight: 600;"
            f" }}"
        )

    def _apply_selection_style(self, color: str) -> None:
        # A darker shade of the project's own color, echoing how the active
        # project is highlighted in the sidebar, rather than the generic
        # theme accent - so the Tab-cycled selector reads as "this project".
        highlight = darken(color, 0.5)
        text_color = "#1a1a1a" if _is_light(highlight) else "#ffffff"
        self.tree.setStyleSheet(
            f"QTreeWidget::item:selected {{ background: {highlight}; color: {text_color}; }}"
            f"QTreeWidget::item:selected:!active {{ background: {highlight}; color: {text_color}; }}"
        )

    def show_error(self, message: str) -> None:
        self.tree.clear()
        error_item = QTreeWidgetItem([f"⚠ {message}", "", ""])
        self.tree.addTopLevelItem(error_item)

    def focus_filter(self) -> None:
        self.filter_edit.setFocus()

    def clear_filter(self) -> None:
        self.filter_edit.clear()

    def has_filter_text(self) -> bool:
        return bool(self.filter_edit.text())

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            name = (item.text(0) or "").lower()
            item.setHidden(bool(needle) and needle not in name)

    def _activate_item(self, item: QTreeWidgetItem, _column: int) -> None:
        path = item.data(0, PATH_ROLE)
        is_dir = item.data(0, IS_DIR_ROLE)
        if path is None:
            return
        if is_dir:
            self.navigateInto.emit(path)
        else:
            self.openFile.emit(path)

    def _first_visible_row(self) -> int:
        for i in range(self.tree.topLevelItemCount()):
            if not self.tree.topLevelItem(i).isHidden():
                return i
        return -1

    def cycle_selection(self, step: int) -> None:
        """Move the highlighted row to the next (step=1) or previous (step=-1)
        visible item, wrapping around, and give the list keyboard focus."""
        visible_rows = [
            i for i in range(self.tree.topLevelItemCount()) if not self.tree.topLevelItem(i).isHidden()
        ]
        if not visible_rows:
            return

        target_row = visible_rows[0]
        if self.tree.hasFocus():
            current = self.tree.currentItem()
            current_row = self.tree.indexOfTopLevelItem(current) if current else -1
            if current_row in visible_rows:
                target_row = visible_rows[(visible_rows.index(current_row) + step) % len(visible_rows)]

        self.tree.setFocus()
        self.tree.setCurrentItem(self.tree.topLevelItem(target_row))

    def eventFilter(self, obj, event) -> bool:
        tree = getattr(self, "tree", None)
        if tree is None:
            return super().eventFilter(obj, event)

        if obj is self.filter_edit and event.type() == event.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key_Down, Qt.Key_Up, Qt.Key_Return, Qt.Key_Enter):
                tree.setFocus()
                if tree.currentItem() is None:
                    row = self._first_visible_row()
                    if row >= 0:
                        tree.setCurrentItem(tree.topLevelItem(row))
                if key in (Qt.Key_Return, Qt.Key_Enter) and tree.currentItem():
                    self._activate_item(tree.currentItem(), 0)
                    return True
                tree.keyPressEvent(event)
                return True
        if obj is tree and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and tree.currentItem():
                self._activate_item(tree.currentItem(), 0)
                return True
        return super().eventFilter(obj, event)
