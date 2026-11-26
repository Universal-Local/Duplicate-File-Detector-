"""Dynamic results container for displaying duplicate file groups.

Renders duplicate groups, provides batch heuristic selectors ('Keep Oldest',
'Keep Newest', 'Keep Shortest Path'), supports individual copy retention toggles,
dynamically tracks recoverable storage, and synchronizes state after file recycling.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.models import DeletionResult, DuplicateGroup, FileStatus, ScanStats, format_bytes
from widgets.action_bar import ActionBar
from widgets.duplicate_card import DuplicateCard
from widgets.progress_panel import ProgressPanel


class ResultsContainer(QWidget):
    """Main results panel managing scan progress, duplicate group cards, and actions."""

    # Forward delete request for MainWindow / DeleteWorker handling
    delete_requested = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.duplicate_groups: List[DuplicateGroup] = []
        self.selected_files: Dict[str, Dict[str, Any]] = {}
        self.group_card_widgets: Dict[str, List[DuplicateCard]] = {}
        self.group_frames: Dict[str, QFrame] = {}
        self.setup_ui()

    def setup_ui(self) -> None:
        """Initialize base UI containers."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        # Header Section
        self.header_widget = QWidget()
        header_layout = QVBoxLayout(self.header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        self.heading = QLabel("Duplicate Detection")
        self.heading.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        header_layout.addWidget(self.heading)

        self.subtitle = QLabel("Select a folder to start scanning for duplicate files.")
        self.subtitle.setStyleSheet("color: #92959c; font-size: 13px;")
        header_layout.addWidget(self.subtitle)

        main_layout.addWidget(self.header_widget)

        # Progress Panel (Hidden by default, displayed during active scans)
        self.progress_panel = ProgressPanel()
        self.progress_panel.setVisible(False)
        main_layout.addWidget(self.progress_panel)

        # Batch Operations Toolbar (Hidden until results are available)
        self.batch_toolbar = QFrame()
        self.batch_toolbar.setStyleSheet("""
            QFrame {
                background-color: #1f2126;
                border: 1px solid #34373e;
                border-radius: 8px;
            }
            QPushButton {
                background-color: #2c2f36;
                color: #e8e8e8;
                border: 1px solid #41444c;
                border-radius: 5px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3d7bf0;
                color: white;
                border: 1px solid #508cf7;
            }
        """)
        batch_layout = QHBoxLayout(self.batch_toolbar)
        batch_layout.setContentsMargins(12, 8, 12, 8)
        batch_layout.setSpacing(8)

        batch_title = QLabel("Auto-Retention Rules:")
        batch_title.setStyleSheet("color: #b5b7bd; font-size: 12px; font-weight: bold; border: none;")
        batch_layout.addWidget(batch_title)

        btn_oldest = QPushButton("Keep Oldest")
        btn_oldest.setToolTip("Retain the earliest modified file in every group")
        btn_oldest.clicked.connect(lambda: self.apply_global_heuristic("oldest"))
        batch_layout.addWidget(btn_oldest)

        btn_newest = QPushButton("Keep Newest")
        btn_newest.setToolTip("Retain the most recently modified file in every group")
        btn_newest.clicked.connect(lambda: self.apply_global_heuristic("newest"))
        batch_layout.addWidget(btn_newest)

        btn_shortest = QPushButton("Keep Shortest Path")
        btn_shortest.setToolTip("Retain the file located at the shortest file path")
        btn_shortest.clicked.connect(lambda: self.apply_global_heuristic("shortest_path"))
        batch_layout.addWidget(btn_shortest)

        batch_layout.addStretch()

        btn_select_all = QPushButton("Select All Duplicates")
        btn_select_all.clicked.connect(self.select_all_duplicates)
        batch_layout.addWidget(btn_select_all)

        btn_deselect_all = QPushButton("Deselect All")
        btn_deselect_all.clicked.connect(self.deselect_all_duplicates)
        batch_layout.addWidget(btn_deselect_all)

        self.batch_toolbar.setVisible(False)
        main_layout.addWidget(self.batch_toolbar)

        # Scrollable Area for Duplicate Groups or Status Views
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.scroll_content = QWidget()
        self.results_layout = QVBoxLayout(self.scroll_content)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(15)

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area, 1)

        # Action Bar (Bottom Bar)
        self.action_bar = ActionBar()
        self.action_bar.delete_requested.connect(self.handle_delete_requested)
        main_layout.addWidget(self.action_bar)

        # Show initial empty state
        self.show_empty_state()

    def clear_content_area(self) -> None:
        """Remove all existing child widgets from the scroll layout."""
        self.group_card_widgets.clear()
        self.group_frames.clear()
        self.selected_files.clear()

        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def show_empty_state(
        self,
        title: str = "Ready to Scan",
        message: str = "Choose a folder from the sidebar or click '+ Add Folder' to begin scanning.",
        heading: str = "Duplicate Detection",
        subtitle: str = "Select a folder to start scanning for duplicate files.",
    ) -> None:
        """Display placeholder when no scan has been performed."""
        self.clear_content_area()
        self.heading.setText(heading)
        self.subtitle.setText(subtitle)
        self.batch_toolbar.setVisible(False)
        self.action_bar.update_selection([])

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
        empty_layout.setSpacing(12)

        icon_label = QLabel("🔍")
        icon_label.setStyleSheet("font-size: 40px; border: none;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: white; font-size: 18px; font-weight: bold; border: none;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(title_label)

        msg_label = QLabel(message)
        msg_label.setStyleSheet("color: #92959c; font-size: 13px; border: none;")
        msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(msg_label)

        self.results_layout.addWidget(empty_frame)
        self.results_layout.addStretch()

    def show_scanning_state(self, folder_path: str) -> None:
        """Prepare UI for an active scan."""
        self.clear_content_area()
        self.heading.setText("Scanning in Progress...")
        self.subtitle.setText(f"Scanning target: {folder_path}")
        self.batch_toolbar.setVisible(False)
        self.action_bar.update_selection([])
        self.progress_panel.reset()
        self.progress_panel.setVisible(True)

    def show_cancelled_state(self, stats: Optional[ScanStats] = None) -> None:
        """Display message after user cancels a scan."""
        self.progress_panel.setVisible(False)
        scanned_count = stats.total_files_scanned if stats else 0
        self.show_empty_state(
            title="Scan Cancelled by User",
            message=f"The scan was stopped early. {scanned_count:,} files were examined.",
            heading="Scan Cancelled",
            subtitle=f"Scan aborted after inspecting {scanned_count:,} files.",
        )

    def show_error_state(self, error_message: str) -> None:
        """Display error alert if a scan failed."""
        self.progress_panel.setVisible(False)
        self.clear_content_area()
        self.heading.setText("Scan Failed")
        self.subtitle.setText("An unexpected error occurred during the scan.")
        self.batch_toolbar.setVisible(False)

        error_frame = QFrame()
        error_frame.setStyleSheet("""
            QFrame {
                background-color: #3b2224;
                border: 1px solid #733e41;
                border-radius: 10px;
                padding: 25px;
            }
        """)
        err_layout = QVBoxLayout(error_frame)
        err_layout.setSpacing(10)

        err_title = QLabel("Error Details")
        err_title.setStyleSheet("color: #ff958e; font-size: 16px; font-weight: bold; border: none;")
        err_layout.addWidget(err_title)

        err_text = QLabel(error_message)
        err_text.setStyleSheet("color: #e8e8e8; font-size: 13px; border: none;")
        err_text.setWordWrap(True)
        err_layout.addWidget(err_text)

        self.results_layout.addWidget(error_frame)
        self.results_layout.addStretch()

    def set_results(self, duplicate_groups: List[DuplicateGroup], stats: ScanStats) -> None:
        """Populate the container with actual duplicate groups found by the scanner."""
        self.progress_panel.setVisible(False)
        self.duplicate_groups = duplicate_groups
        self.clear_content_area()

        if not duplicate_groups:
            self.show_empty_state(
                title="All Files Unique",
                message=f"Checked {stats.total_files_scanned:,} files. No duplicates detected.",
                heading="Scan Complete — No Duplicates Found",
                subtitle=(
                    f"Scanned {stats.total_files_scanned:,} files ({stats.formatted_total_size}) "
                    f"in {stats.duration_seconds:.2f}s. All files are unique!"
                ),
            )
            return

        # Results found: Update headers
        self.heading.setText("Duplicate Scan Results")
        self.subtitle.setText(
            f"Found {len(duplicate_groups):,} groups ({stats.duplicate_files_count:,} duplicates) "
            f"wasting {stats.formatted_wasted_space} across {stats.total_files_scanned:,} scanned files."
        )
        self.batch_toolbar.setVisible(True)

        # Build duplicate group frames
        for index, group in enumerate(duplicate_groups, start=1):
            group_frame = self._create_group_frame(index, group)
            self.group_frames[group.group_id] = group_frame
            self.results_layout.addWidget(group_frame)

        self.results_layout.addStretch()

        # Update action bar with initially marked duplicates
        self.action_bar.update_selection(list(self.selected_files.values()))

    def _create_group_frame(self, index: int, group: DuplicateGroup) -> QFrame:
        """Create visual group frame containing the header and duplicate file cards."""
        group_frame = QFrame()
        group_frame.setObjectName("groupFrame")
        group_frame.setStyleSheet("""
            QFrame#groupFrame {
                background-color: #202226;
                border: 1px solid #34373e;
                border-radius: 10px;
            }
        """)

        group_layout = QVBoxLayout(group_frame)
        group_layout.setContentsMargins(14, 14, 14, 14)
        group_layout.setSpacing(12)

        # Group Header
        header = QHBoxLayout()

        title_label = QLabel(f"Group {index}: {group.group_name}")
        title_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold; border: none;")
        header.addWidget(title_label)

        header.addStretch()

        meta_label = QLabel(
            f"{len(group.files)} copies  |  {format_bytes(group.file_size)} each  |  "
            f"Wasting {group.formatted_wasted_size}"
        )
        meta_label.setStyleSheet("color: #92959c; font-size: 12px; border: none;")
        header.addWidget(meta_label)

        group_layout.addLayout(header)

        # File Cards Container
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)

        card_list: List[DuplicateCard] = []

        for file_info in group.files:
            file_data = file_info.to_dict()
            card = DuplicateCard(file_data)

            # Listen for checkbox selection changes
            card.selection_changed.connect(self._handle_card_selection_changed)
            # Listen for "Keep This Copy" button
            card.set_as_keep_requested.connect(
                lambda data, grp=group: self._handle_switch_keep(grp, data)
            )

            cards_layout.addWidget(card, 1)
            card_list.append(card)

            # Initially select all files flagged as Duplicate for deletion
            if file_info.status == FileStatus.DUPLICATE:
                self.selected_files[file_info.path] = file_data

        self.group_card_widgets[group.group_id] = card_list
        group_layout.addLayout(cards_layout)

        return group_frame

    def _handle_card_selection_changed(self, checked: bool, file_data: dict) -> None:
        """Handle individual file card checkbox selection toggle."""
        path = file_data["path"]
        if checked:
            self.selected_files[path] = file_data
        else:
            self.selected_files.pop(path, None)

        self.action_bar.update_selection(list(self.selected_files.values()))

    def _handle_switch_keep(self, group: DuplicateGroup, file_data: dict) -> None:
        """Switch the retained copy in a duplicate group and refresh that group's cards."""
        target_path = file_data["path"]
        group.mark_keep(target_path)
        self._refresh_group_ui(group)

    def _refresh_group_ui(self, group: DuplicateGroup) -> None:
        """Rebuild the cards for a single duplicate group without re-rendering the whole page."""
        old_frame = self.group_frames.get(group.group_id)
        if not old_frame:
            return

        # Remove existing file entries of this group from selected_files
        for f in group.files:
            self.selected_files.pop(f.path, None)

        # Find position of old frame in results_layout
        index = self.results_layout.indexOf(old_frame)
        if index < 0:
            return

        # Re-create group frame
        group_number = list(self.group_frames.keys()).index(group.group_id) + 1
        new_frame = self._create_group_frame(group_number, group)

        self.results_layout.replaceWidget(old_frame, new_frame)
        old_frame.deleteLater()
        self.group_frames[group.group_id] = new_frame

        # Update action bar with updated selections
        self.action_bar.update_selection(list(self.selected_files.values()))

    def apply_global_heuristic(self, heuristic: str) -> None:
        """Apply a retention rule ('oldest', 'newest', 'shortest_path') across all groups."""
        if not self.duplicate_groups:
            return

        for group in self.duplicate_groups:
            group.apply_heuristic(heuristic)

        # Re-render all groups with the new retention choices
        self.set_results(
            self.duplicate_groups,
            ScanStats(
                total_files_scanned=sum(len(g.files) for g in self.duplicate_groups),
                duplicate_groups_count=len(self.duplicate_groups),
                duplicate_files_count=sum(len(g.files) - 1 for g in self.duplicate_groups),
                wasted_space_bytes=sum(g.wasted_size_bytes for g in self.duplicate_groups),
            ),
        )

    def select_all_duplicates(self) -> None:
        """Select all eligible duplicate files (excluding kept files) for deletion."""
        for card_list in self.group_card_widgets.values():
            for card in card_list:
                if card.file_data.get("status") == "Duplicate":
                    card.set_selected_for_delete(True)

    def deselect_all_duplicates(self) -> None:
        """Deselect all files in all groups."""
        for card_list in self.group_card_widgets.values():
            for card in card_list:
                card.set_selected_for_delete(False)

    def sync_post_deletion(self, deletion_results: List[DeletionResult]) -> None:
        """Update duplicate groups and selection after files have been moved to the Recycle Bin.

        Removes successfully deleted files from their groups, eliminates groups that
        now contain fewer than 2 files, and updates all counters and metrics.
        """
        deleted_paths: Set[str] = {
            os.path.normpath(res.file_path)
            for res in deletion_results
            if res.success
        }

        if not deleted_paths:
            return

        # Prune deleted paths from selected files
        for path in deleted_paths:
            self.selected_files.pop(path, None)

        # Update groups
        remaining_groups: List[DuplicateGroup] = []
        for group in self.duplicate_groups:
            group.files = [
                f for f in group.files
                if os.path.normpath(f.path) not in deleted_paths
            ]
            # Only groups with 2 or more files remain duplicates
            if len(group.files) >= 2:
                # Ensure at least one copy is marked KEEP
                has_keep = any(f.status == FileStatus.KEEP for f in group.files)
                if not has_keep:
                    group.files[0].status = FileStatus.KEEP
                    group.group_name = group.files[0].name
                remaining_groups.append(group)

        updated_stats = ScanStats(
            total_files_scanned=sum(len(g.files) for g in remaining_groups),
            duplicate_groups_count=len(remaining_groups),
            duplicate_files_count=sum(len(g.files) - 1 for g in remaining_groups),
            wasted_space_bytes=sum(g.wasted_size_bytes for g in remaining_groups),
        )

        self.set_results(remaining_groups, updated_stats)

    def handle_delete_requested(self, files: list) -> None:
        """Forward delete request to MainWindow for confirmation dialog and execution."""
        self.delete_requested.emit(files)
