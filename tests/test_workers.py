"""Tests for background workers and progress reporting."""

import os
import tempfile
import unittest

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from app.workers import ScanWorker
from core.models import ScanSettings
from widgets.progress_panel import ProgressPanel

# Ensure a QApplication instance exists for QWidget and signal delivery
app = QApplication.instance()
if not app:
    app = QApplication([])


class TestWorkersAndProgress(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_scan_worker_execution(self):
        content = b"Worker duplicate test payload" * 100
        p1 = os.path.join(self.root, "dup1.bin")
        p2 = os.path.join(self.root, "dup2.bin")
        with open(p1, "wb") as f:
            f.write(content)
        with open(p2, "wb") as f:
            f.write(content)

        worker = ScanWorker(folder_path=self.root)

        phases = []
        progress_calls = []
        results = []

        worker.phase_changed.connect(lambda p: phases.append(p))
        worker.progress_updated.connect(lambda c, t, item: progress_calls.append((c, t, item)))
        worker.scan_completed.connect(lambda groups, stats: results.append((groups, stats)))

        worker.start()
        worker.wait(5000)
        # Flush Qt event loop to receive cross-thread queued signals
        app.processEvents()

        self.assertGreater(len(phases), 0)
        self.assertGreater(len(results), 0)
        groups, stats = results[0]
        self.assertEqual(len(groups), 1)
        self.assertEqual(stats.duplicate_files_count, 1)

    def test_scan_worker_cancellation(self):
        for i in range(20):
            p = os.path.join(self.root, f"file_{i}.bin")
            with open(p, "wb") as f:
                f.write(b"data" * 100)

        worker = ScanWorker(folder_path=self.root)
        cancelled = []
        worker.scan_cancelled.connect(lambda: cancelled.append(True))

        # Request cancellation
        worker.cancel()
        worker.start()
        worker.wait(5000)
        # Flush cross-thread queued signals
        app.processEvents()

        self.assertEqual(len(cancelled), 1)

    def test_progress_panel_updates_and_cancellation(self):
        panel = ProgressPanel()

        panel.set_phase("Test Phase")
        self.assertEqual(panel.phase_label.text(), "Test Phase")

        panel.update_progress(50, 100, "C:\\test\\path\\file.txt")
        self.assertEqual(panel.progress_bar.value(), 50)
        self.assertIn("50%", panel.detail_label.text())

        cancel_emitted = []
        panel.cancel_requested.connect(lambda: cancel_emitted.append(True))
        panel.cancel_button.click()
        self.assertEqual(len(cancel_emitted), 1)

        panel.reset()
        self.assertEqual(panel.progress_bar.value(), 0)
        self.assertEqual(panel.phase_label.text(), "Ready to scan")


if __name__ == "__main__":
    unittest.main()
