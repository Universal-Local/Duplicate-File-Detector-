
from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout
)

from app.sidebar import Sidebar
from widgets.results_container import ResultsContainer


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Duplicate File Detector")
        self.resize(1200, 750)

        self.setup_ui()

    def setup_ui(self):

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(15)

        # Sidebar
        sidebar = Sidebar()
        main_layout.addWidget(sidebar)

        # Connect sidebar signals
        sidebar.section_changed.connect(
            self.handle_section_change
        )

        sidebar.folder_selected.connect(
            self.handle_folder_selected
        )

        # Results area
        results = ResultsContainer()
        main_layout.addWidget(results, 1)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #17181b;
            }
        """)

    # Sidebar event handlers
    def handle_section_change(self, section):
        print("Selected section:", section)

    def handle_folder_selected(self, folder):
        print("Selected folder:", folder)

