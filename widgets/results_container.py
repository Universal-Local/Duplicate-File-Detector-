from PySide6.QtWidgets import QMessageBox
from widgets.action_bar import ActionBar
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QScrollArea
)

from widgets.duplicate_card import DuplicateCard
from data.mock_data import DUPLICATE_GROUPS


class ResultsContainer(QWidget):

    def __init__(self):
        super().__init__()

        # Stores selected files, using their paths as keys.
        self.selected_files = {}

        self.setup_ui()

    def setup_ui(self):

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(15)

        # Heading
        heading = QLabel("Scan Results")
        heading.setStyleSheet("""
            font-size: 26px;
            font-weight: bold;
            color: white;
        """)

        main_layout.addWidget(heading)

        subtitle = QLabel(
            "Review and manage detected duplicate files"
        )
        subtitle.setStyleSheet("color: #92959c;")

        main_layout.addWidget(subtitle)

        # Selection summary
        self.selection_label = QLabel()
        self.selection_label.setStyleSheet(
            "color: #92959c; font-size: 12px;"
        )

        main_layout.addWidget(self.selection_label)

        # Scrollable results area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        results_layout = QVBoxLayout(scroll_content)
        results_layout.setSpacing(15)

        # Create duplicate groups
        for index, group in enumerate(DUPLICATE_GROUPS, start=1):

            group_frame = QFrame()
            group_frame.setStyleSheet("""
                QFrame {
                    background-color: #202226;
                    border: 1px solid #34373e;
                    border-radius: 10px;
                }
            """)

            group_layout = QVBoxLayout(group_frame)
            group_layout.setContentsMargins(12, 12, 12, 12)
            group_layout.setSpacing(12)

            # Group heading
            header = QHBoxLayout()

            group_title = QLabel(
                f'Group {index}: {group["group_name"]}'
            )

            group_title.setStyleSheet("""
                color: white;
                font-size: 14px;
                font-weight: bold;
                border: none;
            """)

            file_count = QLabel(
                f'{len(group["files"])} Files'
            )

            file_count.setStyleSheet("""
                color: #92959c;
                border: none;
            """)

            header.addWidget(group_title)
            header.addStretch()
            header.addWidget(file_count)

            group_layout.addLayout(header)

            # Individual file cards
            cards_layout = QHBoxLayout()
            cards_layout.setSpacing(10)

            for file_data in group["files"]:

                card = DuplicateCard(file_data)

                # Listen for checkbox changes
                card.selection_changed.connect(
                    self.handle_selection_changed
                )

                cards_layout.addWidget(card, 1)

                # Register initially selected duplicates
                if file_data["status"] == "Duplicate":
                    self.selected_files[file_data["path"]] = file_data

            group_layout.addLayout(cards_layout)
            results_layout.addWidget(group_frame)

        results_layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 1)

        # Action bar
        self.action_bar = ActionBar()

        self.action_bar.delete_requested.connect(
            self.handle_mock_delete
        )

        main_layout.addWidget(self.action_bar)

        # Initialise action bar with default selections
        self.action_bar.update_selection(
            list(self.selected_files.values())
        )

        self.update_selection_label()

    def handle_selection_changed(self, checked, file_data):

        file_path = file_data["path"]

        if checked:
            self.selected_files[file_path] = file_data
        else:
            self.selected_files.pop(file_path, None)

        self.update_selection_label()

        self.action_bar.update_selection(
            list(self.selected_files.values())
        )

    def update_selection_label(self):

        count = len(self.selected_files)

        self.selection_label.setText(
            f"{count} duplicate file(s) selected"
        )
    def handle_mock_delete(self, files):

        QMessageBox.information(
            self,
            "Demo Action",
            f"{len(files)} duplicate file(s) selected.\n\n"
            "Actual file deletion will be connected "
            "to the backend later."
        )    