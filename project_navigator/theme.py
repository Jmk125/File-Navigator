"""Application-wide theming: three palettes (dark/medium/light), applied via
QPalette + a generated stylesheet. Custom-painted widgets (delegates) can't
be reached by stylesheets, so they read colors from `current()` at paint time."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

THEMES = {
    "dark": dict(
        BG="#1e1e1e", PANEL="#2a2a2a", PANEL_ALT="#242424", BORDER="#444444",
        TEXT="#e0e0e0", MUTED="#9a9a9a",
        ACCENT="#2d5f9f", ACCENT_HOVER="#3d7fc0",
        SECONDARY="#444444", SECONDARY_HOVER="#555555",
        BUTTON_TEXT="#f0f0f0", ON_ACCENT_TEXT="#ffffff",
    ),
    "medium": dict(
        BG="#3a3a3a", PANEL="#454545", PANEL_ALT="#404040", BORDER="#5c5c5c",
        TEXT="#eaeaea", MUTED="#bdbdbd",
        ACCENT="#4a7fc9", ACCENT_HOVER="#5c93de",
        SECONDARY="#555555", SECONDARY_HOVER="#666666",
        BUTTON_TEXT="#f5f5f5", ON_ACCENT_TEXT="#ffffff",
    ),
    "light": dict(
        BG="#f4f4f4", PANEL="#ffffff", PANEL_ALT="#ececec", BORDER="#cccccc",
        TEXT="#202020", MUTED="#5c5c5c",
        ACCENT="#2d5f9f", ACCENT_HOVER="#1f4d86",
        SECONDARY="#e2e2e2", SECONDARY_HOVER="#d3d3d3",
        BUTTON_TEXT="#202020", ON_ACCENT_TEXT="#ffffff",
    ),
}

CURRENT_NAME = "dark"
CURRENT = THEMES[CURRENT_NAME]


def current() -> dict:
    return CURRENT


def _build_stylesheet(c: dict) -> str:
    return f"""
QWidget {{
    background-color: {c['BG']};
    color: {c['TEXT']};
    font-size: 13px;
}}
QLabel {{
    background: transparent;
}}
QLabel#sectionTitle {{
    color: {c['MUTED']};
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
QLabel#mutedHint {{
    color: {c['MUTED']};
    padding: 12px 0;
}}
QSplitter::handle {{
    background: {c['BORDER']};
}}
QPushButton, QToolButton {{
    background: {c['SECONDARY']};
    color: {c['BUTTON_TEXT']};
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton:hover, QToolButton:hover {{
    background: {c['SECONDARY_HOVER']};
}}
QPushButton:default {{
    background: {c['ACCENT']};
    color: {c['ON_ACCENT_TEXT']};
}}
QPushButton:default:hover {{
    background: {c['ACCENT_HOVER']};
}}
QToolButton:checked {{
    background: {c['ACCENT']};
    color: {c['ON_ACCENT_TEXT']};
}}
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {c['BG']};
    border: 1px solid {c['BORDER']};
    border-radius: 4px;
    padding: 6px 8px;
    color: {c['TEXT']};
    selection-background-color: {c['ACCENT']};
    selection-color: {c['ON_ACCENT_TEXT']};
}}
QLineEdit:focus {{
    border-color: {c['ACCENT']};
}}
QListWidget, QTreeWidget {{
    background: {c['PANEL']};
    border: 1px solid {c['BORDER']};
    border-radius: 6px;
    outline: none;
}}
QTreeWidget::item, QListWidget::item {{
    padding: 4px;
}}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {c['ACCENT']};
    color: {c['ON_ACCENT_TEXT']};
}}
QHeaderView::section {{
    background: {c['PANEL_ALT']};
    color: {c['TEXT']};
    padding: 4px 8px;
    border: none;
    border-bottom: 1px solid {c['BORDER']};
}}
QScrollBar:vertical {{
    background: {c['BG']};
    width: 12px;
}}
QScrollBar:horizontal {{
    background: {c['BG']};
    height: 12px;
}}
QScrollBar::handle {{
    background: {c['BORDER']};
    border-radius: 5px;
    min-height: 24px;
    min-width: 24px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
QDialog {{
    background: {c['PANEL']};
}}
QMessageBox {{
    background: {c['PANEL']};
}}
QComboBox {{
    background: {c['SECONDARY']};
    color: {c['BUTTON_TEXT']};
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
}}
QKeySequenceEdit {{
    background: {c['BG']};
    border: 1px solid {c['BORDER']};
    border-radius: 4px;
    padding: 4px 8px;
    color: {c['TEXT']};
}}
"""


def apply_theme(app: QApplication, name: str = "dark") -> None:
    global CURRENT_NAME, CURRENT
    c = THEMES.get(name, THEMES["dark"])
    CURRENT_NAME = name if name in THEMES else "dark"
    CURRENT = c

    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(c["BG"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(c["TEXT"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(c["PANEL"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(c["PANEL_ALT"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(c["TEXT"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(c["SECONDARY"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(c["BUTTON_TEXT"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(c["ACCENT"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(c["ON_ACCENT_TEXT"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(c["PANEL"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(c["TEXT"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(c["MUTED"]))
    app.setPalette(palette)
    app.setStyleSheet(_build_stylesheet(c))
