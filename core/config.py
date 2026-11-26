"""Settings management, validation, and JSON persistence.

Handles loading, validating, and persisting user configuration between application
sessions in a standard cross-platform user configuration directory.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.models import ScanSettings

DEFAULT_EXCLUDED_FOLDERS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "$RECYCLE.BIN",
    "System Volume Information",
    ".idea",
    ".vscode",
    "node_modules",
}

DEFAULT_EXCLUDED_EXTENSIONS = {
    ".tmp",
    ".bak",
    ".log",
    ".sys",
}


def get_default_config_path() -> Path:
    """Return the absolute path to the configuration JSON file in user AppData/Home."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        base_dir = Path(appdata) / "DuplicateFileDetector"
    else:
        base_dir = Path.home() / ".duplicate_file_detector"

    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "settings.json"


def validate_settings(
    min_size_bytes: int,
    max_size_bytes: Optional[int],
    excluded_folders: Set[str],
    excluded_extensions: Set[str],
    follow_symlinks: bool,
) -> Tuple[bool, List[str]]:
    """Validate settings constraints and return (is_valid, error_messages)."""
    errors: List[str] = []

    if min_size_bytes < 0:
        errors.append("Minimum file size cannot be negative.")

    if max_size_bytes is not None:
        if max_size_bytes < 0:
            errors.append("Maximum file size cannot be negative.")
        elif max_size_bytes < min_size_bytes:
            errors.append("Maximum file size must be greater than or equal to minimum file size.")

    # Validate extensions
    valid_ext_re = re.compile(r"^\.[a-zA-Z0-9_\-]+$")
    for ext in excluded_extensions:
        if not ext.startswith("."):
            errors.append(f"Extension '{ext}' must start with a period (e.g. '.tmp').")
        elif not valid_ext_re.match(ext):
            errors.append(f"Extension '{ext}' contains invalid characters.")

    # Validate folder names
    invalid_folder_chars = set(r'<>:"/\|?*')
    for folder in excluded_folders:
        if any(c in folder for c in invalid_folder_chars):
            errors.append(f"Folder name '{folder}' contains prohibited path characters.")

    return len(errors) == 0, errors


def sanitize_extensions(raw_extensions: List[str]) -> Set[str]:
    """Clean and normalize a list of extension strings."""
    cleaned = set()
    for item in raw_extensions:
        ext = item.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = "." + ext
        cleaned.add(ext)
    return cleaned


def sanitize_folders(raw_folders: List[str]) -> Set[str]:
    """Clean and normalize a list of folder names."""
    cleaned = set()
    for item in raw_folders:
        folder = item.strip()
        if folder:
            cleaned.add(folder)
    return cleaned


def load_settings(config_path: Optional[Path] = None) -> ScanSettings:
    """Load settings from JSON file or return defaults if file is missing/invalid."""
    path = config_path or get_default_config_path()

    if not path.exists():
        return ScanSettings(
            excluded_folders=set(DEFAULT_EXCLUDED_FOLDERS),
            excluded_extensions=set(DEFAULT_EXCLUDED_EXTENSIONS),
        )

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        min_size = int(data.get("min_size_bytes", 1))
        max_size = data.get("max_size_bytes")
        if max_size is not None:
            max_size = int(max_size)

        folders = sanitize_folders(data.get("excluded_folders", list(DEFAULT_EXCLUDED_FOLDERS)))
        extensions = sanitize_extensions(data.get("excluded_extensions", list(DEFAULT_EXCLUDED_EXTENSIONS)))
        symlinks = bool(data.get("follow_symlinks", False))

        is_valid, _ = validate_settings(min_size, max_size, folders, extensions, symlinks)
        if not is_valid:
            # Fallback to defaults on corrupt config
            return ScanSettings(
                excluded_folders=set(DEFAULT_EXCLUDED_FOLDERS),
                excluded_extensions=set(DEFAULT_EXCLUDED_EXTENSIONS),
            )

        return ScanSettings(
            min_size_bytes=min_size,
            max_size_bytes=max_size,
            excluded_folders=folders,
            excluded_extensions=extensions,
            follow_symlinks=symlinks,
        )

    except (json.JSONDecodeError, OSError, ValueError):
        return ScanSettings(
            excluded_folders=set(DEFAULT_EXCLUDED_FOLDERS),
            excluded_extensions=set(DEFAULT_EXCLUDED_EXTENSIONS),
        )


def save_settings(settings: ScanSettings, config_path: Optional[Path] = None) -> Tuple[bool, List[str]]:
    """Validate and persist ScanSettings to JSON file."""
    is_valid, errors = validate_settings(
        min_size_bytes=settings.min_size_bytes,
        max_size_bytes=settings.max_size_bytes,
        excluded_folders=settings.excluded_folders,
        excluded_extensions=settings.excluded_extensions,
        follow_symlinks=settings.follow_symlinks,
    )

    if not is_valid:
        return False, errors

    path = config_path or get_default_config_path()
    try:
        data = {
            "min_size_bytes": settings.min_size_bytes,
            "max_size_bytes": settings.max_size_bytes,
            "excluded_folders": sorted(list(settings.excluded_folders)),
            "excluded_extensions": sorted(list(settings.excluded_extensions)),
            "follow_symlinks": settings.follow_symlinks,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True, []
    except OSError as exc:
        return False, [f"Failed to write settings file: {exc}"]
