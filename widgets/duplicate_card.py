from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox
)


class DuplicateCard(QFrame):
    selection_changed = Signal(bool, dict)

    def __init__(self, file_data):
        super().__init__()

        self.file_data = file_data
        self.setup_ui()

    def setup_ui(self):

        self.setObjectName("duplicateCard")

        self.setStyleSheet("""
            QFrame#duplicateCard {
                background-color: #292c32;
                border: 1px solid #41444c;
                border-radius: 10px;
            }

            QLabel {
                color: #e8e8e8;
                border: none;
            }

            QCheckBox {
                color: white;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Top row: file name and selection
        top_row = QHBoxLayout()

        name = QLabel(self.file_data["name"])
        name.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
        """)

        top_row.addWidget(name)
        top_row.addStretch()

        if self.file_data["status"] == "Duplicate":
         checkbox = QCheckBox()
         checkbox.setChecked(True)

         checkbox.toggled.connect(
             lambda checked: self.selection_changed.emit(
                 checked, self.file_data
             )
         )

         top_row.addWidget(checkbox)

        layout.addLayout(top_row)

        # Status label
        status = QLabel(self.file_data["status"])

        if self.file_data["status"] == "Keep":
            status.setStyleSheet("""
                color: #75d6aa;
                font-weight: bold;
                background-color: #214b3b;
                padding: 5px;
                border-radius: 5px;
            """)
        else:
            status.setStyleSheet("""
                color: #ff958e;
                font-weight: bold;
                background-color: #542e30;
                padding: 5px;
                border-radius: 5px;
            """)

        layout.addWidget(status, 0)

        # File location
        path = QLabel(self.file_data["path"])
        path.setWordWrap(True)
        path.setStyleSheet("color: #b5b7bd;")

        layout.addWidget(path)

        # File metadata
        metadata = QLabel(
            f'{self.file_data["size"]}  |  '
            f'{self.file_data["date"]}'
        )

        metadata.setStyleSheet("""
            color: #858991;
            font-size: 11px;
        """)

        layout.addWidget(metadata)
