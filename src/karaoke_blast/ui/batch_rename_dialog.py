"""Batch rename wizard for a folder of video files."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.ui.checkbox_style import CHECKBOX_STYLE_WHITE_LABEL
from karaoke_blast.ui.format_config_widget import FormatConfigWidget
from karaoke_blast.ui.video_type_selector import VideoTypeSelectorWidget
from karaoke_blast.ui.visible_space_field import VisibleSpaceLineEdit
from karaoke_blast.ui.rename_file_dialog import RenameFileDialog, RenameResult
from karaoke_blast.utils.filename_rename import FilenameFormat, looks_canonical
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


class BatchRenameDialog(QDialog):
    """Pick a folder and rename video files one at a time."""

    file_renamed = pyqtSignal(object, object)

    def __init__(
        self,
        *,
        initial_folder: Path | None = None,
        video_types: list[VideoTypeProfile],
        active_video_type_id: str,
        skip_canonical: bool = True,
        auto_fill_slots: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._video_types = [profile.copy() for profile in video_types]
        self._active_video_type_id = active_video_type_id
        active_profile = find_video_type(self._video_types, active_video_type_id)
        self._fmt = (
            active_profile.rename_format.copy()
            if active_profile is not None
            else self._video_types[0].rename_format.copy()
        )
        self._skip_canonical = skip_canonical
        self._auto_fill_slots = auto_fill_slots
        self._folder = initial_folder
        self._renamed_count = 0
        self._skipped_count = 0

        self.setWindowTitle("Batch Rename")
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
        browse_btn = QPushButton("Browse…")
        browse_btn.setStyleSheet(_SECONDARY_BUTTON_STYLE)
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(folder_label)
        folder_row.addWidget(self._folder_field, 1)
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)

        self._skip_checkbox = QCheckBox("Skip files that already match the format")
        self._skip_checkbox.setStyleSheet(CHECKBOX_STYLE_WHITE_LABEL)
        self._skip_checkbox.setChecked(skip_canonical)
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
            self._folder_field.setText(str(initial_folder))

    def format(self) -> FilenameFormat:
        return self._format_widget.format()

    def video_types(self) -> list[VideoTypeProfile]:
        self._persist_active_profile_format()
        return [profile.copy() for profile in self._video_types]

    def active_video_type_id(self) -> str:
        return self._type_selector.active_id()

    def skip_canonical(self) -> bool:
        return self._skip_checkbox.isChecked()

    def auto_fill_slots(self) -> bool:
        return self._auto_fill_checkbox.isChecked()

    def _on_format_changed(self, fmt: FilenameFormat) -> None:
        self._fmt = fmt.copy()
        self._persist_active_profile_format()

    def _persist_active_profile_format(self) -> None:
        active_id = self._type_selector.active_id()
        for profile in self._video_types:
            if profile.id == active_id:
                profile.rename_format = self._fmt.copy()
                return

    def _on_video_type_changed(self, profile: VideoTypeProfile) -> None:
        self._persist_active_profile_format()
        self._active_video_type_id = profile.id
        self._fmt = profile.rename_format.copy()
        self._format_widget.set_format(self._fmt)

    def _on_video_types_changed(self, profiles: list[VideoTypeProfile]) -> None:
        self._persist_active_profile_format()
        self._video_types = [profile.copy() for profile in profiles]
        self._active_video_type_id = self._type_selector.active_id()

    def _browse_folder(self) -> None:
        start_dir = self._folder_field.text() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", start_dir)
        if folder:
            self._folder_field.setText(folder)

    def _start(self) -> None:
        folder_text = self._folder_field.text().strip()
        if not folder_text:
            QMessageBox.warning(self, "No Folder", "Select a folder to rename files in.")
            return

        folder = Path(folder_text)
        if not folder.is_dir():
            QMessageBox.warning(self, "Invalid Folder", f"Not a directory:\n{folder}")
            return

        self._folder = folder
        self._fmt = self._format_widget.format()
        self._skip_canonical = self._skip_checkbox.isChecked()
        self._auto_fill_slots = self._auto_fill_checkbox.isChecked()
        self._run_batch()

    def _run_batch(self) -> None:
        assert self._folder is not None
        files = sorted(scan_videos(self._folder), key=lambda path: path.name.lower())
        if self._skip_canonical:
            files = [path for path in files if not looks_canonical(path, self._fmt)]

        if not files:
            QMessageBox.information(
                self,
                "No Files",
                "No video files found to rename in the selected folder.",
            )
            return

        total = len(files)
        self.hide()

        for index, path in enumerate(files, start=1):
            progress = f"File {index} of {total}"
            dialog = RenameFileDialog(
                path,
                fmt=self._fmt,
                progress_label=progress,
                show_format_config=False,
                auto_fill_slots=self._auto_fill_slots,
                parent=self.parentWidget(),
            )
            code = dialog.exec()
            self._fmt = dialog.format()

            if code == QDialog.DialogCode.Rejected:
                break

            result = dialog.result_value()
            if result == RenameResult.SKIPPED:
                self._skipped_count += 1
                continue
            if result == RenameResult.RENAMED:
                new_path = dialog.new_path()
                if new_path is not None:
                    self._renamed_count += 1
                    self.file_renamed.emit(path, new_path)

        QMessageBox.information(
            self,
            "Batch Rename Complete",
            f"Renamed {self._renamed_count} file(s), skipped {self._skipped_count}.",
        )
        self.accept()
