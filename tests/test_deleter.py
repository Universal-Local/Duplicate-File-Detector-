"""Automated unit and integration tests for safe file recycling (Milestone 4).

All deletion calls to send2trash are mocked to completely prevent any risk to
user files.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from app.workers import DeleteWorker
from core.deleter import recycle_files, recycle_single_file
from core.models import DeletionResult, DuplicateGroup, FileInfo, FileStatus, ScanStats
from widgets.confirmation_dialog import DeletionConfirmationDialog
from widgets.results_container import ResultsContainer

app = QApplication.instance()
if not app:
    app = QApplication([])


class TestSafeDeleter(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_retained_status_rejection(self):
        file_path = os.path.join(self.root, "kept_file.txt")
        with open(file_path, "wb") as f:
            f.write(b"content")

        file_data = {
            "path": file_path,
            "name": "kept_file.txt",
            "size_bytes": 7,
            "status": "Keep",
        }

        with patch("send2trash.send2trash") as mock_trash:
            result = recycle_single_file(file_data)
            self.assertFalse(result.success)
            self.assertIn("retained copy", result.error_message)
            mock_trash.assert_not_called()

    def test_protected_path_rejection(self):
        file_path = os.path.join(self.root, "dup_in_protected.txt")
        with open(file_path, "wb") as f:
            f.write(b"content")

        file_data = {
            "path": file_path,
            "name": "dup_in_protected.txt",
            "size_bytes": 7,
            "status": "Duplicate",
        }

        with patch("send2trash.send2trash") as mock_trash:
            result = recycle_single_file(file_data, protected_paths={file_path})
            self.assertFalse(result.success)
            self.assertIn("protected retention list", result.error_message)
            mock_trash.assert_not_called()

    def test_missing_file_rejection(self):
        missing_path = os.path.join(self.root, "ghost_file.txt")
        file_data = {
            "path": missing_path,
            "name": "ghost_file.txt",
            "size_bytes": 100,
            "status": "Duplicate",
        }

        with patch("send2trash.send2trash") as mock_trash:
            result = recycle_single_file(file_data)
            self.assertFalse(result.success)
            self.assertIn("File not found on disk", result.error_message)
            mock_trash.assert_not_called()

    def test_size_mismatch_rejection(self):
        file_path = os.path.join(self.root, "changed_size.txt")
        with open(file_path, "wb") as f:
            f.write(b"new content that is 28 bytes")

        file_data = {
            "path": file_path,
            "name": "changed_size.txt",
            "size_bytes": 10,  # Recorded as 10 B during scan
            "status": "Duplicate",
        }

        with patch("send2trash.send2trash") as mock_trash:
            result = recycle_single_file(file_data)
            self.assertFalse(result.success)
            self.assertIn("File size changed since scan", result.error_message)
            mock_trash.assert_not_called()

    def test_mtime_mismatch_rejection(self):
        file_path = os.path.join(self.root, "changed_mtime.txt")
        with open(file_path, "wb") as f:
            f.write(b"same size")

        file_data = {
            "path": file_path,
            "name": "changed_mtime.txt",
            "size_bytes": 9,
            "mtime": 1000.0,  # Old mtime
            "status": "Duplicate",
        }

        with patch("send2trash.send2trash") as mock_trash:
            result = recycle_single_file(file_data)
            self.assertFalse(result.success)
            self.assertIn("File was modified after the scan", result.error_message)
            mock_trash.assert_not_called()

    def test_directory_deletion_prohibited(self):
        dir_path = os.path.join(self.root, "test_dir")
        os.makedirs(dir_path)

        file_data = {
            "path": dir_path,
            "name": "test_dir",
            "status": "Duplicate",
        }

        with patch("send2trash.send2trash") as mock_trash:
            result = recycle_single_file(file_data)
            self.assertFalse(result.success)
            self.assertIn("directory deletion is prohibited", result.error_message)
            mock_trash.assert_not_called()

    def test_successful_recycle_simulation(self):
        file_path = os.path.join(self.root, "valid_dup.txt")
        content = b"exact duplicate payload"
        with open(file_path, "wb") as f:
            f.write(content)

        st = os.stat(file_path)
        file_data = {
            "path": file_path,
            "name": "valid_dup.txt",
            "size_bytes": st.st_size,
            "mtime": st.st_mtime,
            "status": "Duplicate",
        }

        # Mock send2trash side-effect to remove the file from disk (simulating trash move)
        def fake_trash(path):
            os.remove(path)

        with patch("send2trash.send2trash", side_effect=fake_trash) as mock_trash:
            result = recycle_single_file(file_data)
            self.assertTrue(result.success)
            self.assertEqual(result.freed_bytes, len(content))
            mock_trash.assert_called_once_with(os.path.normpath(file_path))

    def test_batch_recycle_with_cancellation(self):
        files_data = []
        for i in range(5):
            p = os.path.join(self.root, f"batch_{i}.txt")
            with open(p, "wb") as f:
                f.write(b"data")
            st = os.stat(p)
            files_data.append({
                "path": p,
                "name": f"batch_{i}.txt",
                "size_bytes": st.st_size,
                "mtime": st.st_mtime,
                "status": "Duplicate",
            })

        def fake_trash(path):
            if os.path.exists(path):
                os.remove(path)

        with patch("send2trash.send2trash", side_effect=fake_trash):
            # Cancel after 2 files
            call_count = 0

            def should_cancel():
                nonlocal call_count
                call_count += 1
                return call_count > 2

            results, succeeded, freed_bytes = recycle_files(
                files_to_delete=files_data,
                cancel_cb=should_cancel,
            )

            self.assertEqual(len(results), 2)
            self.assertEqual(succeeded, 2)
            self.assertEqual(freed_bytes, 8)

    def test_delete_worker_execution(self):
        p1 = os.path.join(self.root, "worker_del1.txt")
        p2 = os.path.join(self.root, "worker_del2.txt")
        with open(p1, "wb") as f:
            f.write(b"payload1")
        with open(p2, "wb") as f:
            f.write(b"payload2")

        st1 = os.stat(p1)
        st2 = os.stat(p2)

        files_data = [
            {"path": p1, "name": "worker_del1.txt", "size_bytes": st1.st_size, "mtime": st1.st_mtime, "status": "Duplicate"},
            {"path": p2, "name": "worker_del2.txt", "size_bytes": st2.st_size, "mtime": st2.st_mtime, "status": "Duplicate"},
        ]

        def fake_trash(path):
            if os.path.exists(path):
                os.remove(path)

        with patch("send2trash.send2trash", side_effect=fake_trash):
            worker = DeleteWorker(files_to_delete=files_data)
            completed_payload = []
            worker.deletion_completed.connect(lambda res, cnt, freed: completed_payload.append((res, cnt, freed)))

            worker.start()
            worker.wait(5000)
            app.processEvents()

            self.assertEqual(len(completed_payload), 1)
            results, succeeded, freed_bytes = completed_payload[0]
            self.assertEqual(succeeded, 2)
            self.assertEqual(freed_bytes, st1.st_size + st2.st_size)

    def test_results_container_sync_post_deletion(self):
        f1 = FileInfo(path="C:/Downloads/a.txt", name="a.txt", size=500, mtime=100.0, status=FileStatus.KEEP)
        f2 = FileInfo(path="C:/Downloads/a_copy.txt", name="a_copy.txt", size=500, mtime=200.0, status=FileStatus.DUPLICATE)
        f3 = FileInfo(path="C:/Downloads/a_copy2.txt", name="a_copy2.txt", size=500, mtime=300.0, status=FileStatus.DUPLICATE)

        group = DuplicateGroup("grp1", "a.txt", 500, "hash123", [f1, f2, f3])
        stats = ScanStats(total_files_scanned=3, duplicate_groups_count=1, duplicate_files_count=2, wasted_space_bytes=1000)

        container = ResultsContainer()
        container.set_results([group], stats)

        self.assertEqual(len(container.selected_files), 2)

        # Simulate f2 successfully recycled
        del_results = [
            DeletionResult(file_path=f2.path, success=True, freed_bytes=500),
        ]
        container.sync_post_deletion(del_results)

        # f2 should be gone from selected_files; f3 is still a duplicate of f1
        self.assertEqual(len(container.selected_files), 1)
        self.assertNotIn(f2.path, container.selected_files)
        self.assertIn(f3.path, container.selected_files)
        self.assertEqual(len(group.files), 2)

        # Now simulate f3 successfully recycled
        del_results_2 = [
            DeletionResult(file_path=f3.path, success=True, freed_bytes=500),
        ]
        container.sync_post_deletion(del_results_2)

        # Now group only has f1 remaining (< 2 files) -> group is pruned and results are empty
        self.assertEqual(len(container.duplicate_groups), 0)
        self.assertEqual(container.heading.text(), "Scan Complete — No Duplicates Found")

    def test_confirmation_dialog_components(self):
        files_data = [
            {"path": "C:/fake/path1.txt", "name": "path1.txt", "size": "10 MB", "size_bytes": 10 * 1024 * 1024},
            {"path": "C:/fake/path2.txt", "name": "path2.txt", "size": "5 MB", "size_bytes": 5 * 1024 * 1024},
        ]
        dialog = DeletionConfirmationDialog(files_data)
        self.assertEqual(dialog.file_list.count(), 2)
        self.assertIn("path1.txt", dialog.file_list.item(0).text())
        dialog.close()


if __name__ == "__main__":
    unittest.main()
