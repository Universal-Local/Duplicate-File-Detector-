"""Settings view widget.

Allows users to configure scan preferences (minimum/maximum file size, excluded
folders, excluded extensions, symlink rules), validates input constraints, and
persists preferences between launches.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.config import (
    DEFAULT_EXCLUDED_EXTENSIONS,
    DEFAULT_EXCLUDED_FOLDERS,
    load_settings,
    sanitize_extensions,
    sanitize_folders,
    save_settings,
    validate_settings,
)
from core.models import ScanSettings


class SettingsView(QWidget):
    """View panel for managing and persisting scanner configuration."""

    settings_saved = Signal(ScanSettings)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_settings = load_settings()
        self.setup_ui()

    def setup_ui(self) -> None:
        """Initialize UI controls and dark styling."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(15)

        # Header Section
        header = QVBoxLayout()
        header.setSpacing(4)

        title = QLabel("Application Settings")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        header.addWidget(title)

        subtitle = QLabel("Configure scan filters, exclusions, and safety rules.")
        subtitle.setStyleSheet("color: #92959c; font-size: 13px;")
        header.addWidget(subtitle)

        main_layout.addLayout(header)

        # Scrollable form container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        form_layout = QVBoxLayout(container)
        form_layout.setSpacing(18)

        # 1. File Size Filters Card
        size_card = self._create_card("File Size Filters")
        size_layout = QVBoxLayout(size_card)
        size_layout.setSpacing(12)

        min_row = QHBoxLayout()
        min_label = QLabel("Minimum File Size (KB):")
        min_label.setStyleSheet("color: #e8e8e8; font-size: 13px;")
        self.min_size_spin = QSpinBox()
        self.min_size_spin.setRange(0, 10_000_000)
        self.min_size_spin.setValue(max(0, self.current_settings.min_size_bytes // 1024))
        self.min_size_spin.setFixedWidth(130)
        self.min_size_spin.setStyleSheet(self._input_style())
        min_row.addWidget(min_label)
        min_row.addStretch()
        min_row.addWidget(self.min_size_spin)
        size_layout.addLayout(min_row)

        max_row = QHBoxLayout()
        self.enable_max_check = QCheckBox("Enable Maximum File Size Limit (MB):")
        self.enable_max_check.setStyleSheet("color: #e8e8e8; font-size: 13px;")
        has_max = self.current_settings.max_size_bytes is not None
        self.enable_max_check.setChecked(has_max)

        self.max_size_spin = QSpinBox()
        self.max_size_spin.setRange(1, 100_000)
        max_val_mb = (self.current_settings.max_size_bytes // (1024 * 1024)) if has_max else 500
        self.max_size_spin.setValue(max_val_mb)
        self.max_size_spin.setEnabled(has_max)
        self.max_size_spin.setFixedWidth(130)
        self.max_size_spin.setStyleSheet(self._input_style())

        self.enable_max_check.toggled.connect(self.max_size_spin.setEnabled)

        max_row.addWidget(self.enable_max_check)
        max_row.addStretch()
        max_row.addWidget(self.max_size_spin)
        size_layout.addLayout(max_row)

        form_layout.addWidget(size_card)

        # 2. Excluded Folders Card
        folder_card = self._create_card("Excluded Folders (comma separated)")
        folder_layout = QVBoxLayout(folder_card)
        folder_layout.setSpacing(8)

        folder_desc = QLabel("Directories matching these names will be skipped during scans:")
        folder_desc.setStyleSheet("color: #92959c; font-size: 12px;")
        folder_layout.addWidget(folder_desc)

        self.folder_edit = QLineEdit()
        self.folder_edit.setText(", ".join(sorted(self.current_settings.excluded_folders)))
        self.folder_edit.setStyleSheet(self._input_style())
        folder_layout.addWidget(self.folder_edit)

        form_layout.addWidget(folder_card)

        # 3. Excluded Extensions Card
        ext_card = self._create_card("Excluded File Extensions (comma separated)")
        ext_layout = QVBoxLayout(ext_card)
        ext_layout.setSpacing(8)

        ext_desc = QLabel("Files ending with these extensions will be ignored (e.g. .tmp, .bak, .log):")
        ext_desc.setStyleSheet("color: #92959c; font-size: 12px;")
        ext_layout.addWidget(ext_desc)

        self.ext_edit = QLineEdit()
        self.ext_edit.setText(", ".join(sorted(self.current_settings.excluded_extensions)))
        self.ext_edit.setStyleSheet(self._input_style())
        ext_layout.addWidget(self.ext_edit)

        form_layout.addWidget(ext_card)

        # 4. Symlink Handling Card
        symlink_card = self._create_card("Symlink and Junction Policy")
        sym_layout = QVBoxLayout(symlink_card)

        self.symlink_check = QCheckBox("Follow directory symlinks and junctions (Caution: may increase scan time)")
        self.symlink_check.setChecked(self.current_settings.follow_symlinks)
        self.symlink_check.setStyleSheet("color: #e8e8e8; font-size: 13px;")
        sym_layout.addWidget(self.symlink_check)

        form_layout.addWidget(symlink_card)

        form_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll, 1)

        # Bottom Buttons
        btn_layout = QHBoxLayout()

        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #2c2f36;
                color: #b5b7bd;
                border: 1px solid #41444c;
                border-radius: 6px;
                padding: 9px 18px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #383b44;
                color: white;
            }
        """)
        self.reset_btn.clicked.connect(self.reset_defaults)
        btn_layout.addWidget(self.reset_btn)

        btn_layout.addStretch()

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d7bf0;
                color: white;
                border-radius: 6px;
                padding: 9px 24px;
                font-weight: bold;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                background-color: #508cf7;
            }
        """)
        self.save_btn.clicked.connect(self.save_current_settings)
        btn_layout.addWidget(self.save_btn)

        main_layout.addLayout(btn_layout)

    def _create_card(self, title: str) -> QFrame:
        """Create a styled card container for settings groups."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #202226;
                border: 1px solid #34373e;
                border-radius: 10px;
                padding: 14px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)

        header = QLabel(title)
        header.setStyleSheet("color: white; font-size: 14px; font-weight: bold; border: none;")
        card_layout.addWidget(header)
        return card

    @staticmethod
    def _input_style() -> str:
        """Standard input control styling."""
        return """
            QLineEdit, QSpinBox {
                background-color: #17181b;
                color: white;
                border: 1px solid #41444c;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid #3d7bf0;
            }
        """

    def save_current_settings(self) -> None:
        """Validate input fields and persist settings."""
        min_bytes = self.min_size_spin.value() * 1024
        max_bytes = (self.max_size_spin.value() * 1024 * 1024) if self.enable_max_check.isChecked() else None

        raw_folders = [f.strip() for f in self.folder_edit.text().split(",") if f.strip()]
        raw_exts = [e.strip() for e in self.ext_edit.text().split(",") if e.strip()]

        folders = sanitize_folders(raw_folders)
        exts = sanitize_extensions(raw_exts)
        symlinks = self.symlink_check.isChecked()

        is_valid, errors = validate_settings(min_bytes, max_bytes, folders, exts, symlinks)
        if not is_valid:
            QMessageBox.warning(
                self,
                "Invalid Settings",
                "Please fix the following validation issues:\n\n• " + "\n• ".join(errors),
            )
            return

        new_settings = ScanSettings(
            min_size_bytes=min_bytes,
            max_size_bytes=max_bytes,
            excluded_folders=folders,
            excluded_extensions=exts,
            follow_symlinks=symlinks,
        )

        success, save_errors = save_settings(new_settings)
        if success:
            self.current_settings = new_settings
            self.settings_saved.emit(new_settings)
            QMessageBox.information(
                self,
                "Settings Saved",
                "Scan preferences have been successfully updated and saved.",
            )
        else:
            QMessageBox.critical(
                self,
                "Save Failed",
                "Unable to write settings:\n" + "\n".join(save_errors),
            )

    def reset_defaults(self) -> None:
        """Reset fields to default system preferences."""
        self.min_size_spin.setValue(0)
        self.enable_max_check.setChecked(False)
        self.max_size_spin.setValue(500)
        self.folder_edit.setText(", ".join(sorted(DEFAULT_EXCLUDED_FOLDERS)))
        self.ext_edit.setText(", ".join(sorted(DEFAULT_EXCLUDED_EXTENSIONS)))
        self.symlink_check.setChecked(False)
