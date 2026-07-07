"""Modal dialogs: add/edit/duplicate project, add current folder to quick access."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)


class ProjectDialog(QDialog):
    def __init__(self, parent=None, title="Add Project", name="", color="#2d5f9f", folders=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.folders = [dict(f) for f in (folders or [])]
        self._show_add_form = False

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText("Lincoln High School")
        form.addRow("Project Name", self.name_edit)

        color_row = QHBoxLayout()
        self.color = color
        self.color_button = QPushButton()
        self.color_button.setFixedSize(40, 24)
        self.color_label = QLabel(color)
        self._update_color_button()
        self.color_button.clicked.connect(self._pick_color)
        color_row.addWidget(self.color_button)
        color_row.addWidget(self.color_label)
        color_row.addStretch()
        form.addRow("Project Color", color_row)
        layout.addLayout(form)

        layout.addWidget(QLabel("Quick Access Locations"))
        hint = QLabel("Add folders from anywhere - PM server, estimating server, local drives, etc.")
        hint.setStyleSheet("color: #888; font-size: 12px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.folder_list = QListWidget()
        self.folder_list.setMaximumHeight(160)
        layout.addWidget(self.folder_list)
        self._refresh_folder_list()

        self.add_location_btn = QPushButton("+ Add Location")
        self.add_location_btn.clicked.connect(self._show_add_location_form)
        layout.addWidget(self.add_location_btn)

        self.add_form_widget = QWidget()
        add_form_layout = QVBoxLayout(self.add_form_widget)
        self.new_name_edit = QLineEdit()
        self.new_name_edit.setPlaceholderText("Location name (e.g., PM - Drawings)")
        self.new_path_edit = QLineEdit()
        self.new_path_edit.setPlaceholderText(r"Full path (e.g., \\server\Projects\Lincoln\Drawings)")
        path_row = QHBoxLayout()
        path_row.addWidget(self.new_path_edit, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_for_folder)
        path_row.addWidget(browse_btn)
        add_form_layout.addWidget(self.new_name_edit)
        add_form_layout.addLayout(path_row)
        form_buttons = QHBoxLayout()
        form_buttons.addStretch()
        cancel_add_btn = QPushButton("Cancel")
        cancel_add_btn.clicked.connect(self._cancel_add_location)
        confirm_add_btn = QPushButton("Add Location")
        confirm_add_btn.clicked.connect(self._confirm_add_location)
        form_buttons.addWidget(cancel_add_btn)
        form_buttons.addWidget(confirm_add_btn)
        add_form_layout.addLayout(form_buttons)
        self.add_form_widget.setVisible(False)
        layout.addWidget(self.add_form_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        save_btn = QPushButton("Save Project")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        buttons.addButton(save_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_color_button(self) -> None:
        self.color_button.setStyleSheet(f"background: {self.color}; border: 1px solid #444; border-radius: 4px;")
        self.color_label.setText(self.color)

    def _pick_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self.color), self, "Project Color")
        if chosen.isValid():
            self.color = chosen.name()
            self._update_color_button()

    def _refresh_folder_list(self) -> None:
        self.folder_list.clear()
        for index, folder in enumerate(self.folders):
            item = QListWidgetItem()
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 2, 4, 2)
            text = QLabel(f"\U0001F4C1 {folder['name']}\n{folder['path']}")
            text.setStyleSheet("font-size: 12px;")
            row_layout.addWidget(text, 1)
            remove_btn = QPushButton("Remove")
            remove_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
            remove_btn.clicked.connect(lambda checked=False, i=index: self._remove_folder(i))
            row_layout.addWidget(remove_btn)
            item.setSizeHint(row.sizeHint())
            self.folder_list.addItem(item)
            self.folder_list.setItemWidget(item, row)

    def _remove_folder(self, index: int) -> None:
        del self.folders[index]
        self._refresh_folder_list()

    def _show_add_location_form(self) -> None:
        self.add_form_widget.setVisible(True)
        self.new_name_edit.setFocus()

    def _cancel_add_location(self) -> None:
        self.new_name_edit.clear()
        self.new_path_edit.clear()
        self.add_form_widget.setVisible(False)

    def _browse_for_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.new_path_edit.setText(os.path.normpath(folder))
            if not self.new_name_edit.text().strip():
                self.new_name_edit.setText(os.path.basename(folder.rstrip("\\/")) or folder)

    def _confirm_add_location(self) -> None:
        name = self.new_name_edit.text().strip()
        path = self.new_path_edit.text().strip()
        if not name or not path:
            QMessageBox.warning(self, "Missing information", "Please enter both name and path")
            return
        self.folders.append({"name": name, "path": path})
        self.new_name_edit.clear()
        self.new_path_edit.clear()
        self.add_form_widget.setVisible(False)
        self._refresh_folder_list()

    def _save(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Missing name", "Please enter a project name")
            return
        if not self.folders:
            QMessageBox.warning(self, "No locations", "Please add at least one quick access location")
            return
        self.accept()

    def values(self) -> tuple[str, str, list[dict]]:
        return self.name_edit.text().strip(), self.color, [dict(f) for f in self.folders]


class QuickAccessDialog(QDialog):
    def __init__(self, parent=None, suggested_name="", path="", projects=None, current_project_id=None):
        super().__init__(parent)
        self.setWindowTitle("Add to Quick Access")
        self.setMinimumWidth(420)
        self.selected_project_id = current_project_id

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(suggested_name)
        form.addRow("Location Name", self.name_edit)
        layout.addLayout(form)

        path_label = QLabel(path)
        path_label.setStyleSheet("color: #888; font-size: 12px; font-family: monospace;")
        path_label.setWordWrap(True)
        layout.addWidget(QLabel("Path"))
        layout.addWidget(path_label)

        layout.addWidget(QLabel("Add to Project"))
        self.project_list = QListWidget()
        for project in projects or []:
            count = len(project.get("quickFolders", []))
            suffix = " (current)" if project["id"] == current_project_id else ""
            item = QListWidgetItem(f"{project['name']}{suffix}  —  {count} location{'s' if count != 1 else ''}")
            item.setData(Qt.UserRole, project["id"])
            self.project_list.addItem(item)
            if project["id"] == current_project_id:
                self.project_list.setCurrentItem(item)
        layout.addWidget(self.project_list)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        add_btn = QPushButton("Add to Project")
        add_btn.setDefault(True)
        add_btn.clicked.connect(self._save)
        buttons.addButton(add_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Missing name", "Please enter a name for this location")
            return
        item = self.project_list.currentItem()
        if not item:
            QMessageBox.warning(self, "No project selected", "Please select a project")
            return
        self.selected_project_id = item.data(Qt.UserRole)
        self.accept()

    def values(self) -> tuple[str, str]:
        return self.name_edit.text().strip(), self.selected_project_id
