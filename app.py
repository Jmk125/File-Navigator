"""
Project Navigator - native desktop app (PySide6)

A traditional file-explorer-style UI for jumping straight to the folders you
care about, organized by project. No browser, no local web server - this is
a plain Qt desktop application, built into a .exe with PyInstaller.
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from project_navigator.main_window import MainWindow
from project_navigator.settings import load_settings
from project_navigator.theme import apply_theme

APP_NAME = "Project Navigator"


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    apply_theme(app, load_settings()["theme"])
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
