"""Left-hand Quick-Access-style pane listing projects."""
from __future__ import annotations

import os

from PySide6.QtCore import QSize, QStandardPaths, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QListWidget, QListWidgetItem, QMenu,
    QStackedWidget, QStyle, QStyledItemDelegate, QToolButton, QVBoxLayout, QWidget,
)

from . import storage, theme

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
        self.show_hotkeys = False

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
        base_font = painter.font()
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
        hotkey = index.row() + 1
        if self.show_hotkeys and hotkey <= 9:
            badge_rect = _make_rect(rect.left() + 18, rect.top() + (rect.height() - 18) // 2, 18, 18)
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
            painter.setFont(base_font)
            text_left = badge_rect.right() + 8
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
        # itemClicked only fires for a genuine click (Qt itself withholds it
        # once a press turns into a drag past the drag-start threshold), so
        # activation naturally leaves drag-to-reorder alone. Emitting this
        # from mousePressEvent instead would rebuild the whole list mid-press
        # (see below) and corrupt Qt's in-progress drag tracking.
        self.itemClicked.connect(lambda item: self.projectActivated.emit(item.data(Qt.UserRole)))

    def set_edit_mode(self, on: bool) -> None:
        self._delegate.edit_mode = on
        self.viewport().update()

    def set_projects(self, projects: list[dict], selected_id: str | None) -> None:
        # Project jump-hotkeys (1-9) only apply when nothing is selected yet -
        # once you're in a project, those keys belong to its quick access
        # folders instead, so hide the badges to match.
        self._delegate.show_hotkeys = selected_id is None
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

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        ids = [self.item(i).data(Qt.UserRole) for i in range(self.count())]
        self.reordered.emit(ids)


_STANDARD_FOLDERS = (
    ("Home", QStandardPaths.HomeLocation),
    ("Desktop", QStandardPaths.DesktopLocation),
    ("Documents", QStandardPaths.DocumentsLocation),
    ("Downloads", QStandardPaths.DownloadLocation),
    ("Pictures", QStandardPaths.PicturesLocation),
    ("Music", QStandardPaths.MusicLocation),
    ("Videos", QStandardPaths.MoviesLocation),
)


def standard_locations() -> list[tuple[str, str]]:
    """The fixed Quick Access entries (only folders that actually exist)."""
    found = []
    for name, location in _STANDARD_FOLDERS:
        path = QStandardPaths.writableLocation(location)
        if path and os.path.isdir(path):
            found.append((name, os.path.normpath(path)))
    return found


def _same_or_inside(path: str, root: str) -> bool:
    path, root = os.path.normcase(os.path.normpath(path)), os.path.normcase(os.path.normpath(root))
    prefix = root.rstrip("\\/") + os.sep
    return path == root or path.startswith(prefix)


class LocationListWidget(QListWidget):
    """Traditional-view left pane: fixed Quick Access, your own locations, drives."""
    locationActivated = Signal(str)
    renameRequested = Signal(str)
    removeRequested = Signal(str)

    PATH_ROLE = Qt.UserRole
    CUSTOM_ROLE = Qt.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFrameShape(self.Shape.NoFrame)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)
        self.itemClicked.connect(self._on_clicked)

    def _on_clicked(self, item) -> None:
        path = item.data(self.PATH_ROLE)
        if path:
            self.locationActivated.emit(path)

    def _add_header(self, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.NoItemFlags)
        font = item.font()
        font.setPointSize(8)
        font.setBold(True)
        item.setFont(font)
        item.setForeground(QColor(theme.current()["MUTED"]))
        item.setSizeHint(QSize(0, 30))
        self.addItem(item)

    def _add_location(self, icon: str, name: str, path: str, custom: bool = False) -> None:
        item = QListWidgetItem(f"{icon}  {name}")
        item.setData(self.PATH_ROLE, path)
        item.setData(self.CUSTOM_ROLE, custom)
        item.setToolTip(path)
        item.setSizeHint(QSize(0, 32))
        self.addItem(item)

    def set_locations(self, quick: list, custom: list, drives: list, active_path: str | None) -> None:
        self.blockSignals(True)
        self.clear()
        self._add_header("QUICK ACCESS")
        for name, path in quick:
            self._add_location("\U0001F4C1", name, path)
        if custom:
            self._add_header("MY LOCATIONS")
            for loc in custom:
                is_unc = loc["path"].startswith(("\\\\", "//"))
                self._add_location("\U0001F310" if is_unc else "\U0001F4C1", loc["name"], loc["path"], custom=True)
        self._add_header("THIS PC")
        for drive in drives:
            self._add_location("\U0001F4BD", drive, drive)
        self.blockSignals(False)
        self.set_active(active_path)

    def set_active(self, path: str | None) -> None:
        """Highlight the most specific location containing `path`."""
        best, best_len = None, -1
        for row in range(self.count()):
            item = self.item(row)
            root = item.data(self.PATH_ROLE)
            if path and root and _same_or_inside(path, root) and len(root) > best_len:
                best, best_len = item, len(root)
        self.blockSignals(True)
        if best is not None:
            self.setCurrentItem(best)
        else:
            self.clearSelection()
            self.setCurrentItem(None)
        self.blockSignals(False)

    def _show_menu(self, pos) -> None:
        item = self.itemAt(pos)
        if item is None or not item.data(self.CUSTOM_ROLE):
            return
        path = item.data(self.PATH_ROLE)
        menu = QMenu(self)
        rename = menu.addAction("Rename...")
        remove = menu.addAction("Remove from My Locations")
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen is rename:
            self.renameRequested.emit(path)
        elif chosen is remove:
            self.removeRequested.emit(path)


class SidebarWidget(QWidget):
    addProjectClicked = Signal()
    settingsClicked = Signal()
    viewToggleClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        # Doubles as the Projects <-> Traditional view switch; styled to look
        # like the plain section label it replaced.
        self.title_button = QToolButton()
        self.title_button.setObjectName("viewToggle")
        self.title_button.setText("Projects")
        self.title_button.setToolTip("Click to switch to Traditional view")
        self.title_button.setCursor(Qt.PointingHandCursor)
        self.title_button.setAutoRaise(True)
        self.title_button.clicked.connect(self.viewToggleClicked)
        header.addWidget(self.title_button)
        header.addStretch()

        self.settings_button = QToolButton()
        self.settings_button.setText("⚙")
        self.settings_button.setToolTip("Settings (theme, hotkeys, view)")
        self.settings_button.setAutoRaise(True)
        self.settings_button.clicked.connect(self.settingsClicked)
        header.addWidget(self.settings_button)

        self.edit_toggle = QToolButton()
        self.edit_toggle.setText("✎")
        self.edit_toggle.setToolTip("Show edit / duplicate / delete controls")
        self.edit_toggle.setCheckable(True)
        self.edit_toggle.setAutoRaise(True)
        header.addWidget(self.edit_toggle)

        self.add_button = QToolButton()
        self.add_button.setText("+")
        self.add_button.setToolTip("Add project")
        self.add_button.setAutoRaise(True)
        self.add_button.clicked.connect(self.addProjectClicked)
        header.addWidget(self.add_button)

        layout.addLayout(header)

        self.list = ProjectListWidget()
        self.edit_toggle.toggled.connect(self.list.set_edit_mode)

        self.locations = LocationListWidget()

        self.stack = QStackedWidget()
        self.stack.addWidget(self.list)
        self.stack.addWidget(self.locations)
        layout.addWidget(self.stack, 1)

    def set_projects(self, projects: list[dict], selected_id: str | None) -> None:
        self.list.set_projects(projects, selected_id)

    def set_locations(self, custom: list, active_path: str | None) -> None:
        self.locations.set_locations(standard_locations(), custom, storage.list_drives(), active_path)

    def set_mode(self, mode: str) -> None:
        traditional = mode == "traditional"
        self.title_button.setText("Traditional" if traditional else "Projects")
        self.title_button.setToolTip(
            "Click to switch to Projects view" if traditional else "Click to switch to Traditional view"
        )
        self.add_button.setToolTip("Add location" if traditional else "Add project")
        self.edit_toggle.setVisible(not traditional)
        self.stack.setCurrentWidget(self.locations if traditional else self.list)
