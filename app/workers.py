"""Background worker threads for Duplicate File Detector.

Keeps scanning, hashing, deletion, and I/O operations entirely off the GUI thread
to ensure the application remains fully responsive during long operations. Uses
cooperative cancellation, throttled Qt signals, and robust error handling.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import QThread, Signal

from core.deleter import recycle_files
from core.models import DeletionResult, DuplicateGroup, ScanSettings, ScanStats
from core.scanner import FileScanner


class ScanWorker(QThread):
    """Background worker thread executing directory scans and duplicate identification."""

    phase_changed = Signal(str)
    progress_updated = Signal(int, int, str)  # (current, total, current_file_or_desc)
    scan_completed = Signal(list, object)     # (duplicate_groups: List[DuplicateGroup], stats: ScanStats)
    scan_cancelled = Signal()
    scan_error = Signal(str)

    def __init__(
        self,
        folder_path: str,
        settings: Optional[ScanSettings] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.folder_path = folder_path
        self.settings = settings or ScanSettings()
        self._cancel_requested: bool = False
        self._last_progress_time: float = 0.0
        self._throttle_interval_sec: float = 0.04  # 40ms (~25 FPS max signal rate)

    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested via internal flag or QThread interruption."""
        return self._cancel_requested or self.isInterruptionRequested()

    def cancel(self) -> None:
        """Request cooperative cancellation of the running scan."""
        self._cancel_requested = True
        self.requestInterruption()

    def run(self) -> None:
        """Worker thread entry point."""
        try:
            scanner = FileScanner(self.settings)

            def on_progress(phase: str, current: int, total: int, item_name: str) -> None:
                if self.is_cancelled():
                    return

                now = time.monotonic()
                is_boundary = (current == 0 or current >= total or total == 0)
                is_throttled = (now - self._last_progress_time >= self._throttle_interval_sec)

                if is_boundary or is_throttled:
                    self._last_progress_time = now
                    phase_desc = self._get_phase_display(phase)
                    self.phase_changed.emit(phase_desc)
                    self.progress_updated.emit(current, total, item_name)

            duplicate_groups, stats = scanner.scan_directory(
                folder_path=self.folder_path,
                progress_cb=on_progress,
                cancel_cb=self.is_cancelled,
            )

            if self.is_cancelled() or stats.was_cancelled:
                self.scan_cancelled.emit()
            else:
                self.scan_completed.emit(duplicate_groups, stats)

        except Exception as exc:  # pylint: disable=broad-except
            self.scan_error.emit(str(exc))

    @staticmethod
    def _get_phase_display(phase: str) -> str:
        """Map internal scanner phase names to friendly UI descriptions."""
        phase_map = {
            "indexing": "Phase 1/3: Discovering and grouping files by size...",
            "quick_hashing": "Phase 2/3: Quick hash comparison (16 KB)...",
            "full_hashing": "Phase 3/3: Verifying full SHA-256 digests...",
            "completed": "Scan Complete",
        }
        return phase_map.get(phase, phase)


class DeleteWorker(QThread):
    """Background worker thread safely moving selected files to the Windows Recycle Bin."""

    progress_updated = Signal(int, int, str)     # (current, total, current_file_name)
    deletion_completed = Signal(list, int, int)  # (results: List[DeletionResult], succeeded: int, freed_bytes: int)
    deletion_cancelled = Signal(list, int, int)
    deletion_error = Signal(str)

    def __init__(
        self,
        files_to_delete: List[Dict[str, Any]],
        protected_paths: Optional[Set[str]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.files_to_delete = files_to_delete
        self.protected_paths = protected_paths or set()
        self._cancel_requested: bool = False
        self._last_progress_time: float = 0.0
        self._throttle_interval_sec: float = 0.03  # 30ms throttling

    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancel_requested or self.isInterruptionRequested()

    def cancel(self) -> None:
        """Request cooperative cancellation."""
        self._cancel_requested = True
        self.requestInterruption()

    def run(self) -> None:
        """Worker thread entry point for batch file recycling."""
        try:
            def on_progress(current: int, total: int, item_name: str) -> None:
                if self.is_cancelled():
                    return
                now = time.monotonic()
                is_boundary = (current == 1 or current == total)
                if is_boundary or (now - self._last_progress_time >= self._throttle_interval_sec):
                    self._last_progress_time = now
                    self.progress_updated.emit(current, total, item_name)

            results, succeeded, freed_bytes = recycle_files(
                files_to_delete=self.files_to_delete,
                protected_paths=self.protected_paths,
                progress_cb=on_progress,
                cancel_cb=self.is_cancelled,
            )

            if self.is_cancelled():
                self.deletion_cancelled.emit(results, succeeded, freed_bytes)
            else:
                self.deletion_completed.emit(results, succeeded, freed_bytes)

        except Exception as exc:  # pylint: disable=broad-except
            self.deletion_error.emit(str(exc))
