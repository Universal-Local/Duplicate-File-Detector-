"""Confirmation dialog for safe Recycle Bin file deletion.

Provides an explicit confirmation prompt displaying the number of files to be
recycled, total recoverable disk space, and an expandable list of target paths.
"""

from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)

from core.models import format_bytes


class DeletionConfirmationDialog(QDialog):
    """Modal dialog requiring explicit user confirmation before moving files to the Recycle Bin."""

    def __init__(self, files_to_delete: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.files_to_delete = files_to_delete
        self.setup_ui()

    def setup_ui(self) -> None:
        """Build and style the confirmation dialog."""
        self.setWindowTitle("Confirm Move to Recycle Bin")
        self.resize(560, 420)
        self.setModal(True)

        self.setStyleSheet("""
            QDialog {
                background-color: #1e2024;
                color: #e8e8e8;
            }
            QLabel {
                color: #e8e8e8;
            }
            QListWidget {
                background-color: #16171a;
                border: 1px solid #34373e;
                border-radius: 6px;
                color: #b5b7bd;
                padding: 6px;
                font-family: "Consolas", monospace;
                font-size: 11px;
            }
            QPushButton#confirmBtn {
                background-color: #a94444;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 13px;
                border: none;
            }
            QPushButton#confirmBtn:hover {
                background-color: #c65353;
            }
            QPushButton#cancelBtn {
                background-color: #34373e;
                color: #e8e8e8;
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 13px;
                border: 1px solid #41444c;
            }
            QPushButton#cancelBtn:hover {
                background-color: #41444c;
                color: white;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Title
        title_label = QLabel("Move Selected Duplicates to Windows Recycle Bin?")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title_label)

        # Summary details
        count = len(self.files_to_delete)
        total_bytes = sum(f.get("size_bytes", 0) for f in self.files_to_delete)
        formatted_space = format_bytes(total_bytes)

        summary_label = QLabel(
            f"You are about to move <b>{count:,} duplicate file(s)</b> ({formatted_space}) "
            "to the <b>Windows Recycle Bin</b>.<br><br>"
            "Retained copies will be safely preserved. Files sent to the Recycle Bin "
            "can be restored later if needed."
        )
        summary_label.setTextFormat(Qt.TextFormat.RichText)
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet("color: #b5b7bd; font-size: 13px;")
        layout.addWidget(summary_label)

        # Files list preview
        list_header = QLabel("Files to be recycled:")
        list_header.setStyleSheet("color: #92959c; font-size: 12px; font-weight: bold;")
        layout.addWidget(list_header)

        self.file_list = QListWidget()
        for f in self.files_to_delete:
            path_str = f.get("path", "")
            size_str = f.get("size", "")
            self.file_list.addItem(f"{path_str} ({size_str})")
        layout.addWidget(self.file_list)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("cancelBtn")
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setDefault(True)
        btn_layout.addWidget(self.cancel_button)

        btn_layout.addSpacing(10)

        self.confirm_button = QPushButton("Move to Recycle Bin")
        self.confirm_button.setObjectName("confirmBtn")
        self.confirm_button.clicked.connect(self.accept)
        btn_layout.addWidget(self.confirm_button)

        layout.addLayout(btn_layout)
