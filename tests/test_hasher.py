"""Tests for core.hasher."""

import hashlib
import os
import tempfile
import time
import unittest

from core.hasher import compute_sha256, quick_sha256_sample


class TestHasher(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.file_content = b"The quick brown fox jumps over the lazy dog." * 1000
        self.test_file = os.path.join(self.temp_dir.name, "sample.txt")
        with open(self.test_file, "wb") as f:
            f.write(self.file_content)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_compute_sha256_matches_standard(self):
        expected_hash = hashlib.sha256(self.file_content).hexdigest()
        computed_hash = compute_sha256(self.test_file, chunk_size=512)
        self.assertEqual(computed_hash, expected_hash)

    def test_compute_sha256_missing_file_returns_none(self):
        result = compute_sha256(os.path.join(self.temp_dir.name, "nonexistent.file"))
        self.assertIsNone(result)

    def test_compute_sha256_cancellation(self):
        result = compute_sha256(self.test_file, cancel_check=lambda: True)
        self.assertIsNone(result)

    def test_quick_sha256_sample(self):
        sample_size = 64
        expected_sample_hash = hashlib.sha256(self.file_content[:sample_size]).hexdigest()
        quick_hash = quick_sha256_sample(self.test_file, sample_size=sample_size)
        self.assertEqual(quick_hash, expected_sample_hash)

    def test_concurrent_modification_rejected(self):
        # Test expected_size mismatch rejection
        wrong_size_hash = compute_sha256(self.test_file, expected_size=999999)
        self.assertIsNone(wrong_size_hash)

        # Test expected_mtime mismatch rejection
        wrong_mtime_hash = compute_sha256(self.test_file, expected_mtime=12345.0)
        self.assertIsNone(wrong_mtime_hash)


if __name__ == "__main__":
    unittest.main()
