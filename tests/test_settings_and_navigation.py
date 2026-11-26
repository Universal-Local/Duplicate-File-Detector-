"""Automated tests for settings validation, persistence, and non-destructive navigation."""

import os
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from core.config import (
    load_settings,
    sanitize_extensions,
    sanitize_folders,
    save_settings,
    validate_settings,
)
from core.models import ScanSettings
from widgets.archive_view import ArchiveView
from widgets.settings_view import SettingsView

app = QApplication.instance()
if not app:
    app = QApplication([])


class TestSettingsAndNavigation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "test_settings.json"
        self.window = MainWindow()

    def tearDown(self):
        if self.window.current_scan_worker and self.window.current_scan_worker.isRunning():
            self.window.current_scan_worker.cancel()
            self.window.current_scan_worker.wait(1000)
        self.window.close()
        self.window.deleteLater()
        app.processEvents()
        self.temp_dir.cleanup()

    def test_settings_validation_rules(self):
        # Valid settings
        valid, errors = validate_settings(1024, 20480, {".git", "node_modules"}, {".tmp", ".bak"}, False)
        self.assertTrue(valid)
        self.assertEqual(len(errors), 0)

        # Negative min size
        valid, errors = validate_settings(-5, None, set(), set(), False)
        self.assertFalse(valid)
        self.assertTrue(any("cannot be negative" in e for e in errors))

        # Max size smaller than min size
        valid, errors = validate_settings(5000, 2000, set(), set(), False)
        self.assertFalse(valid)
        self.assertTrue(any("greater than or equal" in e for e in errors))

        # Invalid extension (no leading period)
        valid, errors = validate_settings(0, None, set(), {"tmp"}, False)
        self.assertFalse(valid)
        self.assertTrue(any("must start with a period" in e for e in errors))

    def test_settings_persistence(self):
        settings = ScanSettings(
            min_size_bytes=4096,
            max_size_bytes=104857600,
            excluded_folders={"custom_folder", ".cache"},
            excluded_extensions={".log", ".dmp"},
            follow_symlinks=True,
        )

        # Save to temp path
        success, errors = save_settings(settings, config_path=self.config_path)
        self.assertTrue(success)
        self.assertEqual(len(errors), 0)

        # Load back
        loaded = load_settings(config_path=self.config_path)
        self.assertEqual(loaded.min_size_bytes, 4096)
        self.assertEqual(loaded.max_size_bytes, 104857600)
        self.assertEqual(loaded.excluded_folders, {"custom_folder", ".cache"})
        self.assertEqual(loaded.excluded_extensions, {".log", ".dmp"})
        self.assertTrue(loaded.follow_symlinks)

    def test_settings_view_ui(self):
        view = SettingsView()
        self.assertIsNotNone(view.min_size_spin)
        self.assertIsNotNone(view.folder_edit)

        view.reset_defaults()
        self.assertEqual(view.min_size_spin.value(), 0)
        self.assertFalse(view.enable_max_check.isChecked())
        view.close()

    def test_archive_view_records(self):
        archive = ArchiveView()
        # Initially empty state
        self.assertEqual(len(archive.history_records), 0)

        archive.add_record("C:/Downloads", "3 groups found", "2026-11-25 18:00")
        self.assertEqual(len(archive.history_records), 1)
        self.assertEqual(archive.history_records[0]["folder"], "C:/Downloads")
        archive.close()

    def test_non_destructive_navigation(self):
        # Initial page should be Results Container
        self.assertEqual(self.window.stacked_widget.currentWidget(), self.window.results)

        # Navigate to Settings
        self.window.handle_section_change("Settings")
        self.assertEqual(self.window.stacked_widget.currentWidget(), self.window.settings_view)

        # Navigate to Archive
        self.window.handle_section_change("Archive")
        self.assertEqual(self.window.stacked_widget.currentWidget(), self.window.archive_view)

        # Navigate back to Downloads -> Results view
        self.window.handle_section_change("Downloads")
        self.assertEqual(self.window.stacked_widget.currentWidget(), self.window.results)


if __name__ == "__main__":
    unittest.main()
