"""Safe file deletion module using the Windows Recycle Bin.

Safely recycles duplicate files using the send2trash library. Enforces strict
pre-flight safety checks:
  1. Never permanently deletes files.
  2. Never deletes files designated as the retained copy.
  3. Revalidates existence, regular file status, size, and modification time.
  4. Cryptographic Identity Check: Re-verifies complete SHA-256 digest for every file
     immediately before recycling, ensuring file content has not altered since scanning.
  5. Handles locked, missing, or concurrently modified files without crashing.
  6. Tracks individual results and aggregate freed space.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import send2trash

from core.hasher import compute_sha256
from core.models import DeletionResult

ProgressCallback = Callable[[int, int, str], None]
CancelCallback = Callable[[], bool]


def recycle_single_file(
    file_data: Dict[str, Any],
    protected_paths: Optional[Set[str]] = None,
    verify_identity_hash: bool = True,
) -> DeletionResult:
    """Move a single duplicate file to the Windows Recycle Bin after strict validation.

    Args:
        file_data: Dictionary containing at least 'path', and optionally 'size_bytes',
                   'mtime', 'status', 'sha256'.
        protected_paths: Set of normalized paths that must NEVER be deleted (e.g. kept copies).
        verify_identity_hash: Whether to perform pre-recycle cryptographic hash verification.

    Returns:
        DeletionResult indicating success/failure, freed bytes, and error message.
    """
    raw_path = file_data.get("path", "")
    if not raw_path:
        return DeletionResult(
            file_path="",
            success=False,
            error_message="Invalid file path provided.",
        )

    norm_path = os.path.normpath(os.path.abspath(raw_path))

    # Safety Guard 1: Retained copy protection
    if file_data.get("status") == "Keep":
        return DeletionResult(
            file_path=norm_path,
            success=False,
            error_message="Cannot delete: this file is designated as the retained copy.",
        )

    if protected_paths and norm_path in protected_paths:
        return DeletionResult(
            file_path=norm_path,
            success=False,
            error_message="Cannot delete: file is in the protected retention list.",
        )

    # Safety Guard 2: File existence and regular file verification
    if not os.path.exists(norm_path):
        return DeletionResult(
            file_path=norm_path,
            success=False,
            error_message="File not found on disk. It may have already been moved or deleted.",
        )

    if not os.path.isfile(norm_path):
        return DeletionResult(
            file_path=norm_path,
            success=False,
            error_message="Target is not a regular file; directory deletion is prohibited.",
        )

    # Safety Guard 3: Revalidate file size and modification time
    try:
        current_stat = os.stat(norm_path)
    except (PermissionError, FileNotFoundError, OSError) as exc:
        return DeletionResult(
            file_path=norm_path,
            success=False,
            error_message=f"Unable to read file metadata before deletion: {exc}",
        )

    expected_size = file_data.get("size_bytes")
    if expected_size is not None and current_stat.st_size != expected_size:
        return DeletionResult(
            file_path=norm_path,
            success=False,
            error_message=(
                f"File size changed since scan (was {expected_size} B, now {current_stat.st_size} B). "
                "Deletion aborted to prevent data loss."
            ),
        )

    expected_mtime = file_data.get("mtime")
    if expected_mtime is not None and current_stat.st_mtime != expected_mtime:
        return DeletionResult(
            file_path=norm_path,
            success=False,
            error_message=(
                "File was modified after the scan. Deletion aborted to prevent data loss."
            ),
        )

    # Safety Guard 4: Cryptographic identity verification (Complete SHA-256 for all files)
    expected_sha256 = file_data.get("sha256")
    if verify_identity_hash and expected_sha256:
        current_hash = compute_sha256(
            norm_path,
            expected_size=current_stat.st_size,
            expected_mtime=current_stat.st_mtime,
        )
        if current_hash != expected_sha256:
            return DeletionResult(
                file_path=norm_path,
                success=False,
                error_message="Cryptographic verification failed: file content altered since scan.",
            )

    freed_bytes = current_stat.st_size

    # Safety Guard 5: Move to Recycle Bin via send2trash
    try:
        send2trash.send2trash(norm_path)

        if os.path.exists(norm_path):
            return DeletionResult(
                file_path=norm_path,
                success=False,
                error_message="File could not be removed by the Recycle Bin operation.",
            )

        return DeletionResult(
            file_path=norm_path,
            success=True,
            freed_bytes=freed_bytes,
        )

    except PermissionError:
        return DeletionResult(
            file_path=norm_path,
            success=False,
            error_message="Access denied: file is currently locked or requires administrator rights.",
        )
    except Exception as exc:  # pylint: disable=broad-except
        return DeletionResult(
            file_path=norm_path,
            success=False,
            error_message=f"Recycle Bin error: {exc}",
        )


def recycle_files(
    files_to_delete: List[Dict[str, Any]],
    protected_paths: Optional[Set[str]] = None,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
    verify_identity_hash: bool = True,
) -> Tuple[List[DeletionResult], int, int]:
    """Recycle multiple files in sequence with live progress and cancellation."""
    results: List[DeletionResult] = []
    total_files = len(files_to_delete)
    succeeded_count = 0
    total_freed_bytes = 0

    norm_protected = {os.path.normpath(p) for p in (protected_paths or set())}

    for idx, file_data in enumerate(files_to_delete, start=1):
        if cancel_cb and cancel_cb():
            break

        path_name = file_data.get("name") or os.path.basename(file_data.get("path", ""))
        if progress_cb:
            progress_cb(idx, total_files, f"Recycling {path_name}")

        result = recycle_single_file(
            file_data,
            protected_paths=norm_protected,
            verify_identity_hash=verify_identity_hash,
        )
        results.append(result)

        if result.success:
            succeeded_count += 1
            total_freed_bytes += result.freed_bytes

    return results, succeeded_count, total_freed_bytes
