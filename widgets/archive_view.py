"""Archive and scan history view.

Displays records of past scans, inspected directories, duplicate counts,
and space recovered.
"""

from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class ArchiveView(QWidget):
    """View presenting past scan records and summary activity logs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history_records: List[Dict[str, Any]] = []
        self.setup_ui()

    def setup_ui(self) -> None:
        """Initialize UI layout and dark styling."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(15)

        # Header
        header = QVBoxLayout()
        header.setSpacing(4)

        title = QLabel("Scan History & Archive")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        header.addWidget(title)

        subtitle = QLabel("Activity records and summaries of previous duplicate scans.")
        subtitle.setStyleSheet("color: #92959c; font-size: 13px;")
        header.addWidget(subtitle)

        main_layout.addLayout(header)

        # Scrollable list
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.content_widget = QWidget()
        self.list_layout = QVBoxLayout(self.content_widget)
        self.list_layout.setSpacing(10)

        self.scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll_area, 1)

        self.render_empty_state()

    def render_empty_state(self) -> None:
        """Display placeholder when no history records exist."""
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        empty_frame = QFrame()
        empty_frame.setStyleSheet("""
            QFrame {
                background-color: #202226;
                border: 1px dashed #34373e;
                border-radius: 12px;
                padding: 40px;
            }
        """)
        empty_layout = QVBoxLayout(empty_frame)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(10)

        icon = QLabel("📁")
        icon.setStyleSheet("font-size: 36px; border: none;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(icon)

        title = QLabel("No Scan History Recorded")
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(title)

        desc = QLabel("Completed scans and cleanups will be logged here.")
        desc.setStyleSheet("color: #92959c; font-size: 13px; border: none;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(desc)

        self.list_layout.addWidget(empty_frame)
        self.list_layout.addStretch()

    def add_record(self, folder_path: str, stats_desc: str, date_str: str) -> None:
        """Add a completed scan entry to the history log."""
        if not self.history_records:
            # Clear empty frame
            while self.list_layout.count():
                item = self.list_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        record = {"folder": folder_path, "stats": stats_desc, "date": date_str}
        self.history_records.append(record)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #202226;
                border: 1px solid #34373e;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        folder_lbl = QLabel(folder_path)
        folder_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px; border: none;")
        date_lbl = QLabel(date_str)
        date_lbl.setStyleSheet("color: #858991; font-size: 11px; border: none;")
        top_row.addWidget(folder_lbl)
        top_row.addStretch()
        top_row.addWidget(date_lbl)
        layout.addLayout(top_row)

        stats_lbl = QLabel(stats_desc)
        stats_lbl.setStyleSheet("color: #b5b7bd; font-size: 12px; border: none;")
        layout.addWidget(stats_lbl)

        self.list_layout.insertWidget(0, card)
