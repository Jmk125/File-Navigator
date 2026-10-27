"""PDF merge/insert helpers and the dialogs that ask for ordering and position."""
from __future__ import annotations

import contextlib
import os
import shutil
import sys
import tempfile

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSpinBox, QVBoxLayout,
)

from .fileops import unique_destination


WORD_EXTS = (".doc", ".docx", ".rtf")
EXCEL_EXTS = (".xls", ".xlsx", ".xlsm", ".xlsb")


def is_pdf(path: str) -> bool:
    return path.lower().endswith(".pdf") and os.path.isfile(path)


def is_mergeable(path: str) -> bool:
    """A PDF, or a Word/Excel file that can be converted to one."""
    return os.path.isfile(path) and path.lower().endswith((".pdf",) + WORD_EXTS + EXCEL_EXTS)


def _convert_office(sources: list[str], out_dir: str) -> dict[str, str]:
    """Convert Word/Excel files to PDF using the installed Microsoft Office."""
    if sys.platform != "win32":
        raise RuntimeError("Converting Word/Excel files needs Microsoft Office on Windows")
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise RuntimeError("Converting Word/Excel files needs the pywin32 package") from exc

    results: dict[str, str] = {}
    pythoncom.CoInitialize()
    apps: dict[str, object] = {}
    try:
        for index, path in enumerate(sources):
            ext = os.path.splitext(path)[1].lower()
            kind = "Word" if ext in WORD_EXTS else "Excel"
            if kind not in apps:
                app = win32com.client.DispatchEx(f"{kind}.Application")  # own instance, not yours
                app.Visible = False
                app.DisplayAlerts = 0
                apps[kind] = app
            app = apps[kind]
            pdf = os.path.join(out_dir, f"{index}_{os.path.splitext(os.path.basename(path))[0]}.pdf")
            doc = None
            try:
                if kind == "Word":
                    doc = app.Documents.Open(os.path.abspath(path), ReadOnly=True, AddToRecentFiles=False)
                    doc.ExportAsFixedFormat(pdf, 17)  # wdExportFormatPDF
                else:
                    doc = app.Workbooks.Open(os.path.abspath(path), ReadOnly=True)
                    doc.ExportAsFixedFormat(0, pdf)  # xlTypePDF
            except Exception as exc:  # noqa: BLE001 - COM errors are opaque
                raise RuntimeError(f"Couldn't convert {os.path.basename(path)}: {exc}") from exc
            finally:
                if doc is not None:
                    doc.Close(False)
            results[path] = pdf
    finally:
        for app in apps.values():
            with contextlib.suppress(Exception):
                app.Quit()
        pythoncom.CoUninitialize()
    return results


@contextlib.contextmanager
def as_pdfs(sources: list[str]):
    """Yield PDF paths for `sources` (same order), converting Office files to temp PDFs."""
    need = [p for p in sources if not p.lower().endswith(".pdf")]
    if not need:
        yield list(sources)
        return
    tmp = tempfile.mkdtemp(prefix="pn_pdf_")
    try:
        converted = _convert_office(need, tmp)
        yield [converted.get(p, p) for p in sources]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
    with as_pdfs(sources) as pdfs:
        for path in pdfs:
            writer.append(path)
        _write(writer, dest)


def insert_pdfs(target: str, sources: list[str], after_page: int) -> None:
    """Insert `sources` into `target` (in place) after page `after_page` (0 = start)."""
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    total = len(PdfReader(target).pages)
    after_page = max(0, min(after_page, total))
    with as_pdfs(sources) as pdfs:
        if after_page > 0:
            writer.append(target, pages=(0, after_page))
        for path in pdfs:
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
            "Word/Excel files are converted to PDF first.<br>The original file will be updated."
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
