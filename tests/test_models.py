"""Tests for core.models."""

import os
import tempfile
import unittest

from core.models import (
    DuplicateGroup,
    FileInfo,
    FileStatus,
    ScanSettings,
    ScanStats,
    format_bytes,
)


class TestModels(unittest.TestCase):

    def test_format_bytes(self):
        self.assertEqual(format_bytes(0), "0 B")
        self.assertEqual(format_bytes(500), "500 B")
        self.assertEqual(format_bytes(1024), "1.00 KB")
        self.assertEqual(format_bytes(1024 * 1024), "1.00 MB")
        self.assertEqual(format_bytes(int(7.5 * 1024 * 1024)), "7.50 MB")
        self.assertEqual(format_bytes(1024 * 1024 * 1024), "1.00 GB")

    def test_file_info_from_path(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tf:
            tf.write(b"Hello World Test")
            temp_path = tf.name

        try:
            info = FileInfo.from_path(temp_path)
            self.assertEqual(info.size, 16)
            self.assertEqual(info.name, os.path.basename(temp_path))
            self.assertEqual(info.status, FileStatus.DUPLICATE)
            self.assertIn("16 B", info.formatted_size)

            d = info.to_dict()
            self.assertEqual(d["name"], info.name)
            self.assertEqual(d["path"], info.path)
            self.assertEqual(d["size_bytes"], 16)
            self.assertEqual(d["status"], "Duplicate")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_duplicate_group_mark_keep_and_heuristics(self):
        f1 = FileInfo(path="/docs/a.txt", name="a.txt", size=100, mtime=1000.0, status=FileStatus.DUPLICATE)
        f2 = FileInfo(path="/docs/sub/a_copy.txt", name="a_copy.txt", size=100, mtime=2000.0, status=FileStatus.DUPLICATE)
        f3 = FileInfo(path="/backup/a.txt", name="a.txt", size=100, mtime=500.0, status=FileStatus.DUPLICATE)

        group = DuplicateGroup(
            group_id="grp_1",
            group_name="a.txt",
            file_size=100,
            sha256="abc123sha",
            files=[f1, f2, f3],
        )

        # Mark keep explicitly
        self.assertTrue(group.mark_keep("/docs/sub/a_copy.txt"))
        self.assertEqual(f2.status, FileStatus.KEEP)
        self.assertEqual(f1.status, FileStatus.DUPLICATE)
        self.assertEqual(f3.status, FileStatus.DUPLICATE)
        self.assertEqual(group.wasted_size_bytes, 200)

        # Heuristic: oldest (f3 mtime=500)
        group.apply_heuristic("oldest")
        self.assertEqual(f3.status, FileStatus.KEEP)
        self.assertEqual(f1.status, FileStatus.DUPLICATE)
        self.assertEqual(f2.status, FileStatus.DUPLICATE)

        # Heuristic: newest (f2 mtime=2000)
        group.apply_heuristic("newest")
        self.assertEqual(f2.status, FileStatus.KEEP)
        self.assertEqual(f3.status, FileStatus.DUPLICATE)

        # Heuristic: shortest_path (f1 is '/docs/a.txt' -> 11 chars)
        group.apply_heuristic("shortest_path")
        self.assertEqual(f1.status, FileStatus.KEEP)

    def test_duplicate_group_to_dict(self):
        f1 = FileInfo(path="/a.txt", name="a.txt", size=50, mtime=100.0, status=FileStatus.KEEP)
        f2 = FileInfo(path="/b.txt", name="b.txt", size=50, mtime=200.0, status=FileStatus.DUPLICATE)
        group = DuplicateGroup("g1", "a.txt", 50, "hash123", [f1, f2])

        d = group.to_dict()
        self.assertEqual(d["group_id"], "g1")
        self.assertEqual(d["file_size"], 50)
        self.assertEqual(len(d["files"]), 2)
        self.assertEqual(d["files"][0]["status"], "Keep")
        self.assertEqual(d["files"][1]["status"], "Duplicate")


if __name__ == "__main__":
    unittest.main()
