"""Progress panel widget displaying live scan status and cancellation controls.

Provides visual feedback on the current scan phase, percentage progress bar,
active file path, and a cancellation button.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class ProgressPanel(QFrame):
    """A progress panel showing the scanning phase, progress bar, file, and cancel button."""

    cancel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self) -> None:
        """Initialize UI components and dark styling."""
        self.setObjectName("progressPanel")
        self.setStyleSheet("""
            QFrame#progressPanel {
                background-color: #202226;
                border: 1px solid #34373e;
                border-radius: 10px;
            }
            QLabel {
                color: #e8e8e8;
                border: none;
            }
            QProgressBar {
                background-color: #2c2f36;
                border: 1px solid #41444c;
                border-radius: 5px;
                text-align: center;
                color: white;
                font-size: 11px;
                font-weight: bold;
                height: 18px;
            }
            QProgressBar::chunk {
                background-color: #3d7bf0;
                border-radius: 4px;
            }
            QPushButton#cancelBtn {
                background-color: #34373e;
                color: #ff958e;
                border: 1px solid #542e30;
                padding: 6px 14px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#cancelBtn:hover {
                background-color: #542e30;
                color: white;
            }
            QPushButton#cancelBtn:disabled {
                background-color: #25272c;
                color: #555860;
                border: 1px solid #303238;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Top row: Phase title, percentage/counts, and Cancel button
        top_row = QHBoxLayout()

        self.phase_label = QLabel("Ready to scan")
        self.phase_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        top_row.addWidget(self.phase_label)

        top_row.addStretch()

        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet("color: #92959c; font-size: 12px;")
        top_row.addWidget(self.detail_label)

        top_row.addSpacing(15)

        self.cancel_button = QPushButton("Cancel Scan")
        self.cancel_button.setObjectName("cancelBtn")
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        top_row.addWidget(self.cancel_button)

        layout.addLayout(top_row)

        # Middle row: Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Bottom row: Current file path
        self.current_item_label = QLabel("")
        self.current_item_label.setStyleSheet("color: #858991; font-size: 11px;")
        self.current_item_label.setWordWrap(False)
        layout.addWidget(self.current_item_label)

    def set_phase(self, phase_text: str) -> None:
        """Update the displayed phase description."""
        self.phase_label.setText(phase_text)

    def update_progress(self, current: int, total: int, item_text: str) -> None:
        """Update progress bar percentage, item count, and active file name."""
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(percent)
            self.detail_label.setText(f"{current:,} / {total:,} files ({percent}%)")
        else:
            # Indeterminate or counting stage (e.g. indexing)
            self.progress_bar.setRange(0, 0)
            self.detail_label.setText(f"{current:,} files discovered")

        # Truncate long file paths with ellipsis if needed
        max_len = 80
        if len(item_text) > max_len:
            truncated = "..." + item_text[-(max_len - 3):]
        else:
            truncated = item_text

        self.current_item_label.setText(truncated)

    def set_indeterminate(self, message: str) -> None:
        """Set progress bar into indeterminate pulse mode."""
        self.progress_bar.setRange(0, 0)
        self.phase_label.setText(message)
        self.current_item_label.setText("")
        self.cancel_button.setEnabled(True)

    def set_completed(self, message: str = "Scan Completed") -> None:
        """Set panel to completed state."""
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.phase_label.setText(message)
        self.cancel_button.setEnabled(False)

    def reset(self) -> None:
        """Reset panel to initial state."""
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.phase_label.setText("Ready to scan")
        self.detail_label.setText("")
        self.current_item_label.setText("")
        self.cancel_button.setEnabled(True)
