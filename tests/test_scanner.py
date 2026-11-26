"""Tests for core.scanner."""

import os
import tempfile
import unittest

from core.models import ScanSettings
from core.scanner import FileScanner


class TestFileScanner(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_detect_identical_files_across_subdirectories(self):
        content_dup = b"Duplicate content for testing files" * 200
        content_unique = b"Unique content that should never match anything else!"

        sub1 = os.path.join(self.root, "sub1")
        sub2 = os.path.join(self.root, "sub2")
        os.makedirs(sub1)
        os.makedirs(sub2)

        p1 = os.path.join(sub1, "file1.txt")
        p2 = os.path.join(sub2, "file2.txt")
        p3 = os.path.join(self.root, "file3.txt")

        with open(p1, "wb") as f:
            f.write(content_dup)
        with open(p2, "wb") as f:
            f.write(content_dup)
        with open(p3, "wb") as f:
            f.write(content_unique)

        scanner = FileScanner()
        groups, stats = scanner.scan_directory(self.root)

        self.assertEqual(stats.total_files_scanned, 3)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].file_size, len(content_dup))
        self.assertEqual(len(groups[0].files), 2)
        self.assertEqual(stats.duplicate_files_count, 1)
        self.assertEqual(stats.wasted_space_bytes, len(content_dup))
        self.assertFalse(stats.was_cancelled)

    def test_same_size_different_content_not_flagged_as_duplicate(self):
        content_a = b"A" * 1000
        content_b = b"B" * 1000

        pa = os.path.join(self.root, "a.bin")
        pb = os.path.join(self.root, "b.bin")

        with open(pa, "wb") as f:
            f.write(content_a)
        with open(pb, "wb") as f:
            f.write(content_b)

        scanner = FileScanner()
        groups, stats = scanner.scan_directory(self.root)

        self.assertEqual(stats.total_files_scanned, 2)
        self.assertEqual(len(groups), 0)
        self.assertEqual(stats.duplicate_files_count, 0)

    def test_excluded_folders_ignored(self):
        git_dir = os.path.join(self.root, ".git")
        os.makedirs(git_dir)

        content = b"Same content"
        p_git = os.path.join(git_dir, "git_file.txt")
        p_root = os.path.join(self.root, "root_file.txt")

        with open(p_git, "wb") as f:
            f.write(content)
        with open(p_root, "wb") as f:
            f.write(content)

        scanner = FileScanner()
        groups, stats = scanner.scan_directory(self.root)

        self.assertEqual(stats.total_files_scanned, 1)
        self.assertEqual(len(groups), 0)

    def test_size_filters(self):
        settings = ScanSettings(min_size_bytes=50, max_size_bytes=200)
        scanner = FileScanner(settings)

        too_small = os.path.join(self.root, "small.txt")
        in_range1 = os.path.join(self.root, "in1.txt")
        in_range2 = os.path.join(self.root, "in2.txt")
        too_big = os.path.join(self.root, "big.txt")

        with open(too_small, "wb") as f:
            f.write(b"x" * 10)
        with open(in_range1, "wb") as f:
            f.write(b"m" * 100)
        with open(in_range2, "wb") as f:
            f.write(b"m" * 100)
        with open(too_big, "wb") as f:
            f.write(b"l" * 500)

        groups, stats = scanner.scan_directory(self.root)

        self.assertEqual(stats.total_files_scanned, 2)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].file_size, 100)

    def test_scan_cancellation_flags_stat(self):
        for i in range(10):
            p = os.path.join(self.root, f"file_{i}.txt")
            with open(p, "wb") as f:
                f.write(b"test" * 50)

        scanner = FileScanner()
        groups, stats = scanner.scan_directory(self.root, cancel_cb=lambda: True)
        self.assertEqual(len(groups), 0)
        self.assertTrue(stats.was_cancelled)

    def test_nonexistent_directory(self):
        scanner = FileScanner()
        groups, stats = scanner.scan_directory(os.path.join(self.root, "missing_folder"))
        self.assertEqual(len(groups), 0)
        self.assertEqual(stats.total_files_scanned, 0)
        self.assertFalse(stats.was_cancelled)


if __name__ == "__main__":
    unittest.main()
