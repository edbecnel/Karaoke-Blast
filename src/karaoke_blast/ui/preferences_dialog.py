"""Global application preferences dialog."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.services.youtube_cookies import cookies_folder, youtube_cookies_setup_page
from karaoke_blast.storage.paths import (
    default_rumble_cookies_file,
    default_youtube_cookies_file,
)

from karaoke_blast.ui.checkbox_style import CHECKBOX_STYLE_WHITE_LABEL

_DIALOG_STYLE = """
QDialog {
    background-color: #1e1e2e;
}
"""

_SECTION_LABEL_STYLE = "color: white; font-size: 12px; font-weight: 600; background: transparent;"


@dataclass(frozen=True)
class PreferencesValues:
    hide_appledouble_files: bool
    library_flat_browse: bool
    controls_auto_hide: bool
    filename_rename_skip_canonical: bool
    filename_rename_auto_fill_slots: bool
    metadata_skip_tagged: bool
    metadata_auto_fill_slots: bool


def build_preferences_values(
    *,
    hide_appledouble_files: bool,
    library_flat_browse: bool,
    controls_auto_hide: bool,
    filename_rename_skip_canonical: bool,
    filename_rename_auto_fill_slots: bool,
    metadata_skip_tagged: bool,
    metadata_auto_fill_slots: bool,
) -> PreferencesValues:
    return PreferencesValues(
        hide_appledouble_files=hide_appledouble_files,
        library_flat_browse=library_flat_browse,
        controls_auto_hide=controls_auto_hide,
        filename_rename_skip_canonical=filename_rename_skip_canonical,
        filename_rename_auto_fill_slots=filename_rename_auto_fill_slots,
        metadata_skip_tagged=metadata_skip_tagged,
        metadata_auto_fill_slots=metadata_auto_fill_slots,
    )


class PreferencesDialog(QDialog):
    """Edit global preferences stored in settings.json."""

    def __init__(
        self,
        *,
        hide_appledouble_files: bool,
        library_flat_browse: bool,
        controls_auto_hide: bool,
        filename_rename_skip_canonical: bool,
        filename_rename_auto_fill_slots: bool,
        metadata_skip_tagged: bool,
        metadata_auto_fill_slots: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(self._section_label("Library"))

        self._hide_appledouble_checkbox = QCheckBox(
            "Hide macOS metadata files (._)"
        )
        self._hide_appledouble_checkbox.setStyleSheet(CHECKBOX_STYLE_WHITE_LABEL)
        self._hide_appledouble_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hide_appledouble_checkbox.setToolTip(
            "Hide AppleDouble sidecar files created on external drives. "
            "These are not playable videos."
        )
        self._hide_appledouble_checkbox.setChecked(hide_appledouble_files)
        layout.addWidget(self._hide_appledouble_checkbox)

        self._library_flat_browse_checkbox = QCheckBox(
            "Include subfolders in library list"
        )
        self._library_flat_browse_checkbox.setStyleSheet(CHECKBOX_STYLE_WHITE_LABEL)
        self._library_flat_browse_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self._library_flat_browse_checkbox.setToolTip(
            "Show all media files in subfolders as a flat list."
        )
        self._library_flat_browse_checkbox.setChecked(library_flat_browse)
        layout.addWidget(self._library_flat_browse_checkbox)

        layout.addWidget(self._section_label("Playback"))

        self._controls_auto_hide_checkbox = QCheckBox("Auto-hide playback controls")
        self._controls_auto_hide_checkbox.setStyleSheet(CHECKBOX_STYLE_WHITE_LABEL)
        self._controls_auto_hide_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self._controls_auto_hide_checkbox.setChecked(controls_auto_hide)
        layout.addWidget(self._controls_auto_hide_checkbox)

        layout.addWidget(self._section_label("YouTube"))

        youtube_cookies_path = default_youtube_cookies_file()
        youtube_cookies_help = QLabel(
            "For YouTube downloads that fail with HTTP 403, export a Netscape cookies.txt "
            "from youtube.com while signed in and save it as:"
        )
        youtube_cookies_help.setWordWrap(True)
        youtube_cookies_help.setStyleSheet(
            "color: #ccc; font-size: 12px; background: transparent;"
        )
        layout.addWidget(youtube_cookies_help)

        youtube_cookies_path_label = QLabel(str(youtube_cookies_path))
        youtube_cookies_path_label.setWordWrap(True)
        youtube_cookies_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        youtube_cookies_path_label.setStyleSheet(
            "color: #aaa; font-size: 11px; font-family: monospace; background: transparent;"
        )
        layout.addWidget(youtube_cookies_path_label)

        layout.addWidget(self._section_label("Rumble"))

        rumble_cookies_path = default_rumble_cookies_file()
        rumble_cookies_help = QLabel(
            "For Rumble playback and metadata, export cookies from rumble.com while signed in "
            "and save as:"
        )
        rumble_cookies_help.setWordWrap(True)
        rumble_cookies_help.setStyleSheet(
            "color: #ccc; font-size: 12px; background: transparent;"
        )
        layout.addWidget(rumble_cookies_help)

        rumble_cookies_path_label = QLabel(str(rumble_cookies_path))
        rumble_cookies_path_label.setWordWrap(True)
        rumble_cookies_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        rumble_cookies_path_label.setStyleSheet(
            "color: #aaa; font-size: 11px; font-family: monospace; background: transparent;"
        )
        layout.addWidget(rumble_cookies_path_label)

        cookies_buttons = QHBoxLayout()
        open_folder_btn = QPushButton("Open folder…")
        open_folder_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(cookies_folder())))
        )
        cookies_buttons.addWidget(open_folder_btn)

        setup_page = youtube_cookies_setup_page()
        setup_btn = QPushButton("Cookies setup (bookmarklet)…")
        setup_btn.setEnabled(setup_page.is_file())
        if setup_page.is_file():
            setup_btn.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(setup_page)))
            )
        cookies_buttons.addWidget(setup_btn)
        cookies_buttons.addStretch()
        layout.addLayout(cookies_buttons)

        layout.addWidget(self._section_label("Batch tools"))

        self._rename_skip_canonical_checkbox = QCheckBox(
            "Skip files that already match the rename format"
        )
        self._rename_skip_canonical_checkbox.setStyleSheet(CHECKBOX_STYLE_WHITE_LABEL)
        self._rename_skip_canonical_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rename_skip_canonical_checkbox.setChecked(filename_rename_skip_canonical)
        layout.addWidget(self._rename_skip_canonical_checkbox)

        self._rename_auto_fill_checkbox = QCheckBox(
            "Auto-fill rename slots from filename"
        )
        self._rename_auto_fill_checkbox.setStyleSheet(CHECKBOX_STYLE_WHITE_LABEL)
        self._rename_auto_fill_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rename_auto_fill_checkbox.setChecked(filename_rename_auto_fill_slots)
        layout.addWidget(self._rename_auto_fill_checkbox)

        self._metadata_skip_tagged_checkbox = QCheckBox(
            "Skip files that already have Title and Artist"
        )
        self._metadata_skip_tagged_checkbox.setStyleSheet(CHECKBOX_STYLE_WHITE_LABEL)
        self._metadata_skip_tagged_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self._metadata_skip_tagged_checkbox.setChecked(metadata_skip_tagged)
        layout.addWidget(self._metadata_skip_tagged_checkbox)

        self._metadata_auto_fill_checkbox = QCheckBox(
            "Auto-fill metadata slots from filename"
        )
        self._metadata_auto_fill_checkbox.setStyleSheet(CHECKBOX_STYLE_WHITE_LABEL)
        self._metadata_auto_fill_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self._metadata_auto_fill_checkbox.setChecked(metadata_auto_fill_slots)
        layout.addWidget(self._metadata_auto_fill_checkbox)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(_SECTION_LABEL_STYLE)
        return label

    def values(self) -> PreferencesValues:
        return build_preferences_values(
            hide_appledouble_files=self._hide_appledouble_checkbox.isChecked(),
            library_flat_browse=self._library_flat_browse_checkbox.isChecked(),
            controls_auto_hide=self._controls_auto_hide_checkbox.isChecked(),
            filename_rename_skip_canonical=self._rename_skip_canonical_checkbox.isChecked(),
            filename_rename_auto_fill_slots=self._rename_auto_fill_checkbox.isChecked(),
            metadata_skip_tagged=self._metadata_skip_tagged_checkbox.isChecked(),
            metadata_auto_fill_slots=self._metadata_auto_fill_checkbox.isChecked(),
        )
