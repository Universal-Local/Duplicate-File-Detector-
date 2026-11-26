"""Tests for MainWindow integration and scan lifecycle."""

import os
import tempfile
import unittest

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow

app = QApplication.instance()
if not app:
    app = QApplication([])


class TestMainWindowIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name
        self.window = MainWindow()

    def tearDown(self):
        if self.window.current_scan_worker and self.window.current_scan_worker.isRunning():
            self.window.current_scan_worker.cancel()
            self.window.current_scan_worker.wait(1000)
        if self.window.current_delete_worker and self.window.current_delete_worker.isRunning():
            self.window.current_delete_worker.cancel()
            self.window.current_delete_worker.wait(1000)
        self.window.close()
        self.window.deleteLater()
        app.processEvents()
        self.temp_dir.cleanup()

    def test_window_initial_state(self):
        self.assertIsNotNone(self.window.sidebar)
        self.assertIsNotNone(self.window.results)
        self.assertEqual(self.window.results.heading.text(), "Duplicate Detection")

    def test_start_scan_and_complete(self):
        content = b"Integration test duplicate file" * 50
        p1 = os.path.join(self.root, "f1.txt")
        p2 = os.path.join(self.root, "f2.txt")
        with open(p1, "wb") as f:
            f.write(content)
        with open(p2, "wb") as f:
            f.write(content)

        self.window.start_scan(self.root)
        self.assertIsNotNone(self.window.current_scan_worker)

        self.window.current_scan_worker.wait(5000)
        app.processEvents()

        self.assertEqual(len(self.window.results.duplicate_groups), 1)
        self.assertEqual(self.window.sidebar.status_value.text(), "1 duplicate group(s)")
        self.assertEqual(len(self.window.results.selected_files), 1)


if __name__ == "__main__":
    unittest.main()
