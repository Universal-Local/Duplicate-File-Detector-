"""Streaming SHA-256 Hasher.

Computes cryptographic SHA-256 digests in chunks to maintain a minimal, constant
memory footprint regardless of file size. Supports fast partial hashing for early
filtering of non-identical files, cooperative cancellation checks, and verification
against concurrent file modifications.
"""

from __future__ import annotations

import hashlib
import os
from typing import Callable, Optional

DEFAULT_CHUNK_SIZE = 64 * 1024  # 64 KB
DEFAULT_SAMPLE_SIZE = 16 * 1024  # 16 KB


def compute_sha256(
    file_path: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_bytes: Optional[int] = None,
    expected_size: Optional[int] = None,
    expected_mtime: Optional[float] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Optional[str]:
    """Compute the SHA-256 hash of a file using chunked streaming.

    Includes concurrency safety: verifies that file size and modification time
    do not change during hashing to prevent false duplicate results.

    Args:
        file_path: Path to the target file.
        chunk_size: Size of read chunks in bytes (default 64 KB).
        max_bytes: If specified, only hash up to this many bytes from start.
        expected_size: Expected file size in bytes; rejected if file does not match.
        expected_mtime: Expected mtime; rejected if modified during or prior to hashing.
        cancel_check: Optional callable returning True if the operation should be cancelled.

    Returns:
        Hexadecimal SHA-256 digest string, or None if reading failed, was cancelled,
        or if the file was modified concurrently.
    """
    try:
        stat_before = os.stat(file_path)

        if expected_size is not None and stat_before.st_size != expected_size:
            return None
        if expected_mtime is not None and stat_before.st_mtime != expected_mtime:
            return None

        hasher = hashlib.sha256()
        bytes_read_total = 0

        with open(file_path, "rb") as f:
            while True:
                if cancel_check and cancel_check():
                    return None

                to_read = chunk_size
                if max_bytes is not None:
                    remaining = max_bytes - bytes_read_total
                    if remaining <= 0:
                        break
                    to_read = min(chunk_size, remaining)

                chunk = f.read(to_read)
                if not chunk:
                    break

                hasher.update(chunk)
                bytes_read_total += len(chunk)

                if max_bytes is not None and bytes_read_total >= max_bytes:
                    break

        # Post-hash concurrency check: ensure file was not altered while being read
        stat_after = os.stat(file_path)
        if stat_after.st_mtime != stat_before.st_mtime or stat_after.st_size != stat_before.st_size:
            return None

        # If a full hash was requested (max_bytes is None), ensure total read matches stat size
        if max_bytes is None and bytes_read_total != stat_after.st_size:
            return None

        return hasher.hexdigest()

    except (PermissionError, FileNotFoundError, OSError):
        return None


def quick_sha256_sample(
    file_path: str,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    expected_size: Optional[int] = None,
    expected_mtime: Optional[float] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Optional[str]:
    """Compute a fast partial SHA-256 hash using only the first chunk of a file.

    Args:
        file_path: Path to the file.
        sample_size: Maximum bytes to read for the sample (default 16 KB).
        expected_size: Optional expected file size.
        expected_mtime: Optional expected modification timestamp.
        cancel_check: Optional cancellation check callable.

    Returns:
        Hexadecimal partial SHA-256 digest string, or None on failure, cancellation,
        or concurrent modification.
    """
    return compute_sha256(
        file_path=file_path,
        chunk_size=sample_size,
        max_bytes=sample_size,
        expected_size=expected_size,
        expected_mtime=expected_mtime,
        cancel_check=cancel_check,
    )
