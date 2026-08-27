"""Batch metadata wizard for a folder of media files."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.ui.checkbox_style import CHECKBOX_STYLE_WHITE_LABEL
from karaoke_blast.ui.context_menu_style import CONTEXT_MENU_STYLE
from karaoke_blast.ui.format_config_widget import FormatConfigWidget
from karaoke_blast.ui.video_type_selector import VideoTypeSelectorWidget
from karaoke_blast.ui.visible_space_field import VisibleSpaceLineEdit
from karaoke_blast.ui.metadata_file_dialog import MetadataFileDialog, MetadataResult
from karaoke_blast.ui.recent_folders_panel import PINNED_LABEL
from karaoke_blast.utils.filename_rename import FilenameFormat
from karaoke_blast.utils.media_metadata import has_title_and_artist, supports_metadata
from karaoke_blast.utils.video_types import VideoTypeProfile, find_video_type
from karaoke_blast.utils.video_scanner import scan_videos

_DIALOG_STYLE = """
QDialog {
    background-color: #1e1e2e;
}
"""

_FIELD_STYLE = """
QLineEdit {
    background-color: #2d2d42;
    color: #ffffff;
    border: 1px solid #5a5a72;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
}
"""

_BUTTON_STYLE = """
QPushButton {
    background-color: #e94560;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #ff6b81;
}
QPushButton:disabled {
    background-color: #5a5a72;
    color: #aaa;
}
"""

_SECONDARY_BUTTON_STYLE = """
QPushButton {
    background-color: #2d2d42;
    color: white;
    border: 1px solid #5a5a72;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #3a3a52;
}
"""


class BatchMetadataDialog(QDialog):
    """Pick a folder and tag media files one at a time from filename slots."""

    def __init__(
        self,
        *,
        initial_folder: Path | None = None,
        recent_folders: list[Path] | None = None,
        pinned_folders: list[Path] | None = None,
        pinned_folder_label: str | None = None,
        video_types: list[VideoTypeProfile],
        active_video_type_id: str,
        skip_tagged: bool = True,
        auto_fill_slots: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._video_types = [profile.copy() for profile in video_types]
        self._active_video_type_id = active_video_type_id
        active_profile = find_video_type(self._video_types, active_video_type_id)
        if active_profile is None:
            active_profile = self._video_types[0]
        self._fmt = active_profile.rename_format.copy()
        self._skip_tagged = skip_tagged
        self._auto_fill_slots = auto_fill_slots
        self._folder = initial_folder
        self._recent_folders = list(recent_folders or [])
        self._pinned_folders = list(pinned_folders or [])
        self._pinned_folder_label = pinned_folder_label
        self._applied_count = 0
        self._skipped_count = 0
        self._unsupported_count = 0
        self._failed_count = 0

        self.setWindowTitle("Tag Metadata")
        self.setModal(True)
        self.setMinimumWidth(820)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._type_selector = VideoTypeSelectorWidget(
            video_types=self._video_types,
            active_id=self._active_video_type_id,
        )
        self._type_selector.type_changed.connect(self._on_video_type_changed)
        self._type_selector.types_changed.connect(self._on_video_types_changed)
        layout.addWidget(self._type_selector)

        folder_row = QHBoxLayout()
        folder_label = QLabel("Folder:")
        folder_label.setStyleSheet("color: #ccc; font-size: 13px;")
        self._folder_field = VisibleSpaceLineEdit()
        self._folder_field.setReadOnly(True)
        self._folder_field.setStyleSheet(_FIELD_STYLE)
        self._folder_btn = QPushButton("Choose…")
        self._folder_btn.setStyleSheet(_SECONDARY_BUTTON_STYLE)
        self._folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._folder_btn.clicked.connect(self._show_folder_menu)
        folder_row.addWidget(folder_label)
        folder_row.addWidget(self._folder_field, 1)
        folder_row.addWidget(self._folder_btn)
        layout.addLayout(folder_row)

        self._skip_checkbox = QCheckBox("Skip files that already have Title and Artist")
        self._skip_checkbox.setStyleSheet(CHECKBOX_STYLE_WHITE_LABEL)
        self._skip_checkbox.setChecked(skip_tagged)
        self._skip_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self._skip_checkbox)

        self._auto_fill_checkbox = QCheckBox("Auto-fill slots from filename")
        self._auto_fill_checkbox.setStyleSheet(CHECKBOX_STYLE_WHITE_LABEL)
        self._auto_fill_checkbox.setChecked(auto_fill_slots)
        self._auto_fill_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self._auto_fill_checkbox.setToolTip(
            "Map split filename parts to enabled slots in order."
        )
        layout.addWidget(self._auto_fill_checkbox)

        self._format_widget = FormatConfigWidget()
        self._format_widget.set_format(self._fmt)
        self._format_widget.format_changed.connect(self._on_format_changed)
        layout.addWidget(self._format_widget)

        self._status_label = QLabel()
        self._status_label.setStyleSheet("color: #aaa; font-size: 12px;")
        layout.addWidget(self._status_label)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_SECONDARY_BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)
        self._start_btn = QPushButton("Start")
        self._start_btn.setStyleSheet(_BUTTON_STYLE)
        self._start_btn.clicked.connect(self._start)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(self._start_btn)
        layout.addLayout(button_row)

        if initial_folder is not None:
            self._set_folder(initial_folder)

    def format(self) -> FilenameFormat:
        return self._format_widget.format()

    def video_types(self) -> list[VideoTypeProfile]:
        self._persist_active_profile()
        return [profile.copy() for profile in self._video_types]

    def active_video_type_id(self) -> str:
        return self._type_selector.active_id()

    def skip_tagged(self) -> bool:
        return self._skip_checkbox.isChecked()

    def auto_fill_slots(self) -> bool:
        return self._auto_fill_checkbox.isChecked()

    def _active_profile(self) -> VideoTypeProfile:
        active_id = self._type_selector.active_id()
        profile = find_video_type(self._video_types, active_id)
        if profile is None:
            return self._video_types[0]
        return profile

    def _metadata_mapping(self):
        return self._active_profile().resolved_metadata_mapping()

    def _on_format_changed(self, fmt: FilenameFormat) -> None:
        self._fmt = fmt.copy()
        self._persist_active_profile()

    def _persist_active_profile(self) -> None:
        active_id = self._type_selector.active_id()
        for profile in self._video_types:
            if profile.id == active_id:
                profile.rename_format = self._fmt.copy()
                mapping = profile.resolved_metadata_mapping().normalize_for_format(
                    self._fmt
                )
                profile.metadata_field_mapping = mapping
                profile.metadata_comment_slot_indices = (
                    list(mapping.description_slots) or None
                )
                return

    def _on_video_type_changed(self, profile: VideoTypeProfile) -> None:
        self._persist_active_profile()
        self._active_video_type_id = profile.id
        self._fmt = profile.rename_format.copy()
        self._format_widget.set_format(self._fmt)

    def _on_video_types_changed(self, profiles: list[VideoTypeProfile]) -> None:
        self._persist_active_profile()
        self._video_types = [profile.copy() for profile in profiles]
        self._active_video_type_id = self._type_selector.active_id()

    def _current_folder(self) -> Path | None:
        text = self._folder_field.text().strip()
        if not text:
            return None
        try:
            return Path(text).resolve()
        except OSError:
            return None

    def _set_folder(self, folder: Path) -> None:
        self._folder = folder
        self._folder_field.setText(str(folder))

    def _show_folder_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)
        current = self._current_folder()
        pinned_resolved = {path.resolve() for path in self._pinned_folders}
        pinned_label = self._pinned_folder_label or PINNED_LABEL

        for folder in self._pinned_folders:
            action = QAction(pinned_label, self)
            action.setToolTip(str(folder))
            resolved = folder.resolve()
            if current == resolved:
                action.setCheckable(True)
                action.setChecked(True)
                action.setEnabled(False)
            else:
                action.triggered.connect(
                    lambda _checked=False, selected=folder: self._set_folder(selected)
                )
            menu.addAction(action)

        recent = [
            folder
            for folder in self._recent_folders
            if folder.resolve() not in pinned_resolved
        ]
        if recent and self._pinned_folders:
            menu.addSeparator()

        for folder in recent:
            action = QAction(folder.name, self)
            action.setToolTip(str(folder))
            resolved = folder.resolve()
            if current == resolved:
                action.setCheckable(True)
                action.setChecked(True)
                action.setEnabled(False)
            else:
                action.triggered.connect(
                    lambda _checked=False, selected=folder: self._set_folder(selected)
                )
            menu.addAction(action)

        if self._pinned_folders or recent:
            menu.addSeparator()

        browse = QAction("Browse…", self)
        browse.triggered.connect(self._browse_folder)
        menu.addAction(browse)

        menu.exec(
            self._folder_btn.mapToGlobal(self._folder_btn.rect().bottomLeft())
        )

    def _browse_folder(self) -> None:
        start_dir = self._folder_field.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", start_dir)
        if folder:
            self._set_folder(Path(folder))

    def _start(self) -> None:
        folder_text = self._folder_field.text().strip()
        if not folder_text:
            QMessageBox.warning(self, "No Folder", "Select a folder to tag files in.")
            return

        folder = Path(folder_text)
        if not folder.is_dir():
            QMessageBox.warning(self, "Invalid Folder", f"Not a directory:\n{folder}")
            return

        self._folder = folder
        self._fmt = self._format_widget.format()
        self._skip_tagged = self._skip_checkbox.isChecked()
        self._auto_fill_slots = self._auto_fill_checkbox.isChecked()
        self._persist_active_profile()
        self._run_batch()

    def _run_batch(self) -> None:
        assert self._folder is not None
        files = sorted(scan_videos(self._folder), key=lambda path: path.name.lower())

        unsupported = [path for path in files if not supports_metadata(path)]
        files = [path for path in files if supports_metadata(path)]
        self._unsupported_count = len(unsupported)

        if self._skip_tagged:
            tagged = [path for path in files if has_title_and_artist(path)]
            self._skipped_count += len(tagged)
            files = [path for path in files if not has_title_and_artist(path)]

        if not files:
            message = "No supported media files found to tag in the selected folder."
            if self._unsupported_count:
                message += f"\n\nSkipped {self._unsupported_count} unsupported file(s)."
            QMessageBox.information(self, "No Files", message)
            return

        total = len(files)
        self.hide()

        for index, path in enumerate(files, start=1):
            progress = f"File {index} of {total}"
            dialog = MetadataFileDialog(
                path,
                fmt=self._fmt,
                metadata_field_mapping=self._metadata_mapping(),
                progress_label=progress,
                auto_fill_slots=self._auto_fill_slots,
                parent=self.parentWidget(),
            )
            code = dialog.exec()
            self._fmt = dialog.format()

            if code == QDialog.DialogCode.Rejected:
                break

            result = dialog.result_value()
            if result == MetadataResult.SKIPPED:
                self._skipped_count += 1
                continue
            if result == MetadataResult.APPLIED:
                self._applied_count += 1
            else:
                self._failed_count += 1

        summary_parts = [
            f"Applied metadata to {self._applied_count} file(s).",
            f"Skipped {self._skipped_count}.",
        ]
        if self._unsupported_count:
            summary_parts.append(f"Unsupported format: {self._unsupported_count}.")
        if self._failed_count:
            summary_parts.append(f"Failed: {self._failed_count}.")

        QMessageBox.information(
            self,
            "Tag Metadata Complete",
            "\n".join(summary_parts),
        )
        self.accept()
