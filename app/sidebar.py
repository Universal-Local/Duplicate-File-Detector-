
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QFileDialog
)

from PySide6.QtCore import Signal


class Sidebar(QWidget):

    # Signals communicate events to other components
    section_changed = Signal(str)
    folder_selected = Signal(str)

    def __init__(self):
        super().__init__()

        self.setFixedWidth(230)

        self.setStyleSheet("""
            Sidebar {
                background-color: #222429;
                border-radius: 10px;
            }

            QLabel {
                color: #eeeeee;
            }

            QPushButton {
                background-color: transparent;
                color: #b5b7bd;
                border: none;
                padding: 12px;
                text-align: left;
                border-radius: 6px;
                font-size: 14px;
            }

            QPushButton:hover {
                background-color: #34373e;
                color: white;
            }
        """)

        self.setup_ui()

    def setup_ui(self):

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 18, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Duplicate Finder")
        title.setStyleSheet("""
            font-size: 19px;
            font-weight: bold;
        """)

        layout.addWidget(title)
        layout.addSpacing(15)

        # Add Folder
        add_folder = QPushButton("+  Add Folder")
        add_folder.clicked.connect(self.open_folder_picker)
        layout.addWidget(add_folder)

        layout.addSpacing(12)

        # Navigation
        self.nav_buttons = {}

        sections = [
            "Downloads",
            "Pictures",
            "Documents",
            "Archive",
            "Settings"
        ]

        for section in sections:

            button = QPushButton(section)

            button.clicked.connect(
                lambda checked=False, name=section:
                self.select_section(name)
            )

            layout.addWidget(button)
            self.nav_buttons[section] = button

        layout.addStretch()

        # Status panel
        status_panel = QFrame()
        status_panel.setStyleSheet("""
            QFrame {
                background-color: #303238;
                border-radius: 8px;
            }
        """)

        status_layout = QVBoxLayout(status_panel)

        status_title = QLabel("Scanning status")
        self.status_value = QLabel("Ready to scan")

        status_title.setStyleSheet("font-weight: bold;")

        status_layout.addWidget(status_title)
        status_layout.addWidget(self.status_value)

        layout.addWidget(status_panel)

        # Initial selection
        self.select_section("Downloads")

    def select_section(self, section):

        for name, button in self.nav_buttons.items():

            if name == section:
                button.setStyleSheet("""
                    background-color: #41444c;
                    color: white;
                    font-weight: bold;
                """)
            else:
                button.setStyleSheet("")

        self.section_changed.emit(section)

    def open_folder_picker(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder"
        )

        if folder:
            self.folder_selected.emit(folder)
            self.status_value.setText("Folder selected")
