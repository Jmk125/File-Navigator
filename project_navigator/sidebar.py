"""Left-hand Quick-Access-style pane listing projects."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QStyle, QStyledItemDelegate, QToolButton, QVBoxLayout, QWidget,
)

from . import theme

NAME_ROLE = Qt.UserRole + 1
COLOR_ROLE = Qt.UserRole + 2
ROW_HEIGHT = 44
BUTTON_SIZE = 22
BUTTON_GAP = 4
BUTTON_MARGIN = 8


class ProjectItemDelegate(QStyledItemDelegate):
    """Paints the color swatch + name, and (in edit mode) small action buttons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.edit_mode = False

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), ROW_HEIGHT)

    def button_rects(self, rect):
        actions = ["delete", "edit", "duplicate"]
        rects = {}
        x = rect.right() - BUTTON_MARGIN - BUTTON_SIZE
        y = rect.top() + (rect.height() - BUTTON_SIZE) // 2
        for action in actions:
            rects[action] = _make_rect(x, y, BUTTON_SIZE, BUTTON_SIZE)
            x -= BUTTON_SIZE + BUTTON_GAP
        return rects

    def hit_test(self, rect, pos):
        if not self.edit_mode:
            return None
        for action, r in self.button_rects(rect).items():
            if r.contains(pos):
                return action
        return None

    def paint(self, painter: QPainter, option, index):
        painter.save()
        rect = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        color = QColor(index.data(COLOR_ROLE) or "#2d5f9f")

        if selected:
            # QColor's 8-digit hex string constructor expects #AARRGGBB, not
            # CSS's #RRGGBBAA - use setAlpha() to avoid misparsing the color.
            highlight = QColor(color)
            highlight.setAlpha(64)
            painter.fillRect(rect, highlight)

        swatch = _make_rect(rect.left() + 8, rect.top() + 8, 4, rect.height() - 16)
        painter.fillRect(swatch, color)

        name = index.data(NAME_ROLE) or ""
        text_left = rect.left() + 22
        text_right = rect.right() - BUTTON_MARGIN
        if self.edit_mode:
            text_right = min(text_right, min(r.left() for r in self.button_rects(rect).values()) - 8)

        colors = theme.current()
        painter.setPen(QColor(colors["TEXT"]))
        metrics = QFontMetrics(painter.font())
        elided = metrics.elidedText(name, Qt.ElideRight, max(10, text_right - text_left))
        text_rect = _make_rect(text_left, rect.top(), max(10, text_right - text_left), rect.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)

        if self.edit_mode:
            glyphs = {"duplicate": "⧉", "edit": "✎", "delete": "\U0001F5D1"}
            for action, r in self.button_rects(rect).items():
                painter.setPen(QColor(colors["MUTED"]))
                painter.drawText(r, Qt.AlignCenter, glyphs[action])

        painter.restore()


def _make_rect(x, y, w, h):
    from PySide6.QtCore import QRect
    return QRect(x, y, w, h)


class ProjectListWidget(QListWidget):
    projectActivated = Signal(str)
    editRequested = Signal(str)
    duplicateRequested = Signal(str)
    deleteRequested = Signal(str)
    reordered = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setUniformItemSizes(True)
        self._delegate = ProjectItemDelegate(self)
        self.setItemDelegate(self._delegate)
        self.setFrameShape(self.Shape.NoFrame)
        self.setFocusPolicy(Qt.NoFocus)
        # The delegate paints selection itself (in the project's own color);
        # suppress the app-wide QSS/palette selection tint so it doesn't show
        # through underneath as a mismatched color.
        self.setStyleSheet(
            "QListWidget::item { border: none; }"
            "QListWidget::item:selected, QListWidget::item:hover { background: transparent; }"
        )

    def set_edit_mode(self, on: bool) -> None:
        self._delegate.edit_mode = on
        self.viewport().update()

    def set_projects(self, projects: list[dict], selected_id: str | None) -> None:
        self.blockSignals(True)
        self.clear()
        for project in projects:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, project["id"])
            item.setData(NAME_ROLE, project["name"])
            item.setData(COLOR_ROLE, project["color"])
            item.setSizeHint(QSize(0, ROW_HEIGHT))
            self.addItem(item)
            if project["id"] == selected_id:
                self.setCurrentItem(item)
        self.blockSignals(False)

    def mousePressEvent(self, event) -> None:
        item = self.itemAt(event.pos())
        if item is not None:
            rect = self.visualItemRect(item)
            action = self._delegate.hit_test(rect, event.pos())
            if action:
                pid = item.data(Qt.UserRole)
                if action == "edit":
                    self.editRequested.emit(pid)
                elif action == "duplicate":
                    self.duplicateRequested.emit(pid)
                elif action == "delete":
                    self.deleteRequested.emit(pid)
                return
        super().mousePressEvent(event)
        if item is not None:
            self.projectActivated.emit(item.data(Qt.UserRole))

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        ids = [self.item(i).data(Qt.UserRole) for i in range(self.count())]
        self.reordered.emit(ids)


class SidebarWidget(QWidget):
    addProjectClicked = Signal()
    settingsClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("Projects")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()

        self.settings_button = QToolButton()
        self.settings_button.setText("⚙")
        self.settings_button.setToolTip("Settings (theme, hotkeys)")
        self.settings_button.setAutoRaise(True)
        self.settings_button.clicked.connect(self.settingsClicked)
        header.addWidget(self.settings_button)

        self.edit_toggle = QToolButton()
        self.edit_toggle.setText("✎")
        self.edit_toggle.setToolTip("Show edit / duplicate / delete controls")
        self.edit_toggle.setCheckable(True)
        self.edit_toggle.setAutoRaise(True)
        header.addWidget(self.edit_toggle)

        add_button = QToolButton()
        add_button.setText("+")
        add_button.setToolTip("Add project")
        add_button.setAutoRaise(True)
        add_button.clicked.connect(self.addProjectClicked)
        header.addWidget(add_button)

        layout.addLayout(header)

        self.list = ProjectListWidget()
        self.edit_toggle.toggled.connect(self.list.set_edit_mode)
        layout.addWidget(self.list, 1)

    def set_projects(self, projects: list[dict], selected_id: str | None) -> None:
        self.list.set_projects(projects, selected_id)
