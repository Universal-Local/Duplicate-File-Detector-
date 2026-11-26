"""Data models and interfaces for the Duplicate File Detector.

This module defines independent data structures for files, duplicate groups,
scan settings, scan statistics, and deletion results. It provides a clean,
well-documented interface decoupled from the UI and background workers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class FileStatus(str, Enum):
    """Status indicating whether a file in a duplicate group should be kept or deleted."""
    KEEP = "Keep"
    DUPLICATE = "Duplicate"


def format_bytes(num_bytes: int) -> str:
    """Format bytes into human-readable strings (e.g. 7.2 MB, 1.05 GB)."""
    if num_bytes < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    unit_idx = 0
    while size >= 1024.0 and unit_idx < len(units) - 1:
        size /= 1024.0
        unit_idx += 1
    if unit_idx == 0:
        return f"{int(size)} B"
    return f"{size:.2f} {units[unit_idx]}"


@dataclass
class FileInfo:
    """Represents a discovered file and its metadata.

    Attributes:
        path: Absolute normalized path to the file.
        name: Base file name (including extension).
        size: Exact file size in bytes.
        mtime: Last modified timestamp (POSIX epoch float).
        status: FileStatus.KEEP if this file should be retained, FileStatus.DUPLICATE otherwise.
        sha256: Hexadecimal SHA-256 hash, computed during the scanning phase.
        quick_hash: Hexadecimal partial SHA-256 hash for early collision elimination.
    """
    path: str
    name: str
    size: int
    mtime: float
    status: FileStatus = FileStatus.DUPLICATE
    sha256: Optional[str] = None
    quick_hash: Optional[str] = None

    @classmethod
    def from_path(cls, path: str, status: FileStatus = FileStatus.DUPLICATE) -> FileInfo:
        """Create a FileInfo instance from an existing file path."""
        norm_path = os.path.normpath(os.path.abspath(path))
        stat_result = os.stat(norm_path)
        return cls(
            path=norm_path,
            name=os.path.basename(norm_path),
            size=stat_result.st_size,
            mtime=stat_result.st_mtime,
            status=status,
        )

    @property
    def formatted_size(self) -> str:
        """Human-readable file size."""
        return format_bytes(self.size)

    @property
    def formatted_date(self) -> str:
        """Formatted last modified date (YYYY-MM-DD)."""
        return datetime.fromtimestamp(self.mtime).strftime("%Y-%m-%d")

    def to_dict(self) -> Dict[str, Any]:
        """Convert FileInfo into a dictionary compatible with the existing UI components."""
        return {
            "name": self.name,
            "path": self.path,
            "size": self.formatted_size,
            "size_bytes": self.size,
            "date": self.formatted_date,
            "mtime": self.mtime,
            "status": self.status.value,
            "sha256": self.sha256 or "",
        }


@dataclass
class DuplicateGroup:
    """A group of 2 or more identical files identified by identical byte size and SHA-256.

    Attributes:
        group_id: Unique string identifier for this group.
        group_name: Primary display name for the group (typically the name of the kept file).
        file_size: Exact byte size of each file in this group.
        sha256: Full SHA-256 digest of the files.
        files: List of FileInfo objects that share this hash and size.
    """
    group_id: str
    group_name: str
    file_size: int
    sha256: str
    files: List[FileInfo] = field(default_factory=list)

    @property
    def wasted_size_bytes(self) -> int:
        """Total space wasted by duplicates (files marked as DUPLICATE)."""
        duplicates = [f for f in self.files if f.status == FileStatus.DUPLICATE]
        return len(duplicates) * self.file_size

    @property
    def formatted_wasted_size(self) -> str:
        """Human-readable representation of wasted space in this group."""
        return format_bytes(self.wasted_size_bytes)

    def mark_keep(self, target_path: str) -> bool:
        """Set a specific file as KEEP and all others in the group as DUPLICATE.

        Args:
            target_path: Absolute path to the file to keep.

        Returns:
            True if the target file was found and updated, False otherwise.
        """
        target_norm = os.path.normpath(target_path)
        found = False
        for f in self.files:
            if os.path.normpath(f.path) == target_norm:
                f.status = FileStatus.KEEP
                self.group_name = f.name
                found = True
            else:
                f.status = FileStatus.DUPLICATE
        return found

    def apply_heuristic(self, heuristic: str) -> None:
        """Apply an automatic retention heuristic to the group.

        Heuristic options:
            - 'oldest': Keep the file with the earliest modified date.
            - 'newest': Keep the file with the most recent modified date.
            - 'shortest_path': Keep the file with the shortest path string length.
            - 'longest_path': Keep the file with the longest path string length.
        """
        if not self.files:
            return

        heuristic = heuristic.lower().strip()
        if heuristic == "oldest":
            kept = min(self.files, key=lambda f: f.mtime)
        elif heuristic == "newest":
            kept = max(self.files, key=lambda f: f.mtime)
        elif heuristic == "shortest_path":
            kept = min(self.files, key=lambda f: len(f.path))
        elif heuristic == "longest_path":
            kept = max(self.files, key=lambda f: len(f.path))
        else:
            kept = self.files[0]

        self.mark_keep(kept.path)

    def to_dict(self) -> Dict[str, Any]:
        """Convert DuplicateGroup into a dictionary compatible with the existing UI components."""
        return {
            "group_id": self.group_id,
            "group_name": self.group_name,
            "file_size": self.file_size,
            "formatted_size": format_bytes(self.file_size),
            "sha256": self.sha256,
            "files": [f.to_dict() for f in self.files],
        }


@dataclass
class ScanSettings:
    """User-configurable settings for folder scanning and filtering."""
    min_size_bytes: int = 1
    max_size_bytes: Optional[int] = None
    excluded_extensions: Set[str] = field(default_factory=set)
    excluded_folders: Set[str] = field(default_factory=lambda: {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "$RECYCLE.BIN",
        "System Volume Information",
        ".idea",
        ".vscode",
    })
    follow_symlinks: bool = False
    quick_hash_sample_size: int = 16384  # 16 KB partial hash sample size
    chunk_size: int = 65536              # 64 KB chunk size for full hashing


@dataclass
class ScanStats:
    """Statistical summary of a scan execution."""
    total_files_scanned: int = 0
    total_size_scanned_bytes: int = 0
    candidate_size_groups: int = 0
    duplicate_groups_count: int = 0
    duplicate_files_count: int = 0
    wasted_space_bytes: int = 0
    duration_seconds: float = 0.0
    was_cancelled: bool = False
    permission_denied_count: int = 0
    inaccessible_files: List[str] = field(default_factory=list)

    @property
    def formatted_wasted_space(self) -> str:
        """Formatted wasted space."""
        return format_bytes(self.wasted_space_bytes)

    @property
    def formatted_total_size(self) -> str:
        """Formatted total scanned size."""
        return format_bytes(self.total_size_scanned_bytes)


@dataclass
class DeletionResult:
    """Result of an attempted file deletion."""
    file_path: str
    success: bool
    freed_bytes: int = 0
    error_message: Optional[str] = None
