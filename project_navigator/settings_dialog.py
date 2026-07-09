"""Settings dialog: theme picker + rebindable hotkeys."""
from __future__ import annotations

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QKeySequenceEdit,
    QLabel, QMessageBox, QPushButton, QVBoxLayout,
)

from .settings import DEFAULT_HOTKEYS, DEFAULT_SETTINGS, HOTKEY_LABELS

THEME_DISPLAY_NAMES = {"dark": "Dark", "medium": "Medium", "light": "Light"}


class SettingsDialog(QDialog):
    def __init__(
        self, parent=None, theme: str = "dark", hotkeys: dict | None = None,
        auto_open_single_quick_folder: bool = True, summon_hotkey_enabled: bool = True,
        summon_hotkey: str = "Ctrl+Alt+F",
    ):
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

        self.auto_open_single_checkbox = QCheckBox("Automatically open the only quick access folder when selecting a project")
        self.auto_open_single_checkbox.setChecked(auto_open_single_quick_folder)
        theme_form.addRow("Single quick access folder", self.auto_open_single_checkbox)

        self.summon_hotkey_enabled_checkbox = QCheckBox("Use a shortcut to show Project Navigator again after hiding it")
        self.summon_hotkey_enabled_checkbox.setChecked(summon_hotkey_enabled)
        theme_form.addRow("Show/hide shortcut", self.summon_hotkey_enabled_checkbox)

        self.summon_hotkey_edit = QKeySequenceEdit(QKeySequence(summon_hotkey or DEFAULT_SETTINGS["summon_hotkey"]))
        self.summon_hotkey_edit.setMaximumSequenceLength(1)
        theme_form.addRow("Shortcut key", self.summon_hotkey_edit)
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
        summon_text = self.summon_hotkey_edit.keySequence().toString()
        if self.summon_hotkey_enabled_checkbox.isChecked() and not summon_text:
            QMessageBox.warning(self, "Missing shortcut", "The show/hide shortcut needs a key assigned.")
            return

        seen: dict[str, str] = {}
        if summon_text:
            seen[summon_text] = "show/hide shortcut"
        for action, edit in self.key_edits.items():
            text = edit.keySequence().toString()
            if not text:
                QMessageBox.warning(self, "Missing hotkey", f'"{HOTKEY_LABELS[action]}" needs a key assigned.')
                return
            if text in seen:
                other = seen[text]
                other_label = HOTKEY_LABELS[other] if other in HOTKEY_LABELS else other
                QMessageBox.warning(
                    self, "Duplicate hotkey",
                    f'"{HOTKEY_LABELS[action]}" and "{other_label}" are both set to "{text}". '
                    "Give each action its own key.",
                )
                return
            seen[text] = action
        self.accept()

    def values(self) -> tuple[str, dict, bool, bool, str]:
        theme = self.theme_combo.currentData()
        hotkeys = {action: edit.keySequence().toString() for action, edit in self.key_edits.items()}
        return (
            theme, hotkeys, self.auto_open_single_checkbox.isChecked(),
            self.summon_hotkey_enabled_checkbox.isChecked(),
            self.summon_hotkey_edit.keySequence().toString(),
        )
