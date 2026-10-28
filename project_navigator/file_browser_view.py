"""Main-area view when browsing into a folder: breadcrumb, type-to-filter, file list."""
from __future__ import annotations

import os
import re

from PySide6.QtCore import QByteArray, QMimeData, QPoint, QRect, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QGuiApplication, QKeySequence, QMouseEvent, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu,
    QMessageBox, QPushButton, QRubberBand, QToolButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from . import file_locks, fileops, pdf_tools, pending_deletes, theme
from .pdf_tools import InsertPositionDialog, MergeOrderDialog
from .icons import darken, file_icon, format_file_size, format_modified

PATH_ROLE = Qt.UserRole
IS_DIR_ROLE = Qt.UserRole + 1
PENDING_COLUMN = 3
PENDING_TEXT = "⏳ Deletes when closed — click to cancel"


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


DROP_EFFECT_MIME = 'application/x-qt-windows-mime;value="Preferred DropEffect"'


class FileTree(QTreeWidget):
    """File list that drags real files out and accepts file drops in."""
    filesDropped = Signal(list, str, bool)  # source paths, target dir, move?
    pdfsDropped = Signal(list, str)  # source PDFs, PDF they were dropped on

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_dir = ""
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.CopyAction)
        # Rows span the full width, so Qt never sees an "empty" spot to start a
        # rubber band from. We draw our own: pressing on a file's name still
        # drags the file, pressing anywhere else on the row/blank area lassos.
        self._band = QRubberBand(QRubberBand.Shape.Rectangle, self.viewport())
        self._band_origin: QPoint | None = None   # in scrolled content coordinates
        self._band_press: QMouseEvent | None = None
        self._band_active = False
        self._band_base: set[int] = set()

    def selected_paths(self) -> list[str]:
        return [i.data(0, PATH_ROLE) for i in self.selectedItems() if i.data(0, PATH_ROLE)]

    def _scroll_offset(self) -> QPoint:
        return QPoint(self.horizontalScrollBar().value(), self.verticalScrollBar().value())

    def _on_name_text(self, pos: QPoint) -> bool:
        """True if pos is over a row's icon/name text (the part you drag files by)."""
        item = self.itemAt(pos)
        if item is None:
            return False
        rect = self.visualRect(self.indexFromItem(item, 0))
        text_right = rect.left() + 8 + self.fontMetrics().horizontalAdvance(item.text(0)) + 8
        return rect.left() <= pos.x() <= text_right

    def mousePressEvent(self, event):
        pos = event.position().toPoint()
        if event.button() == Qt.LeftButton and not self._on_name_text(pos):
            self.setFocus()
            self._band_origin = pos + self._scroll_offset()
            self._band_press = QMouseEvent(event)
            self._band_active = False
            self._band_base = {
                id(self.topLevelItem(i)) for i in range(self.topLevelItemCount())
                if self.topLevelItem(i).isSelected()
            } if event.modifiers() & Qt.ControlModifier else set()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._band_origin is None:
            super().mouseMoveEvent(event)
            return
        pos = event.position().toPoint()
        origin = self._band_origin - self._scroll_offset()
        if not self._band_active:
            if (pos - origin).manhattanLength() < QApplication.startDragDistance():
                return
            self._band_active = True
            self._band.show()
        rect = QRect(origin, pos).normalized().intersected(self.viewport().rect())
        self._band.setGeometry(rect)
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            hit = not item.isHidden() and self.visualItemRect(item).intersects(rect)
            want = hit or id(item) in self._band_base
            if item.isSelected() != want:
                item.setSelected(want)
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._band_origin is None:
            super().mouseReleaseEvent(event)
            return
        press, was_band = self._band_press, self._band_active
        self._band_origin = self._band_press = None
        self._band_active = False
        self._band.hide()
        if was_band:
            event.accept()
            return
        # No drag happened: it was a plain click, so replay it normally (selects
        # the row, honours Ctrl/Shift, and fires itemClicked to open it).
        if press is not None:
            super().mousePressEvent(press)
        super().mouseReleaseEvent(event)

    def mimeData(self, items):
        mime = QMimeData()
        paths = [i.data(0, PATH_ROLE) for i in items if i.data(0, PATH_ROLE)]
        mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
        return mime

    def mimeTypes(self):
        return ["text/uri-list"]

    def _target_dir(self, event) -> str:
        item = self.itemAt(event.position().toPoint())
        if item is not None and item.data(0, IS_DIR_ROLE):
            return item.data(0, PATH_ROLE)
        return self.current_dir

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() and self.current_dir:
            event.acceptProposedAction()
            item = self.itemAt(event.position().toPoint())
            if item is not None and (item.data(0, IS_DIR_ROLE) or pdf_tools.is_pdf(item.data(0, PATH_ROLE) or "")):
                self.setCurrentItem(item)
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if not paths or not self.current_dir:
            event.ignore()
            return
        item = self.itemAt(event.position().toPoint())
        if item is not None and not item.data(0, IS_DIR_ROLE):
            target = item.data(0, PATH_ROLE)
            sources = [p for p in paths if p != target]
            if pdf_tools.is_pdf(target) and sources and all(pdf_tools.is_mergeable(p) for p in sources):
                event.setDropAction(Qt.CopyAction)
                event.accept()
                self.pdfsDropped.emit(sources, target)
                return
        mods = event.modifiers()
        if event.source() is self:
            move = not mods & Qt.ControlModifier   # internal drag: move, Ctrl copies
        else:
            move = bool(mods & Qt.ShiftModifier)   # from elsewhere: copy, Shift moves
        event.setDropAction(Qt.MoveAction if move else Qt.CopyAction)
        event.accept()
        self.filesDropped.emit(paths, self._target_dir(event), move)


class FileBrowserView(QWidget):
    navigateInto = Signal(str)
    navigateUp = Signal()
    navigateBack = Signal()
    navigateBreadcrumb = Signal(int)
    closeBrowser = Signal()
    openFile = Signal(str)
    openInExplorer = Signal()
    addToQuickAccess = Signal()
    refreshRequested = Signal()
    statusMessage = Signal(str, bool)  # message, is_error

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(10)

        actions_bar = QHBoxLayout()
        actions_bar.addStretch()

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Type to filter... (* wildcard)")
        self.filter_edit.setFixedWidth(220)
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.filter_edit.installEventFilter(self)
        actions_bar.addWidget(self.filter_edit)

        add_qa_btn = QToolButton()
        add_qa_btn.setText("+ Quick Access")
        add_qa_btn.setToolTip("Add current location to quick access")
        add_qa_btn.clicked.connect(self.addToQuickAccess)
        actions_bar.addWidget(add_qa_btn)

        up_btn = QToolButton()
        up_btn.setText("↑ Up")
        up_btn.clicked.connect(self.navigateUp)
        actions_bar.addWidget(up_btn)

        close_btn = QToolButton()
        close_btn.setText("✕ Close")
        close_btn.clicked.connect(self.closeBrowser)
        actions_bar.addWidget(close_btn)

        explorer_btn = QToolButton()
        explorer_btn.setText("↗")
        explorer_btn.setToolTip("Open in File Explorer")
        explorer_btn.clicked.connect(self.openInExplorer)
        actions_bar.addWidget(explorer_btn)

        layout.addLayout(actions_bar)

        self.breadcrumb = Breadcrumb()
        self.breadcrumb.segmentClicked.connect(self.navigateBreadcrumb)
        self.breadcrumb.backClicked.connect(self.navigateBack)
        layout.addWidget(self.breadcrumb)

        self.tree = FileTree()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Name", "Size", "Modified", ""])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree.setColumnWidth(0, 380)
        self.tree.itemClicked.connect(self._activate_item)
        self._sort_column = 0
        self._sort_ascending = True
        self._data: tuple[list[str], list[dict], str] | None = None
        header = self.tree.header()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(self._sort_column, Qt.AscendingOrder)
        header.sectionClicked.connect(self._on_header_clicked)
        self.tree.installEventFilter(self)
        self.tree.filesDropped.connect(self._on_files_dropped)
        self.tree.pdfsDropped.connect(self._on_pdfs_dropped)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.tree, 1)

        self.pending = pending_deletes.get_manager()
        self.pending.changed.connect(self._refresh_pending_marks)

        for keys, handler in (
            (QKeySequence.Copy, lambda: self.copy_selected(cut=False)),
            (QKeySequence.Cut, lambda: self.copy_selected(cut=True)),
            (QKeySequence.Paste, self.paste),
            (QKeySequence(Qt.Key_Delete), lambda: self.delete_selected(permanent=False)),
            (QKeySequence(Qt.SHIFT | Qt.Key_Delete), lambda: self.delete_selected(permanent=True)),
            (QKeySequence(Qt.Key_F2), self.rename_selected),
            (QKeySequence(Qt.CTRL | Qt.SHIFT | Qt.Key_N), self.new_folder),
            (QKeySequence.SelectAll, self.tree.selectAll),
        ):
            shortcut = QShortcut(keys, self.tree)
            shortcut.setContext(Qt.WidgetShortcut)
            shortcut.activated.connect(handler)

    def _on_header_clicked(self, column: int) -> None:
        if column >= PENDING_COLUMN:
            return
        if column == self._sort_column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column, self._sort_ascending = column, True
        self.tree.header().setSortIndicator(
            self._sort_column, Qt.AscendingOrder if self._sort_ascending else Qt.DescendingOrder
        )
        if self._data is not None:
            self.set_data(*self._data)

    def _sorted(self, items: list[dict]) -> list[dict]:
        """Folders stay on top (as in Explorer); the chosen column orders within each group."""
        by_name = lambda e: e["name"].lower()  # noqa: E731
        key = {
            0: by_name,
            1: lambda e: (e["size"], by_name(e)),
            2: lambda e: (e.get("modified") or "", by_name(e)),
        }[self._sort_column]
        # Folders have no size, so for the Size column they just stay alphabetical.
        folders = sorted((e for e in items if e["isDirectory"]),
                         key=by_name if self._sort_column == 1 else key,
                         reverse=self._sort_ascending is False and self._sort_column != 1)
        files = sorted((e for e in items if not e["isDirectory"]), key=key,
                       reverse=not self._sort_ascending)
        return folders + files

    def set_data(self, history: list[str], items: list[dict], color: str) -> None:
        self._data = (history, items, color)
        items = self._sorted(items)
        self.breadcrumb.set_history(history)
        self.tree.current_dir = history[-1] if history else ""
        self._apply_header_color(color)
        self._apply_selection_style(color)
        self.tree.clear()
        for entry in items:
            icon = "\U0001F4C1" if entry["isDirectory"] else file_icon(entry["name"])
            size_str = "" if entry["isDirectory"] else format_file_size(entry["size"])
            modified_str = format_modified(entry["modified"]) if entry.get("modified") else ""
            tree_item = QTreeWidgetItem([f"{icon}  {entry['name']}", size_str, modified_str, ""])
            tree_item.setData(0, PATH_ROLE, entry["path"])
            tree_item.setData(0, IS_DIR_ROLE, entry["isDirectory"])
            self.tree.addTopLevelItem(tree_item)
        self._refresh_pending_marks()
        self._apply_filter(self.filter_edit.text())

    def _refresh_pending_marks(self) -> None:
        """Tag rows whose delete is waiting on the file being closed."""
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            path = item.data(0, PATH_ROLE)
            marked = bool(path) and self.pending.is_pending(path)
            item.setText(PENDING_COLUMN, PENDING_TEXT if marked else "")
            for col in range(self.tree.columnCount()):
                item.setForeground(col, QBrush(QColor("#c42b1c")) if marked else QBrush())
                font = item.font(col)
                font.setStrikeOut(marked and col == 0)
                item.setFont(col, font)

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
        # Re-assert once the click/keypress that triggered this has finished
        # being processed, in case something grabbed focus back meanwhile.
        QTimer.singleShot(0, self._refocus_filter)

    def _refocus_filter(self) -> None:
        if self.isVisible() and not isinstance(QApplication.focusWidget(), QLineEdit):
            self.filter_edit.setFocus()

    def clear_filter(self) -> None:
        self.filter_edit.clear()

    def has_filter_text(self) -> bool:
        return bool(self.filter_edit.text())

    @staticmethod
    def _filter_pattern(needle: str) -> re.Pattern | None:
        """Build a search pattern from typed text, treating '*' as a
        multi-character wildcard (e.g. "img*2024*raw" matches a name that
        contains those three pieces in order with anything in between).
        Plain text with no '*' behaves as a substring search, same as before."""
        if not needle:
            return None
        parts = [re.escape(part) for part in needle.split("*")]
        return re.compile(".*".join(parts))

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        pattern = self._filter_pattern(needle)
        first_visible_row = -1
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            name = (item.text(0) or "").lower()
            hidden = pattern is not None and not pattern.search(name)
            item.setHidden(hidden)
            if not hidden and first_visible_row == -1:
                first_visible_row = i

        if needle:
            # Keep the selector on the top match as you type, so Enter opens
            # it the moment you've narrowed it down - no need to press Down.
            if first_visible_row >= 0:
                self.tree.setCurrentItem(self.tree.topLevelItem(first_visible_row))
            else:
                self.tree.setCurrentItem(None)

    def _activate_item(self, item: QTreeWidgetItem, _column: int) -> None:
        # Ctrl/Shift-click is multi-select, not "open this".
        if QApplication.keyboardModifiers() & (Qt.ControlModifier | Qt.ShiftModifier):
            return
        path = item.data(0, PATH_ROLE)
        is_dir = item.data(0, IS_DIR_ROLE)
        if path is None:
            return
        if _column == PENDING_COLUMN and self.pending.is_pending(path):
            self.pending.cancel(path)
            self.statusMessage.emit(f"Cancelled scheduled delete: {os.path.basename(path)}", False)
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

        # Handled identically whether the filter box or the list itself has
        # focus, so arrow-key cycling works without ever leaving the search bar.
        if obj in (self.filter_edit, tree) and event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key_Down:
                self.cycle_selection(1)
                return True
            if key == Qt.Key_Up:
                self.cycle_selection(-1)
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                if tree.currentItem() is None:
                    row = self._first_visible_row()
                    if row >= 0:
                        tree.setCurrentItem(tree.topLevelItem(row))
                if tree.currentItem():
                    self._activate_item(tree.currentItem(), 0)
                return True
        return super().eventFilter(obj, event)

    # ---- file operations -----------------------------------------------------
    def _report(self, verb: str, done: int, errors: list[str]) -> None:
        if errors:
            self.statusMessage.emit(f"{verb} failed - " + "; ".join(errors[:3]), True)
        elif done:
            self.statusMessage.emit(f"{verb}: {done} item{'s' if done != 1 else ''}", False)
        self.refreshRequested.emit()

    def copy_selected(self, cut: bool) -> None:
        paths = self.tree.selected_paths()
        if not paths:
            return
        mime = self.tree.mimeData(self.tree.selectedItems())
        # Windows convention: DropEffect 2 = cut (move on paste), 5 = copy.
        mime.setData(DROP_EFFECT_MIME, QByteArray((2 if cut else 5).to_bytes(4, "little")))
        QGuiApplication.clipboard().setMimeData(mime)
        self.statusMessage.emit(f"{'Cut' if cut else 'Copied'} {len(paths)} item(s)", False)

    def paste(self) -> None:
        mime = QGuiApplication.clipboard().mimeData()
        if mime is None or not mime.hasUrls() or not self.tree.current_dir:
            return
        paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
        if not paths:
            return
        move = False
        if mime.hasFormat(DROP_EFFECT_MIME):
            data = bytes(mime.data(DROP_EFFECT_MIME))
            move = bool(data) and int.from_bytes(data[:4], "little") & 2 == 2
        done, errors = fileops.transfer(paths, self.tree.current_dir, move)
        if move and done and not errors:
            QGuiApplication.clipboard().clear()
        self._report("Moved" if move else "Pasted", done, errors)

    def delete_selected(self, permanent: bool) -> None:
        paths = self.tree.selected_paths()
        if not paths:
            return
        names = ", ".join(os.path.basename(p) for p in paths[:3]) + ("..." if len(paths) > 3 else "")
        action = "Permanently delete" if permanent else "Move to Recycle Bin"
        answer = QMessageBox.question(
            self, "Delete", f"{action} {len(paths)} item(s)?\n\n{names}",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        done, errors, locked = fileops.trash_split(paths, permanent)
        if locked:
            self._offer_delete_when_closed(locked, permanent)
        self._report("Deleted", done, errors)

    def _offer_delete_when_closed(self, locked: list[str], permanent: bool) -> None:
        names = ", ".join(os.path.basename(p) for p in locked[:3]) + ("..." if len(locked) > 3 else "")
        apps = sorted({name for p in locked for name, _t in file_locks.holders(p)})
        held_by = f" ({', '.join(apps)})" if apps else ""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("File is open")
        box.setText(
            f"{names} {'is' if len(locked) == 1 else 'are'} open in another program{held_by}.\n\n"
            "Delete automatically once closed?"
        )
        yes = box.addButton("&Yes", QMessageBox.ButtonRole.YesRole)
        close = box.addButton("&Close and delete", QMessageBox.ButtonRole.AcceptRole) \
            if file_locks.available() else None
        no = box.addButton("&No", QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(yes)
        box.setEscapeButton(no)
        box.exec()
        clicked = box.clickedButton()
        if clicked is yes or (close is not None and clicked is close):
            for path in locked:
                self.pending.add(path, permanent, close=clicked is close)
            verb = "Closing and deleting" if clicked is close else "Will delete"
            self.statusMessage.emit(f"{verb} {len(locked)} item(s)" + ("" if clicked is close else " when closed"), False)

    def rename_selected(self) -> None:
        paths = self.tree.selected_paths()
        if len(paths) != 1:
            return
        old = os.path.basename(paths[0])
        new, ok = QInputDialog.getText(self, "Rename", "New name:", text=old)
        if not ok or not new or new == old:
            return
        try:
            fileops.rename(paths[0], new)
            self._report("Renamed", 1, [])
        except OSError as exc:
            self._report("Rename", 0, [f"{old}: {exc}"])

    def new_folder(self) -> None:
        if not self.tree.current_dir:
            return
        name, ok = QInputDialog.getText(self, "New folder", "Folder name:", text="New folder")
        if not ok or not name:
            return
        try:
            fileops.make_folder(self.tree.current_dir, name)
            self._report("Created", 1, [])
        except OSError as exc:
            self._report("Create folder", 0, [str(exc)])

    def _on_files_dropped(self, paths: list, target: str, move: bool) -> None:
        done, errors = fileops.transfer(paths, target, move)
        self._report("Moved" if move else "Copied", done, errors)

    def merge_selected_pdfs(self) -> None:
        paths = [p for p in self.tree.selected_paths() if pdf_tools.is_mergeable(p)]
        if len(paths) < 2:
            return
        dialog = MergeOrderDialog(paths, self.tree.current_dir, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        dest = dialog.output_path()
        QApplication.setOverrideCursor(Qt.WaitCursor)  # Office conversion can take a while
        try:
            pdf_tools.merge_pdfs(dialog.ordered_paths(), dest)
        except Exception as exc:  # noqa: BLE001 - pypdf raises many error types
            self._report("Merge PDFs", 0, [str(exc)])
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.statusMessage.emit(f"Merged {len(paths)} PDFs into {os.path.basename(dest)}", False)
        self.refreshRequested.emit()

    def _on_pdfs_dropped(self, sources: list, target: str) -> None:
        try:
            total = pdf_tools.page_count(target)
            dialog = InsertPositionDialog(target, sources, total, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                pdf_tools.insert_pdfs(target, sources, dialog.after_page())
            finally:
                QApplication.restoreOverrideCursor()
        except Exception as exc:  # noqa: BLE001
            self._report("Add PDF", 0, [f"{os.path.basename(target)}: {exc}"])
            return
        self.statusMessage.emit(f"Added {len(sources)} PDF(s) to {os.path.basename(target)}", False)
        self.refreshRequested.emit()

    def _show_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is not None and not item.isSelected():
            self.tree.setCurrentItem(item)
        has_sel = bool(self.tree.selected_paths())
        menu = QMenu(self)
        entries = [
            ("Cut", "Ctrl+X", lambda: self.copy_selected(True), has_sel),
            ("Copy", "Ctrl+C", lambda: self.copy_selected(False), has_sel),
            ("Paste", "Ctrl+V", self.paste, True),
            None,
            ("Rename", "F2", self.rename_selected, len(self.tree.selected_paths()) == 1),
            ("Delete", "Del", lambda: self.delete_selected(False), has_sel),
        ]
        selected = self.tree.selected_paths()
        if any(self.pending.is_pending(p) for p in selected):
            entries.append((
                "Cancel scheduled delete", "",
                lambda: [self.pending.cancel(p) for p in self.tree.selected_paths()], True,
            ))
        if len([p for p in selected if pdf_tools.is_mergeable(p)]) >= 2:
            entries += [None, ("Merge PDFs...", "", self.merge_selected_pdfs, True)]
        entries += [
            None,
            ("New folder", "Ctrl+Shift+N", self.new_folder, True),
        ]
        for entry in entries:
            if entry is None:
                menu.addSeparator()
                continue
            label, hint, handler, enabled = entry
            action = QAction(f"{label}\t{hint}", menu)
            action.setEnabled(enabled)
            action.triggered.connect(handler)
            menu.addAction(action)
        menu.exec(self.tree.viewport().mapToGlobal(pos))
