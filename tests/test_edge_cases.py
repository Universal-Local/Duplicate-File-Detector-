"""Edge-case, stress, scale, and lifecycle tests for Duplicate File Detector (Milestone 6).

Covers:
  1. Permission-denied files and directories.
  2. Files moved during scanning (in addition to files deleted or modified).
  3. Rapid navigation and repeated scan requests.
  4. Corrupt settings/configuration and reset-to-default behavior.
  5. Recycle Bin failures and partial deletion.
  6. Deletion cancellation and worker cleanup.
  7. Memory usage and UI responsiveness under larger workloads.
  8. Unicode, non-ASCII, spaces, and unusual characters in paths.
  9. Deeply nested directory hierarchies.
  10. Zero-byte files (enabled vs disabled).
  11. Worker lifecycle and application shutdown.
  12. Cryptographic pre-recycle identity tamper detection.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QMessageBox

from app.main_window import MainWindow
from app.workers import DeleteWorker, ScanWorker
from core.config import load_settings, save_settings
from core.deleter import recycle_files, recycle_single_file
from core.models import DeletionResult, DuplicateGroup, FileInfo, FileStatus, ScanSettings, ScanStats
from core.scanner import FileScanner
from widgets.results_container import ResultsContainer
from widgets.settings_view import SettingsView

app = QApplication.instance()
if not app:
    app = QApplication([])


class TestEdgeCasesAndHardening(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    # 1. Permission-denied files and directories
    def test_permission_denied_directory_and_file_resilience(self):
        # Create an accessible directory with duplicate files and a restricted directory
        content = b"Accessible duplicate payload" * 20
        sub_ok = os.path.join(self.root, "accessible")
        sub_restricted = os.path.join(self.root, "restricted_dir")
        os.makedirs(sub_ok, exist_ok=True)
        os.makedirs(sub_restricted, exist_ok=True)

        p1 = os.path.join(sub_ok, "f1.txt")
        p2 = os.path.join(sub_ok, "f2.txt")
        with open(p1, "wb") as f:
            f.write(content)
        with open(p2, "wb") as f:
            f.write(content)

        # Mock os.scandir so scanning sub_restricted raises PermissionError
        original_scandir = os.scandir

        def mocked_scandir(path):
            norm = os.path.normpath(str(path))
            if norm == os.path.normpath(sub_restricted):
                raise PermissionError("Access denied to restricted directory")
            return original_scandir(path)

        with patch("os.scandir", side_effect=mocked_scandir):
            scanner = FileScanner()
            groups, stats = scanner.scan_directory(self.root)

            # Scanner should not crash, permission error should be recorded
            self.assertGreaterEqual(stats.permission_denied_count, 1)
            self.assertIn(sub_restricted, stats.inaccessible_files)
            # Accessible files should still be discovered as duplicates
            self.assertEqual(len(groups), 1)
            self.assertEqual(len(groups[0].files), 2)

    # 2. Files moved during scanning
    def test_file_moved_during_scan_handled_gracefully(self):
        content = b"Candidate for move test payload" * 10
        p1 = os.path.join(self.root, "stay_put.txt")
        p2 = os.path.join(self.root, "will_move.txt")
        p2_moved = os.path.join(self.root, "has_moved.txt")

        with open(p1, "wb") as f:
            f.write(content)
        with open(p2, "wb") as f:
            f.write(content)

        scanner = FileScanner()

        # Simulate moving file p2 to p2_moved during the quick_hashing phase
        def on_progress(phase, current, total, item):
            if phase == "quick_hashing" and os.path.exists(p2):
                os.rename(p2, p2_moved)

        groups, stats = scanner.scan_directory(self.root, progress_cb=on_progress)
        # p2 moved so hashing p2 failed; only 1 candidate remains -> 0 duplicate groups
        self.assertEqual(len(groups), 0)
        self.assertIn(os.path.normpath(p2), [os.path.normpath(p) for p in stats.inaccessible_files])

    # 3. Rapid navigation and repeated scan requests
    def test_rapid_scan_requests_and_navigation(self):
        window = MainWindow()

        sub1 = os.path.join(self.root, "sub1")
        sub2 = os.path.join(self.root, "sub2")
        os.makedirs(sub1, exist_ok=True)
        os.makedirs(sub2, exist_ok=True)

        with open(os.path.join(sub1, "a.txt"), "wb") as f:
            f.write(b"data1")
        with open(os.path.join(sub2, "b.txt"), "wb") as f:
            f.write(b"data2")

        # Mock question dialog to approve interrupting active scans
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            # Launch first scan
            window.start_scan(sub1)
            worker1 = window.current_scan_worker
            self.assertIsNotNone(worker1)

            # Immediately launch second scan without waiting
            window.start_scan(sub2)
            worker2 = window.current_scan_worker
            self.assertIsNotNone(worker2)
            self.assertNotEqual(worker1, worker2)

            # Rapidly switch navigation views
            window.handle_section_change("Settings")
            self.assertEqual(window.stacked_widget.currentWidget(), window.settings_view)

            window.handle_section_change("Archive")
            self.assertEqual(window.stacked_widget.currentWidget(), window.archive_view)

            window.handle_section_change("Downloads")
            self.assertEqual(window.stacked_widget.currentWidget(), window.results)

            # Wait for worker2 to complete
            worker2.wait(5000)
            app.processEvents()

            # Window state should be consistent and reflect sub2 scan
            self.assertFalse(window.is_worker_active())
            self.assertEqual(window.stacked_widget.currentWidget(), window.results)

        window.close()

    # 4. Corrupt settings/configuration and reset-to-default behavior
    def test_corrupt_settings_file_recovers_defaults(self):
        config_path = Path(self.root) / "corrupt_settings.json"

        # Case A: Malformed JSON syntax
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("{{INVALID JSON SYNTAX")

        loaded = load_settings(config_path=config_path)
        self.assertEqual(loaded.min_size_bytes, 1)
        self.assertIn(".git", loaded.excluded_folders)

        # Case B: Semantic corruption (negative sizes)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"min_size_bytes": -9999}, f)

        loaded = load_settings(config_path=config_path)
        self.assertEqual(loaded.min_size_bytes, 1)

        # Case C: SettingsView reset to defaults
        view = SettingsView()
        view.min_size_spin.setValue(500)
        view.reset_defaults()
        self.assertEqual(view.min_size_spin.value(), 0)
        view.close()

    # 5. Recycle Bin failures and partial deletion
    def test_partial_deletion_failure_and_ui_sync(self):
        p1 = os.path.join(self.root, "dup1.txt")
        p2 = os.path.join(self.root, "dup2_locked.txt")
        p3 = os.path.join(self.root, "dup3.txt")

        for p in (p1, p2, p3):
            with open(p, "wb") as f:
                f.write(b"content")

        files_data = [
            {"path": p1, "name": "dup1.txt", "size_bytes": 7, "mtime": os.stat(p1).st_mtime, "status": "Duplicate"},
            {"path": p2, "name": "dup2_locked.txt", "size_bytes": 7, "mtime": os.stat(p2).st_mtime, "status": "Duplicate"},
            {"path": p3, "name": "dup3.txt", "size_bytes": 7, "mtime": os.stat(p3).st_mtime, "status": "Duplicate"},
        ]

        # Simulate: p1 and p3 deleted, p2 raises PermissionError (file locked by another process)
        def fake_trash(path):
            if "locked" in path:
                raise PermissionError("Process locked by another application")
            if os.path.exists(path):
                os.remove(path)

        with patch("send2trash.send2trash", side_effect=fake_trash):
            results, succeeded, freed_bytes = recycle_files(files_data)

            self.assertEqual(len(results), 3)
            self.assertEqual(succeeded, 2)
            self.assertEqual(freed_bytes, 14)

            # Check individual statuses
            self.assertTrue(results[0].success)
            self.assertFalse(results[1].success)
            self.assertIn("Access denied", results[1].error_message)
            self.assertTrue(results[2].success)

            # Verify ResultsContainer syncs partial failures correctly
            f_keep = FileInfo(path=os.path.join(self.root, "keep.txt"), name="keep.txt", size=7, mtime=10.0, status=FileStatus.KEEP)
            f1 = FileInfo(path=p1, name="dup1.txt", size=7, mtime=20.0, status=FileStatus.DUPLICATE)
            f2 = FileInfo(path=p2, name="dup2_locked.txt", size=7, mtime=30.0, status=FileStatus.DUPLICATE)
            f3 = FileInfo(path=p3, name="dup3.txt", size=7, mtime=40.0, status=FileStatus.DUPLICATE)

            group = DuplicateGroup("g1", "keep.txt", 7, "hash1", [f_keep, f1, f2, f3])
            stats = ScanStats(total_files_scanned=4, duplicate_groups_count=1, duplicate_files_count=3, wasted_space_bytes=21)

            container = ResultsContainer()
            container.set_results([group], stats)
            self.assertEqual(len(container.selected_files), 3)

            container.sync_post_deletion(results)
            # p1 and p3 removed; p2 was locked so it remains in group and in selected_files
            self.assertEqual(len(container.selected_files), 1)
            self.assertIn(p2, container.selected_files)
            self.assertNotIn(p1, container.selected_files)
            self.assertNotIn(p3, container.selected_files)
            container.close()

    # 6. Deletion cancellation and worker cleanup
    def test_deletion_worker_cancellation_and_cleanup(self):
        files_data = []
        for i in range(10):
            p = os.path.join(self.root, f"del_{i}.txt")
            with open(p, "wb") as f:
                f.write(b"data")
            files_data.append({
                "path": p,
                "name": f"del_{i}.txt",
                "size_bytes": 4,
                "mtime": os.stat(p).st_mtime,
                "status": "Duplicate",
            })

        def fake_trash(path):
            if os.path.exists(path):
                os.remove(path)

        with patch("send2trash.send2trash", side_effect=fake_trash):
            worker = DeleteWorker(files_data)
            cancelled_emitted = []
            worker.deletion_cancelled.connect(lambda res, cnt, freed: cancelled_emitted.append(True))

            # Cancel immediately
            worker.cancel()
            worker.start()
            worker.wait(3000)
            app.processEvents()

            self.assertTrue(len(cancelled_emitted) > 0)
            self.assertFalse(worker.isRunning())

    # 7. Memory usage and UI responsiveness under larger workloads
    def test_ui_memory_and_responsiveness_large_workload(self):
        # Build 100 duplicate groups (300 files)
        groups = []
        total_wasted = 0
        for i in range(100):
            f_keep = FileInfo(path=f"C:/mock/grp_{i}/kept.txt", name="kept.txt", size=1024, mtime=100.0, status=FileStatus.KEEP)
            f_dup1 = FileInfo(path=f"C:/mock/grp_{i}/dup1.txt", name="dup1.txt", size=1024, mtime=200.0, status=FileStatus.DUPLICATE)
            f_dup2 = FileInfo(path=f"C:/mock/grp_{i}/dup2.txt", name="dup2.txt", size=1024, mtime=300.0, status=FileStatus.DUPLICATE)
            grp = DuplicateGroup(f"g_{i}", "kept.txt", 1024, f"hash_{i}", [f_keep, f_dup1, f_dup2])
            groups.append(grp)
            total_wasted += grp.wasted_size_bytes

        stats = ScanStats(
            total_files_scanned=300,
            duplicate_groups_count=100,
            duplicate_files_count=200,
            wasted_space_bytes=total_wasted,
        )

        container = ResultsContainer()

        start = time.time()
        container.set_results(groups, stats)
        render_duration = time.time() - start

        # Rendering 100 groups must be fast
        self.assertLess(render_duration, 3.0)
        self.assertEqual(len(container.selected_files), 200)

        # Apply global heuristic batch operation
        container.apply_global_heuristic("newest")
        self.assertEqual(len(container.selected_files), 200)

        # Clear container cleanly
        container.clear_content_area()
        self.assertEqual(len(container.selected_files), 0)
        self.assertEqual(len(container.group_frames), 0)
        container.close()

    # 8. Unicode and unusual filenames
    def test_unicode_and_unusual_filenames(self):
        content = b"Unicode and special symbol duplicate test" * 10
        names = [
            "测试文件_copy (1) [dup].txt",
            "файл дубликат #2.txt",
            "फ़ाइल टेस्ट $#!.txt",
            "normal space  double space.txt",
        ]

        sub = os.path.join(self.root, "unicode_sub")
        os.makedirs(sub, exist_ok=True)

        paths = []
        for name in names:
            p = os.path.join(sub, name)
            with open(p, "wb") as f:
                f.write(content)
            paths.append(p)

        scanner = FileScanner()
        groups, stats = scanner.scan_directory(self.root)

        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0].files), len(names))
        self.assertEqual(stats.duplicate_files_count, len(names) - 1)

        def fake_trash(p):
            if os.path.exists(p):
                os.remove(p)

        file_to_del = groups[0].files[1].to_dict()
        with patch("send2trash.send2trash", side_effect=fake_trash):
            res = recycle_single_file(file_to_del)
            self.assertTrue(res.success)
            self.assertFalse(os.path.exists(file_to_del["path"]))

    # 9. Deeply nested directory traversal
    def test_deeply_nested_directory_traversal(self):
        content = b"Deeply nested duplicate test payload"
        deep_dir = self.root
        for i in range(10):
            deep_dir = os.path.join(deep_dir, f"level_{i}")
        os.makedirs(deep_dir, exist_ok=True)

        shallow_file = os.path.join(self.root, "shallow.bin")
        deep_file = os.path.join(deep_dir, "deep.bin")

        with open(shallow_file, "wb") as f:
            f.write(content)
        with open(deep_file, "wb") as f:
            f.write(content)

        scanner = FileScanner()
        groups, stats = scanner.scan_directory(self.root)

        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0].files), 2)

    # 10. Zero-byte empty files behavior
    def test_zero_byte_empty_files_behavior(self):
        p1 = os.path.join(self.root, "empty1.txt")
        p2 = os.path.join(self.root, "empty2.txt")
        with open(p1, "wb") as f:
            pass
        with open(p2, "wb") as f:
            pass

        # Case A: Default settings ignore 0-byte files
        scanner_default = FileScanner()
        groups_def, stats_def = scanner_default.scan_directory(self.root)
        self.assertEqual(len(groups_def), 0)
        self.assertEqual(stats_def.total_files_scanned, 0)

        # Case B: User enables 0-byte detection
        scanner_zero = FileScanner(ScanSettings(min_size_bytes=0))
        groups_zero, stats_zero = scanner_zero.scan_directory(self.root)
        self.assertEqual(len(groups_zero), 1)
        self.assertEqual(groups_zero[0].file_size, 0)
        self.assertEqual(len(groups_zero[0].files), 2)

    # 11. Cryptographic pre-recycle tamper detection
    def test_cryptographic_tamper_detection_in_deleter(self):
        file_path = os.path.join(self.root, "tampered.txt")
        original_content = b"original safe content"
        tampered_content = b"tampered evil content"

        with open(file_path, "wb") as f:
            f.write(original_content)

        st = os.stat(file_path)

        import hashlib
        original_sha = hashlib.sha256(original_content).hexdigest()

        with open(file_path, "wb") as f:
            f.write(tampered_content)
        os.utime(file_path, (st.st_atime, st.st_mtime))

        file_data = {
            "path": file_path,
            "name": "tampered.txt",
            "size_bytes": len(tampered_content),
            "mtime": st.st_mtime,
            "sha256": original_sha,
            "status": "Duplicate",
        }

        with patch("send2trash.send2trash") as mock_trash:
            res = recycle_single_file(file_data, verify_identity_hash=True)
            self.assertFalse(res.success)
            self.assertIn("Cryptographic verification failed", res.error_message)
            mock_trash.assert_not_called()

    # 12. Main window close event terminates workers
    def test_main_window_close_event_terminates_workers(self):
        window = MainWindow()
        window.start_scan(self.root)
        self.assertTrue(window.is_worker_active())

        from PySide6.QtGui import QCloseEvent
        close_event = QCloseEvent()
        window.closeEvent(close_event)
        self.assertTrue(close_event.isAccepted())
        self.assertFalse(window.is_worker_active())


if __name__ == "__main__":
    unittest.main()
