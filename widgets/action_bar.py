
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton
)


class ActionBar(QFrame):

    delete_requested = Signal(list)

    def __init__(self):
        super().__init__()

        self.selected_files = []

        self.setup_ui()

    def setup_ui(self):

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
            border: none;
        """)

        self.size_label = QLabel("Estimated space: 0 MB")
        self.size_label.setStyleSheet("""
            color: #92959c;
            border: none;
        """)

        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.setEnabled(False)

        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: #a94444;
                color: white;
                padding: 9px 18px;
                border-radius: 6px;
                font-weight: bold;
            }

            QPushButton:disabled {
                background-color: #45464b;
                color: #92959c;
            }

            QPushButton:hover:!disabled {
                background-color: #c65353;
            }
        """)

        self.delete_button.clicked.connect(
            self.request_delete
        )

        layout.addWidget(self.count_label)
        layout.addSpacing(20)
        layout.addWidget(self.size_label)

        layout.addStretch()

        layout.addWidget(self.delete_button)

    def update_selection(self, selected_files):

        self.selected_files = selected_files

        count = len(selected_files)

        self.count_label.setText(
            f"{count} file(s) selected"
        )

        total_bytes = sum(
            self.parse_size(file["size"])
            for file in selected_files
        )

        size_mb = total_bytes / (1024 * 1024)

        self.size_label.setText(
            f"Estimated space: {size_mb:.2f} MB"
        )

        self.delete_button.setEnabled(count > 0)

    def parse_size(self, size_string):

        value, unit = size_string.split()

        value = float(value)

        multipliers = {
            "KB": 1024,
            "MB": 1024 ** 2,
            "GB": 1024 ** 3
        }

        return int(value * multipliers[unit.upper()])

    def request_delete(self):

        if self.selected_files:
            self.delete_requested.emit(
                self.selected_files
            )
