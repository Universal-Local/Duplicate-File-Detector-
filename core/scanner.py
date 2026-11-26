"""Directory scanner and duplicate detection pipeline.

Executes a multi-stage duplicate detection algorithm:
  1. Traversal & Size Binning: Recursively scan directories, collect file stats,
     and group files by exact size. Unique file sizes are immediately dropped.
  2. Quick Hash Filtering: For size collisions, hash the initial 16 KB chunk.
     Groups with unique quick hashes are discarded without reading whole files.
  3. Full SHA-256 Hashing: Perform streaming SHA-256 hashing on remaining candidates.
  4. Duplicate Group Assembly: Group files sharing identical size and full SHA-256.

Designed with:
  - Symlink and Windows junction safety (preventing directory-traversal recursion cycles).
  - Concurrency checks (discarding files modified during scan).
  - Graceful handling of inaccessible folders and permission errors.
  - Cooperative cancellation tracking.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Set, Tuple

from core.hasher import compute_sha256, quick_sha256_sample
from core.models import (
    DuplicateGroup,
    FileInfo,
    FileStatus,
    ScanSettings,
    ScanStats,
)

ProgressCallback = Callable[[str, int, int, str], None]
CancelCallback = Callable[[], bool]


class FileScanner:
    """Core scanner and duplicate detector."""

    def __init__(self, settings: Optional[ScanSettings] = None):
        self.settings = settings or ScanSettings()

    def scan_directory(
        self,
        folder_path: str,
        progress_cb: Optional[ProgressCallback] = None,
        cancel_cb: Optional[CancelCallback] = None,
    ) -> Tuple[List[DuplicateGroup], ScanStats]:
        """Scan a folder and return discovered duplicate groups and scan statistics."""
        start_time = time.time()
        stats = ScanStats()
        norm_root = os.path.normpath(os.path.abspath(folder_path))

        if not os.path.isdir(norm_root):
            stats.duration_seconds = time.time() - start_time
            return [], stats

        # Phase 1: Directory Traversal and Size Binning
        if progress_cb:
            progress_cb("indexing", 0, 0, f"Indexing {norm_root}...")

        size_map, total_scanned_count, total_scanned_bytes = self._index_files(
            norm_root, stats, progress_cb, cancel_cb
        )

        stats.total_files_scanned = total_scanned_count
        stats.total_size_scanned_bytes = total_scanned_bytes

        if cancel_cb and cancel_cb():
            stats.was_cancelled = True
            stats.duration_seconds = time.time() - start_time
            return [], stats

        # Filter out unique sizes (cannot be duplicates)
        candidate_sizes: Dict[int, List[FileInfo]] = {
            size: files for size, files in size_map.items() if len(files) >= 2
        }
        stats.candidate_size_groups = len(candidate_sizes)

        total_candidates = sum(len(files) for files in candidate_sizes.values())
        if total_candidates == 0:
            stats.duration_seconds = time.time() - start_time
            return [], stats

        # Phase 2: Quick Hash Filtering (first 16 KB sample)
        quick_hash_groups, processed_quick = self._quick_hash_candidates(
            candidate_sizes, total_candidates, stats, progress_cb, cancel_cb
        )

        if cancel_cb and cancel_cb():
            stats.was_cancelled = True
            stats.duration_seconds = time.time() - start_time
            return [], stats

        # Total files requiring full SHA-256
        full_hash_candidates_count = sum(len(f_list) for f_list in quick_hash_groups.values())

        # Phase 3: Full SHA-256 Hashing
        full_hash_groups = self._full_hash_candidates(
            quick_hash_groups, full_hash_candidates_count, stats, progress_cb, cancel_cb
        )

        if cancel_cb and cancel_cb():
            stats.was_cancelled = True
            stats.duration_seconds = time.time() - start_time
            return [], stats

        # Phase 4: Construct Duplicate Groups
        duplicate_groups: List[DuplicateGroup] = []
        group_counter = 1

        for (size, sha256_val), files in sorted(full_hash_groups.items(), key=lambda x: -x[0][0]):
            if len(files) < 2:
                continue

            # Default retention heuristic: Keep oldest modified file
            files.sort(key=lambda f: f.mtime)
            files[0].status = FileStatus.KEEP
            for f in files[1:]:
                f.status = FileStatus.DUPLICATE

            group_name = files[0].name
            group_id = f"group_{group_counter}_{sha256_val[:10]}"
            group_counter += 1

            group = DuplicateGroup(
                group_id=group_id,
                group_name=group_name,
                file_size=size,
                sha256=sha256_val,
                files=files,
            )
            duplicate_groups.append(group)

            stats.duplicate_files_count += len(files) - 1
            stats.wasted_space_bytes += (len(files) - 1) * size

        stats.duplicate_groups_count = len(duplicate_groups)
        stats.duration_seconds = time.time() - start_time

        if progress_cb:
            progress_cb(
                "completed",
                stats.total_files_scanned,
                stats.total_files_scanned,
                f"Completed in {stats.duration_seconds:.2f}s",
            )

        return duplicate_groups, stats

    def _index_files(
        self,
        root_dir: str,
        stats: ScanStats,
        progress_cb: Optional[ProgressCallback],
        cancel_cb: Optional[CancelCallback],
    ) -> Tuple[Dict[int, List[FileInfo]], int, int]:
        """Traverse directory, collect file sizes, and group files with identical sizes."""
        size_map: Dict[int, List[FileInfo]] = defaultdict(list)
        total_files = 0
        total_bytes = 0
        visited_canonical_dirs: Set[str] = set()

        try:
            canonical_root = os.path.realpath(root_dir).lower()
            visited_canonical_dirs.add(canonical_root)
        except OSError:
            pass

        dir_stack = [root_dir]
        reported_count = 0

        while dir_stack:
            if cancel_cb and cancel_cb():
                break

            current_dir = dir_stack.pop()

            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        if cancel_cb and cancel_cb():
                            break

                        name = entry.name

                        # Check Windows junction or symlink
                        is_link = entry.is_symlink() or (
                            hasattr(entry, "is_junction") and entry.is_junction()
                        )

                        # Handle Directories
                        if entry.is_dir(follow_symlinks=False):
                            if name in self.settings.excluded_folders or name.startswith("."):
                                continue

                            # Symlink / Junction policy: ignore by default to prevent cycles
                            if is_link:
                                if not self.settings.follow_symlinks:
                                    continue
                                # Loop prevention if symlinks are enabled
                                try:
                                    canonical_path = os.path.realpath(entry.path).lower()
                                    if canonical_path in visited_canonical_dirs:
                                        continue
                                    visited_canonical_dirs.add(canonical_path)
                                except OSError:
                                    continue
                            else:
                                try:
                                    canonical_path = os.path.realpath(entry.path).lower()
                                    if canonical_path in visited_canonical_dirs:
                                        continue
                                    visited_canonical_dirs.add(canonical_path)
                                except OSError:
                                    pass

                            dir_stack.append(entry.path)
                            continue

                        # Handle Regular Files
                        if entry.is_file(follow_symlinks=False):
                            if is_link and not self.settings.follow_symlinks:
                                continue

                            # Extension exclusions
                            _, ext = os.path.splitext(name)
                            if ext.lower() in self.settings.excluded_extensions:
                                continue

                            try:
                                stat_res = entry.stat()
                                file_size = stat_res.st_size

                                if file_size < self.settings.min_size_bytes:
                                    continue
                                if (
                                    self.settings.max_size_bytes is not None
                                    and file_size > self.settings.max_size_bytes
                                ):
                                    continue

                                norm_path = os.path.normpath(entry.path)
                                file_info = FileInfo(
                                    path=norm_path,
                                    name=name,
                                    size=file_size,
                                    mtime=stat_res.st_mtime,
                                )

                                size_map[file_size].append(file_info)
                                total_files += 1
                                total_bytes += file_size
                                reported_count += 1

                                if progress_cb and (reported_count % 50 == 0):
                                    progress_cb(
                                        "indexing",
                                        reported_count,
                                        0,
                                        f"Indexing: {name}",
                                    )

                            except PermissionError:
                                stats.permission_denied_count += 1
                                stats.inaccessible_files.append(entry.path)
                            except (FileNotFoundError, OSError):
                                stats.inaccessible_files.append(entry.path)

            except PermissionError:
                stats.permission_denied_count += 1
                stats.inaccessible_files.append(current_dir)
            except (FileNotFoundError, OSError):
                stats.inaccessible_files.append(current_dir)

        return size_map, total_files, total_bytes

    def _quick_hash_candidates(
        self,
        candidate_sizes: Dict[int, List[FileInfo]],
        total_candidates: int,
        stats: ScanStats,
        progress_cb: Optional[ProgressCallback],
        cancel_cb: Optional[CancelCallback],
    ) -> Tuple[Dict[Tuple[int, str], List[FileInfo]], int]:
        """Compute quick 16 KB partial hashes for files with size collisions."""
        quick_hash_map: Dict[Tuple[int, str], List[FileInfo]] = defaultdict(list)
        processed = 0

        for size, file_list in candidate_sizes.items():
            for file_info in file_list:
                if cancel_cb and cancel_cb():
                    return {}, processed

                processed += 1
                if progress_cb and (processed % 10 == 0 or processed == total_candidates):
                    progress_cb(
                        "quick_hashing",
                        processed,
                        total_candidates,
                        f"Quick scan: {file_info.name}",
                    )

                # Compute quick sample hash with concurrency checks
                q_hash = quick_sha256_sample(
                    file_info.path,
                    sample_size=self.settings.quick_hash_sample_size,
                    expected_size=file_info.size,
                    expected_mtime=file_info.mtime,
                    cancel_check=cancel_cb,
                )

                if q_hash is not None:
                    file_info.quick_hash = q_hash
                    quick_hash_map[(size, q_hash)].append(file_info)
                else:
                    # File may have changed or become inaccessible
                    stats.inaccessible_files.append(file_info.path)

        # Discard groups that have only 1 file with this (size, quick_hash)
        filtered_groups = {k: v for k, v in quick_hash_map.items() if len(v) >= 2}
        return filtered_groups, processed

    def _full_hash_candidates(
        self,
        quick_groups: Dict[Tuple[int, str], List[FileInfo]],
        total_to_hash: int,
        stats: ScanStats,
        progress_cb: Optional[ProgressCallback],
        cancel_cb: Optional[CancelCallback],
    ) -> Dict[Tuple[int, str], List[FileInfo]]:
        """Compute complete chunked SHA-256 digests for remaining candidates."""
        full_hash_map: Dict[Tuple[int, str], List[FileInfo]] = defaultdict(list)
        processed = 0

        for (size, _), file_list in quick_groups.items():
            for file_info in file_list:
                if cancel_cb and cancel_cb():
                    return {}

                processed += 1
                if progress_cb:
                    progress_cb(
                        "full_hashing",
                        processed,
                        total_to_hash,
                        f"Verifying SHA-256: {file_info.name}",
                    )

                # If file size is smaller than sample size, full SHA-256 equals quick hash
                if size <= self.settings.quick_hash_sample_size and file_info.quick_hash:
                    full_hash = file_info.quick_hash
                else:
                    full_hash = compute_sha256(
                        file_info.path,
                        chunk_size=self.settings.chunk_size,
                        expected_size=file_info.size,
                        expected_mtime=file_info.mtime,
                        cancel_check=cancel_cb,
                    )

                if full_hash is not None:
                    file_info.sha256 = full_hash
                    full_hash_map[(size, full_hash)].append(file_info)
                else:
                    # File changed or inaccessible
                    stats.inaccessible_files.append(file_info.path)

        # Filter for actual confirmed duplicate groups
        return {k: v for k, v in full_hash_map.items() if len(v) >= 2}
