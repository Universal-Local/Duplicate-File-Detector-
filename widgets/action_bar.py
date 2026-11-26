"""Action bar for managing batch operations on selected duplicate files.

Displays real-time selection statistics (number of files and recoverable disk space)
and provides the primary trigger for file deletion.
"""

from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from core.models import format_bytes


class ActionBar(QFrame):
    """Floating action bar at the bottom of the scan results view."""

    delete_requested = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_files: List[Dict[str, Any]] = []
        self.setup_ui()

    def setup_ui(self) -> None:
        """Initialize the UI layout and dark styling."""
        self.setStyleSheet("""
            QFrame {
                background-color: #202226;
                border: 1px solid #34373e;
                border-radius: 10px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)

        self.count_label = QLabel("0 files selected")
        self.count_label.setStyleSheet("""
            color: white;
            font-weight: bold;
            font-size: 13px;
            border: none;
        """)

        self.size_label = QLabel("Recoverable space: 0 B")
        self.size_label.setStyleSheet("""
            color: #92959c;
            font-size: 13px;
            border: none;
        """)

        self.delete_button = QPushButton("Delete Selected Duplicates")
        self.delete_button.setEnabled(False)
        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: #a94444;
                color: white;
                padding: 9px 18px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
                border: none;
            }
            QPushButton:disabled {
                background-color: #34373e;
                color: #656870;
            }
            QPushButton:hover:!disabled {
                background-color: #c65353;
            }
        """)

        self.delete_button.clicked.connect(self.request_delete)

        layout.addWidget(self.count_label)
        layout.addSpacing(20)
        layout.addWidget(self.size_label)

        layout.addStretch()

        layout.addWidget(self.delete_button)

    def update_selection(self, selected_files: List[Dict[str, Any]]) -> None:
        """Update displayed selection count and recoverable space from selected files."""
        self.selected_files = selected_files
        count = len(selected_files)

        self.count_label.setText(f"{count} file(s) selected")

        total_bytes = 0
        for file_info in selected_files:
            if "size_bytes" in file_info:
                total_bytes += int(file_info["size_bytes"])
            elif "size" in file_info and isinstance(file_info["size"], str):
                total_bytes += self.parse_size(file_info["size"])

        formatted_size = format_bytes(total_bytes)
        self.size_label.setText(f"Recoverable space: {formatted_size}")
        self.delete_button.setEnabled(count > 0)

    def parse_size(self, size_string: str) -> int:
        """Parse human-readable size string (e.g. '7.2 MB') into bytes."""
        try:
            parts = size_string.strip().split()
            if len(parts) != 2:
                return 0
            val = float(parts[0])
            unit = parts[1].upper()
            multipliers = {
                "B": 1,
                "KB": 1024,
                "MB": 1024 ** 2,
                "GB": 1024 ** 3,
                "TB": 1024 ** 4,
            }
            return int(val * multipliers.get(unit, 1))
        except (ValueError, KeyError):
            return 0

    def request_delete(self) -> None:
        """Emit delete_requested with currently selected files."""
        if self.selected_files:
            self.delete_requested.emit(self.selected_files)
