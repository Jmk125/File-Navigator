"""Application-wide dark theme (palette + stylesheet)."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

BG = "#1e1e1e"
PANEL = "#2a2a2a"
PANEL_ALT = "#242424"
BORDER = "#444444"
TEXT = "#e0e0e0"
TEXT_BRIGHT = "#ffffff"
MUTED = "#888888"
ACCENT = "#2d5f9f"
ACCENT_HOVER = "#3d7fc0"
SECONDARY = "#444444"
SECONDARY_HOVER = "#555555"
DANGER = "#c42b1c"

STYLESHEET = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-size: 13px;
}}
QLabel {{
    background: transparent;
}}
QLabel#sectionTitle {{
    color: #aaaaaa;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
QLabel#mutedHint {{
    color: {MUTED};
    padding: 12px 0;
}}
QSplitter::handle {{
    background: {BORDER};
}}
QPushButton, QToolButton {{
    background: {SECONDARY};
    color: {TEXT_BRIGHT};
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton:hover, QToolButton:hover {{
    background: {SECONDARY_HOVER};
}}
QPushButton:default {{
    background: {ACCENT};
}}
QPushButton:default:hover {{
    background: {ACCENT_HOVER};
}}
QToolButton:checked {{
    background: {ACCENT};
}}
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 8px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus {{
    border-color: {ACCENT};
}}
QListWidget, QTreeWidget {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 6px;
    outline: none;
}}
QTreeWidget::item, QListWidget::item {{
    padding: 4px;
}}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {ACCENT};
}}
QHeaderView::section {{
    background: {PANEL_ALT};
    color: {TEXT};
    padding: 4px 8px;
    border: none;
    border-bottom: 1px solid {BORDER};
}}
QScrollBar:vertical {{
    background: {BG};
    width: 12px;
}}
QScrollBar:horizontal {{
    background: {BG};
    height: 12px;
}}
QScrollBar::handle {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 24px;
    min-width: 24px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
QDialog {{
    background: {PANEL};
}}
QMessageBox {{
    background: {PANEL};
}}
"""


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(PANEL_ALT))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(SECONDARY))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_BRIGHT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXT_BRIGHT))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(MUTED))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
