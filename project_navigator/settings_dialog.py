"""Settings dialog: theme picker + rebindable hotkeys."""
from __future__ import annotations

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QKeySequenceEdit,
    QLabel, QMessageBox, QPushButton, QVBoxLayout,
)

from .settings import DEFAULT_HOTKEYS, HOTKEY_LABELS

THEME_DISPLAY_NAMES = {"dark": "Dark", "medium": "Medium", "light": "Light"}


class SettingsDialog(QDialog):
    def __init__(self, parent=None, theme: str = "dark", hotkeys: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        theme_form = QFormLayout()
        self.theme_combo = QComboBox()
        for key, label in THEME_DISPLAY_NAMES.items():
            self.theme_combo.addItem(label, key)
        index = self.theme_combo.findData(theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        theme_form.addRow("Theme", self.theme_combo)
        layout.addLayout(theme_form)

        layout.addWidget(QLabel("Hotkeys"))
        hint = QLabel(
            "Click a field and press a key to rebind it. Folder jump keys (1-9) aren't "
            "listed here - drag a quick-access tile to reorder it and reassign its number. "
            "Arrow keys always cycle the file/folder selector and Enter opens/enters it - "
            "those aren't rebindable either."
        )
        hint.setObjectName("mutedHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.key_edits: dict[str, QKeySequenceEdit] = {}
        hotkeys = hotkeys or DEFAULT_HOTKEYS
        hotkey_form = QFormLayout()
        for action, label in HOTKEY_LABELS.items():
            edit = QKeySequenceEdit(QKeySequence(hotkeys.get(action, DEFAULT_HOTKEYS[action])))
            edit.setMaximumSequenceLength(1)
            self.key_edits[action] = edit
            hotkey_form.addRow(label, edit)
        layout.addLayout(hotkey_form)

        reset_btn = QPushButton("Reset Hotkeys to Defaults")
        reset_btn.setAutoDefault(False)
        reset_btn.clicked.connect(self._reset_hotkeys)
        layout.addWidget(reset_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        buttons.addButton(save_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _reset_hotkeys(self) -> None:
        for action, edit in self.key_edits.items():
            edit.setKeySequence(QKeySequence(DEFAULT_HOTKEYS[action]))

    def _save(self) -> None:
        seen: dict[str, str] = {}
        for action, edit in self.key_edits.items():
            text = edit.keySequence().toString()
            if not text:
                QMessageBox.warning(self, "Missing hotkey", f'"{HOTKEY_LABELS[action]}" needs a key assigned.')
                return
            if text in seen:
                QMessageBox.warning(
                    self, "Duplicate hotkey",
                    f'"{HOTKEY_LABELS[action]}" and "{HOTKEY_LABELS[seen[text]]}" are both set to "{text}". '
                    "Give each action its own key.",
                )
                return
            seen[text] = action
        self.accept()

    def values(self) -> tuple[str, dict]:
        theme = self.theme_combo.currentData()
        hotkeys = {action: edit.keySequence().toString() for action, edit in self.key_edits.items()}
        return theme, hotkeys
