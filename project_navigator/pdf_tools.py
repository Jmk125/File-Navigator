"""PDF merge/insert helpers and the dialogs that ask for ordering and position."""
from __future__ import annotations

import os
import tempfile

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSpinBox, QVBoxLayout,
)

from .fileops import unique_destination


def is_pdf(path: str) -> bool:
    return path.lower().endswith(".pdf") and os.path.isfile(path)


def page_count(path: str) -> int:
    from pypdf import PdfReader
    return len(PdfReader(path).pages)


def _write(writer, dest: str) -> None:
    """Write via a temp file so a failure never leaves a half-written PDF."""
    fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=os.path.dirname(dest) or ".")
    try:
        with os.fdopen(fd, "wb") as handle:
            writer.write(handle)
        os.replace(tmp, dest)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def merge_pdfs(sources: list[str], dest: str) -> None:
    from pypdf import PdfWriter
    writer = PdfWriter()
    for path in sources:
        writer.append(path)
    _write(writer, dest)


def insert_pdfs(target: str, sources: list[str], after_page: int) -> None:
    """Insert `sources` into `target` (in place) after page `after_page` (0 = start)."""
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    total = len(PdfReader(target).pages)
    after_page = max(0, min(after_page, total))
    if after_page > 0:
        writer.append(target, pages=(0, after_page))
    for path in sources:
        writer.append(path)
    if after_page < total:
        writer.append(target, pages=(after_page, total))
    _write(writer, target)


class MergeOrderDialog(QDialog):
    """Pick the order of the PDFs to merge (drag rows or use the buttons)."""

    def __init__(self, paths: list[str], default_dir: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Merge PDFs")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Drag to set the order (top is first), or use the buttons:"))

        row = QHBoxLayout()
        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        for path in paths:
            item = QListWidgetItem(os.path.basename(path))
            item.setData(Qt.UserRole, path)
            item.setToolTip(path)
            self.list.addItem(item)
        self.list.setCurrentRow(0)
        row.addWidget(self.list, 1)

        buttons = QVBoxLayout()
        for label, step in (("↑ Up", -1), ("↓ Down", 1)):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _=False, s=step: self._move(s))
            buttons.addWidget(btn)
        buttons.addStretch()
        row.addLayout(buttons)
        layout.addLayout(row)

        form = QFormLayout()
        self.name_edit = QLineEdit("Merged.pdf")
        form.addRow("Save as", self.name_edit)
        layout.addLayout(form)
        self.default_dir = default_dir

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.button(QDialogButtonBox.Ok).setText("Merge")
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def _move(self, step: int) -> None:
        row = self.list.currentRow()
        new = row + step
        if row < 0 or not 0 <= new < self.list.count():
            return
        item = self.list.takeItem(row)
        self.list.insertItem(new, item)
        self.list.setCurrentRow(new)

    def ordered_paths(self) -> list[str]:
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]

    def output_path(self) -> str:
        name = self.name_edit.text().strip() or "Merged.pdf"
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        return unique_destination(self.default_dir, os.path.basename(name))


class InsertPositionDialog(QDialog):
    """Ask where the dragged PDF(s) should go inside the PDF they were dropped on."""

    def __init__(self, target: str, sources: list[str], total_pages: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add PDF")
        self.setMinimumWidth(420)
        self.total = total_pages
        layout = QVBoxLayout(self)
        names = ", ".join(os.path.basename(p) for p in sources[:3]) + ("..." if len(sources) > 3 else "")
        label = QLabel(
            f"Add <b>{names}</b> to <b>{os.path.basename(target)}</b> "
            f"({total_pages} page{'s' if total_pages != 1 else ''}).<br>"
            "The original file will be updated."
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        form = QFormLayout()
        self.where = QComboBox()
        self.where.addItems(["At the end", "At the beginning", "After a specific page"])
        self.where.currentIndexChanged.connect(self._sync)
        form.addRow("Where", self.where)
        self.page = QSpinBox()
        self.page.setRange(1, max(1, total_pages))
        self.page.setPrefix("page ")
        form.addRow("After", self.page)
        layout.addLayout(form)
        self._sync()

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def _sync(self) -> None:
        self.page.setEnabled(self.where.currentIndex() == 2)

    def after_page(self) -> int:
        index = self.where.currentIndex()
        return self.total if index == 0 else 0 if index == 1 else self.page.value()
