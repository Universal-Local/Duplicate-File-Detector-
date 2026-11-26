"""Duplicate file card widget.

Presents details for an individual file within a duplicate group, including its name,
path, size, modification date, and retention status (Keep vs Duplicate).
Enables the user to switch the retained copy or toggle deletion selection.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class DuplicateCard(QFrame):
    """Card widget representing a single file inside a duplicate group."""

    selection_changed = Signal(bool, dict)      # (checked: bool, file_data: dict)
    set_as_keep_requested = Signal(dict)        # (file_data: dict)

    def __init__(self, file_data: dict, parent=None):
        super().__init__(parent)
        self.file_data = file_data
        self.setup_ui()

    def setup_ui(self) -> None:
        """Build and style the card UI."""
        self.setObjectName("duplicateCard")
        self.setMinimumWidth(240)

        is_keep = (self.file_data.get("status") == "Keep")

        border_color = "#2e6852" if is_keep else "#41444c"
        self.setStyleSheet(f"""
            QFrame#duplicateCard {{
                background-color: #292c32;
                border: 1px solid {border_color};
                border-radius: 10px;
            }}
            QLabel {{
                color: #e8e8e8;
                border: none;
            }}
            QCheckBox {{
                color: white;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #5a5e69;
                background-color: #1f2126;
            }}
            QCheckBox::indicator:checked {{
                background-color: #a94444;
                border: 1px solid #d9534f;
            }}
            QPushButton#keepBtn {{
                background-color: #34373e;
                color: #75d6aa;
                border: 1px solid #2e6852;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton#keepBtn:hover {{
                background-color: #214b3b;
                color: #ffffff;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Top row: File name and Checkbox (or Keep star)
        top_row = QHBoxLayout()

        name = QLabel(self.file_data.get("name", "Unknown File"))
        name.setStyleSheet("font-size: 13px; font-weight: bold;")
        top_row.addWidget(name, 1)

        if not is_keep:
            self.checkbox = QCheckBox()
            self.checkbox.setToolTip("Mark for deletion")
            # Default to checked for deletion if status is Duplicate
            self.checkbox.setChecked(True)
            self.checkbox.toggled.connect(
                lambda checked: self.selection_changed.emit(checked, self.file_data)
            )
            top_row.addWidget(self.checkbox)
        else:
            self.checkbox = None
            star_label = QLabel("★ Retained")
            star_label.setStyleSheet("color: #75d6aa; font-size: 11px; font-weight: bold;")
            top_row.addWidget(star_label)

        layout.addLayout(top_row)

        # Status badge and "Keep this copy" action button
        badge_row = QHBoxLayout()

        status = QLabel(self.file_data.get("status", "Duplicate"))
        if is_keep:
            status.setStyleSheet("""
                color: #75d6aa;
                font-weight: bold;
                background-color: #214b3b;
                padding: 3px 8px;
                border-radius: 4px;
                font-size: 11px;
            """)
        else:
            status.setStyleSheet("""
                color: #ff958e;
                font-weight: bold;
                background-color: #542e30;
                padding: 3px 8px;
                border-radius: 4px;
                font-size: 11px;
            """)
        badge_row.addWidget(status)
        badge_row.addStretch()

        if not is_keep:
            keep_btn = QPushButton("Keep This Copy")
            keep_btn.setObjectName("keepBtn")
            keep_btn.setToolTip("Designate this copy to be retained and mark others as duplicates")
            keep_btn.clicked.connect(lambda: self.set_as_keep_requested.emit(self.file_data))
            badge_row.addWidget(keep_btn)

        layout.addLayout(badge_row)

        # File path
        path_str = self.file_data.get("path", "")
        path_label = QLabel(path_str)
        path_label.setWordWrap(True)
        path_label.setStyleSheet("color: #b5b7bd; font-size: 11px;")
        layout.addWidget(path_label)

        # Metadata (Size and Modified Date)
        size_str = self.file_data.get("size", "")
        date_str = self.file_data.get("date", "")
        metadata = QLabel(f"{size_str}  |  {date_str}")
        metadata.setStyleSheet("color: #858991; font-size: 11px;")
        layout.addWidget(metadata)

    def is_selected_for_delete(self) -> bool:
        """Returns True if the card is marked for deletion."""
        if self.checkbox and self.checkbox.isChecked():
            return True
        return False

    def set_selected_for_delete(self, selected: bool) -> None:
        """Programmatically check or uncheck deletion box."""
        if self.checkbox:
            self.checkbox.setChecked(selected)
