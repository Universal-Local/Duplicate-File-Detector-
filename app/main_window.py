"""Main application window for Duplicate File Detector.

Integrates Sidebar navigation, dynamic ResultsContainer, SettingsView, ArchiveView,
and background ScanWorker and DeleteWorker lifecycle management with non-destructive
page switching.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from app.sidebar import Sidebar
from app.styles import MAIN_STYLESHEET
from app.workers import DeleteWorker, ScanWorker
from core.config import load_settings
from core.models import DeletionResult, DuplicateGroup, FileStatus, ScanSettings, ScanStats, format_bytes
from widgets.archive_view import ArchiveView
from widgets.confirmation_dialog import DeletionConfirmationDialog
from widgets.results_container import ResultsContainer
from widgets.settings_view import SettingsView


class MainWindow(QMainWindow):
    """Primary application window coordinating navigation, workers, and view stacks."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Duplicate File Detector")
        self.resize(1200, 750)
        self.setMinimumSize(950, 600)

        self.scan_settings: ScanSettings = load_settings()
        self.current_scan_worker: Optional[ScanWorker] = None
        self.current_delete_worker: Optional[DeleteWorker] = None
        self.setup_ui()

    @property
    def current_worker(self) -> Optional[ScanWorker]:
        """Backward-compatible alias for current_scan_worker."""
        return self.current_scan_worker

    def setup_ui(self) -> None:
        """Initialize main layout, views, and signal connections."""
        self.setStyleSheet(MAIN_STYLESHEET)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(15)

        # Left Sidebar
        self.sidebar = Sidebar()
        main_layout.addWidget(self.sidebar)

        # Right Stacked Area (Results, Settings, Archive)
        self.stacked_widget = QStackedWidget()

        # Page 0: Results Container
        self.results = ResultsContainer()
        self.stacked_widget.addWidget(self.results)

        # Page 1: Settings View
        self.settings_view = SettingsView()
        self.settings_view.settings_saved.connect(self.handle_settings_saved)
        self.stacked_widget.addWidget(self.settings_view)

        # Page 2: Archive / History View
        self.archive_view = ArchiveView()
        self.stacked_widget.addWidget(self.archive_view)

        main_layout.addWidget(self.stacked_widget, 1)

        # Connect Sidebar signals
        self.sidebar.section_changed.connect(self.handle_section_change)
        self.sidebar.folder_selected.connect(self.handle_add_folder_selected)

        # Connect ResultsContainer signals
        self.results.progress_panel.cancel_requested.connect(self.cancel_active_scan)
        self.results.delete_requested.connect(self.handle_delete_requested)

    def handle_settings_saved(self, new_settings: ScanSettings) -> None:
        """Update active scan settings when saved in the settings view."""
        self.scan_settings = new_settings
        self.sidebar.status_value.setText("Settings saved")

    def is_worker_active(self) -> bool:
        """Returns True if a scan or deletion worker is currently running."""
        scan_busy = bool(self.current_scan_worker and self.current_scan_worker.isRunning())
        del_busy = bool(self.current_delete_worker and self.current_delete_worker.isRunning())
        return scan_busy or del_busy

    def start_scan(self, folder_path: str) -> None:
        """Initiate background scanning for the specified directory path."""
        norm_path = os.path.normpath(folder_path)

        if not os.path.isdir(norm_path):
            QMessageBox.warning(
                self,
                "Invalid Directory",
                f"The selected folder does not exist:\n{norm_path}",
            )
            return

        if self.is_worker_active():
            reply = QMessageBox.question(
                self,
                "Scan in Progress",
                "An operation is currently running. Do you want to cancel it to start this new scan?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            self._terminate_active_workers()

        # Always disconnect and cleanly terminate any previous worker before creating a new one
        self._terminate_active_workers()

        # Ensure Results view is active
        self.stacked_widget.setCurrentWidget(self.results)

        self.sidebar.status_value.setText("Scanning...")
        self.results.show_scanning_state(norm_path)

        # Create and launch background scan worker with persistent settings
        self.current_scan_worker = ScanWorker(
            folder_path=norm_path,
            settings=self.scan_settings,
        )
        self.current_scan_worker.phase_changed.connect(self.results.progress_panel.set_phase)
        self.current_scan_worker.progress_updated.connect(self.results.progress_panel.update_progress)
        self.current_scan_worker.scan_completed.connect(
            lambda groups, stats, p=norm_path: self.handle_scan_completed(groups, stats, p)
        )
        self.current_scan_worker.scan_cancelled.connect(self.handle_scan_cancelled)
        self.current_scan_worker.scan_error.connect(self.handle_scan_error)

        self.current_scan_worker.start()

    def _terminate_active_workers(self) -> None:
        """Safely disconnect and terminate any running background workers."""
        if self.current_scan_worker:
            try:
                self.current_scan_worker.phase_changed.disconnect()
                self.current_scan_worker.progress_updated.disconnect()
                self.current_scan_worker.scan_completed.disconnect()
                self.current_scan_worker.scan_cancelled.disconnect()
                self.current_scan_worker.scan_error.disconnect()
            except (RuntimeError, TypeError):
                pass
            if self.current_scan_worker.isRunning():
                self.current_scan_worker.cancel()
                self.current_scan_worker.wait(2000)
            self.current_scan_worker = None

        if self.current_delete_worker:
            try:
                self.current_delete_worker.progress_updated.disconnect()
                self.current_delete_worker.deletion_completed.disconnect()
                self.current_delete_worker.deletion_cancelled.disconnect()
                self.current_delete_worker.deletion_error.disconnect()
            except (RuntimeError, TypeError):
                pass
            if self.current_delete_worker.isRunning():
                self.current_delete_worker.cancel()
                self.current_delete_worker.wait(2000)
            self.current_delete_worker = None

    def closeEvent(self, event) -> None:
        """Ensure all background workers are cleanly stopped before window closes."""
        self._terminate_active_workers()
        event.accept()

    def cancel_active_scan(self) -> None:
        """Cancel the currently running background scan."""
        if self.current_scan_worker and self.current_scan_worker.isRunning():
            self.sidebar.status_value.setText("Cancelling...")
            self.current_scan_worker.cancel()

    def handle_scan_completed(self, duplicate_groups: list, stats: ScanStats, folder_path: str) -> None:
        """Handle successful scan completion and log record to archive."""
        group_count = len(duplicate_groups)
        if group_count > 0:
            self.sidebar.status_value.setText(f"{group_count} duplicate group(s)")
            summary_desc = f"{group_count} duplicate groups ({stats.formatted_wasted_space} wasted)"
        else:
            self.sidebar.status_value.setText("No duplicates")
            summary_desc = f"Clean: {stats.total_files_scanned:,} files scanned, no duplicates found"

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.archive_view.add_record(folder_path, summary_desc, now_str)

        self.results.set_results(duplicate_groups, stats)

    def handle_scan_cancelled(self) -> None:
        """Handle scan cancellation."""
        self.sidebar.status_value.setText("Scan cancelled")
        self.results.show_cancelled_state()

    def handle_scan_error(self, error_message: str) -> None:
        """Handle unhandled scan errors."""
        self.sidebar.status_value.setText("Scan error")
        self.results.show_error_state(error_message)

    def handle_section_change(self, section: str) -> None:
        """Handle sidebar navigation clicks without interrupting active tasks."""
        if section == "Settings":
            self.stacked_widget.setCurrentWidget(self.settings_view)
            return

        if section == "Archive":
            self.stacked_widget.setCurrentWidget(self.archive_view)
            return

        # Standard views: Switch to results view without restarting scans
        self.stacked_widget.setCurrentWidget(self.results)

    def handle_add_folder_selected(self, folder: str) -> None:
        """Handle custom folder selection from '+ Add Folder' button."""
        self.stacked_widget.setCurrentWidget(self.results)
        self.start_scan(folder)

    def handle_delete_requested(self, files_to_delete: list) -> None:
        """Execute explicit confirmation and trigger safe background file recycling."""
        if not files_to_delete:
            return

        protected_paths: Set[str] = set()
        for group in self.results.duplicate_groups:
            for file_info in group.files:
                if file_info.status == FileStatus.KEEP:
                    protected_paths.add(os.path.normpath(file_info.path))

        # Explicit Confirmation Dialog
        dialog = DeletionConfirmationDialog(files_to_delete, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.sidebar.status_value.setText("Recycling files...")
        self.results.action_bar.delete_button.setEnabled(False)

        # Launch DeleteWorker
        self.current_delete_worker = DeleteWorker(
            files_to_delete=files_to_delete,
            protected_paths=protected_paths,
            parent=self,
        )
        self.current_delete_worker.deletion_completed.connect(self.handle_deletion_completed)
        self.current_delete_worker.deletion_cancelled.connect(self.handle_deletion_cancelled)
        self.current_delete_worker.deletion_error.connect(self.handle_deletion_error)
        self.current_delete_worker.start()

    def handle_deletion_completed(
        self,
        results: list,
        succeeded: int,
        freed_bytes: int,
    ) -> None:
        """Synchronize results and notify user of deletion results."""
        self.results.sync_post_deletion(results)

        failed = [r for r in results if not r.success]
        self.sidebar.status_value.setText(f"{succeeded} files recycled")

        if failed:
            failed_lines = "\n".join(
                f"- {os.path.basename(r.file_path)}: {r.error_message}"
                for r in failed[:5]
            )
            if len(failed) > 5:
                failed_lines += f"\n... and {len(failed) - 5} more."

            QMessageBox.warning(
                self,
                "Recycle Bin Results",
                f"Recycled {succeeded} file(s), freeing {format_bytes(freed_bytes)}.\n\n"
                f"{len(failed)} file(s) could not be recycled:\n{failed_lines}",
            )
        else:
            QMessageBox.information(
                self,
                "Recycle Bin Success",
                f"Successfully moved {succeeded} duplicate file(s) to the Windows Recycle Bin.\n"
                f"Recovered storage: {format_bytes(freed_bytes)}.\n\n"
                "Files can be restored from the Recycle Bin if needed.",
            )

    def handle_deletion_cancelled(
        self,
        results: list,
        succeeded: int,
        freed_bytes: int,
    ) -> None:
        """Handle cancelled deletion."""
        self.results.sync_post_deletion(results)
        self.sidebar.status_value.setText("Deletion cancelled")
        QMessageBox.information(
            self,
            "Deletion Aborted",
            f"Operation was cancelled. {succeeded} file(s) were moved to the Recycle Bin "
            f"({format_bytes(freed_bytes)} freed) before cancellation.",
        )

    def handle_deletion_error(self, error_message: str) -> None:
        """Handle unexpected deletion worker error."""
        self.sidebar.status_value.setText("Deletion error")
        self.results.action_bar.delete_button.setEnabled(True)
        QMessageBox.critical(
            self,
            "Recycle Bin Error",
            f"An error occurred while moving files to the Recycle Bin:\n{error_message}",
        )
