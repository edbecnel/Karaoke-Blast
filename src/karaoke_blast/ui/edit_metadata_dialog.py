"""Dialog to edit Title, Artist, Description, and Album tags on a single media file."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.ui.dialog_positioning import fit_dialog_to_anchor, schedule_fit_dialog_to_anchor
from karaoke_blast.ui.visible_space_field import VisibleSpaceLineEdit
from karaoke_blast.utils.display import display_name
from karaoke_blast.utils.filename_rename import DEFAULT_KARAOKE_FORMAT, FilenameFormat
from karaoke_blast.utils.media_metadata import (
    MetadataError,
    read_tags,
    supports_metadata,
    write_tags,
)
from karaoke_blast.utils.metadata_field_mapping import (
    MetadataFieldMapping,
    VLC_FIELD_ALBUM,
    VLC_FIELD_ARTIST,
    VLC_FIELD_DESCRIPTION,
    VLC_FIELD_GENRE,
    VLC_FIELD_TITLE,
    default_metadata_mapping,
    metadata_field_display_labels,
)

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
QLineEdit:focus {
    border-color: #e94560;
}
"""

_LABEL_STYLE = "color: #ccc; font-size: 12px; background: transparent;"
_FILE_STYLE = "color: white; font-size: 13px; background: transparent;"
_HINT_STYLE = "color: #888; font-size: 11px; background: transparent;"
_STATUS_STYLE = "color: #ff6b81; font-size: 12px; background: transparent;"
_FIELD_MIN_WIDTH = 420

_BUTTON_STYLE = """
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
QPushButton:disabled {
    color: #666;
    border-color: #3a3a52;
}
"""

_PRIMARY_BUTTON_STYLE = """
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


class EditMetadataDialog(QDialog):
    """Edit embedded Title, Artist, Description, and Album for one file."""

    def __init__(
        self,
        path: Path,
        *,
        fmt: FilenameFormat | None = None,
        metadata_field_mapping: MetadataFieldMapping | None = None,
        comment_slot_indices: list[int] | None = None,
        parent: QWidget | None = None,
        anchor: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._position_anchor = anchor
        self._fmt = (fmt if fmt is not None else DEFAULT_KARAOKE_FORMAT).copy()
        if metadata_field_mapping is not None:
            self._mapping = metadata_field_mapping.copy().normalize_for_format(self._fmt)
        else:
            self._mapping = default_metadata_mapping(
                self._fmt,
                legacy_comment_slot_indices=comment_slot_indices,
            )
        labels = metadata_field_display_labels(self._fmt, self._mapping)
        self._title_label_text = labels[VLC_FIELD_TITLE]
        self._artist_label_text = labels[VLC_FIELD_ARTIST]
        self._description_label_text = labels[VLC_FIELD_DESCRIPTION]
        self._genre_label_text = labels[VLC_FIELD_GENRE]
        self._album_label_text = labels[VLC_FIELD_ALBUM]
        self.setWindowTitle("Edit Metadata")
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumWidth(640)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        file_label = QLabel(display_name(path))
        file_label.setStyleSheet(_FILE_STYLE)
        file_label.setWordWrap(True)
        layout.addWidget(file_label)

        path_hint = QLabel(str(path))
        path_hint.setStyleSheet(_HINT_STYLE)
        path_hint.setWordWrap(True)
        layout.addWidget(path_hint)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        self._title_field = self._make_field()
        self._title_field.setPlaceholderText(self._title_label_text)
        title_label = QLabel(self._title_label_text)
        title_label.setStyleSheet(_LABEL_STYLE)
        form.addRow(title_label, self._title_field)

        self._artist_field = self._make_field()
        self._artist_field.setPlaceholderText(self._artist_label_text)
        artist_label = QLabel(self._artist_label_text)
        artist_label.setStyleSheet(_LABEL_STYLE)
        form.addRow(artist_label, self._artist_field)

        self._genre_field = self._make_field()
        self._genre_field.setPlaceholderText(self._genre_label_text)
        self._genre_label = QLabel(self._genre_label_text)
        self._genre_label.setStyleSheet(_LABEL_STYLE)
        form.addRow(self._genre_label, self._genre_field)

        self._description_field = self._make_field()
        self._description_field.setPlaceholderText(self._description_label_text)
        description_label = QLabel(self._description_label_text)
        description_label.setStyleSheet(_LABEL_STYLE)
        form.addRow(description_label, self._description_field)

        self._album_field = self._make_field()
        self._album_field.setPlaceholderText(self._album_label_text)
        self._album_label = QLabel(self._album_label_text)
        self._album_label.setStyleSheet(_LABEL_STYLE)
        form.addRow(self._album_label, self._album_field)

        layout.addLayout(form)

        if self._mapping.genre_slot is None:
            self._genre_label.hide()
            self._genre_field.hide()

        self._status = QLabel()
        self._status.setStyleSheet(_STATUS_STYLE)
        self._status.setWordWrap(True)
        self._status.hide()
        layout.addWidget(self._status)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_btn is not None:
            save_btn.setStyleSheet(_PRIMARY_BUTTON_STYLE)
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._save_btn = save_btn
        else:
            self._save_btn = None
        if cancel_btn is not None:
            cancel_btn.setStyleSheet(_BUTTON_STYLE)
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(buttons)

        self._load_tags()

    def showEvent(self, event: QShowEvent) -> None:
        if getattr(self, "_present_on_side_panel", False):
            if self._position_anchor is not None:
                fit_dialog_to_anchor(self, self._position_anchor)
            super().showEvent(event)
            if self._position_anchor is not None:
                fit_dialog_to_anchor(self, self._position_anchor)
                schedule_fit_dialog_to_anchor(self, self._position_anchor)
            return
        super().showEvent(event)
        if self._position_anchor is not None:
            fit_dialog_to_anchor(self, self._position_anchor)
            schedule_fit_dialog_to_anchor(self, self._position_anchor)

    def _make_field(self) -> VisibleSpaceLineEdit:
        field = VisibleSpaceLineEdit()
        field.setStyleSheet(_FIELD_STYLE)
        field.setMinimumWidth(_FIELD_MIN_WIDTH)
        field.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        return field

    def _load_tags(self) -> None:
        if not supports_metadata(self._path):
            suffix = self._path.suffix or "(no extension)"
            self._status.setText(
                f"This file type ({suffix}) does not support embedded metadata."
            )
            self._status.show()
            self._title_field.setEnabled(False)
            self._artist_field.setEnabled(False)
            self._description_field.setEnabled(False)
            self._genre_field.setEnabled(False)
            self._album_field.setEnabled(False)
            if self._save_btn is not None:
                self._save_btn.setEnabled(False)
            return
        try:
            tags = read_tags(self._path)
        except MetadataError as exc:
            self._status.setText(str(exc))
            self._status.show()
            tags = None
        if tags is None:
            return
        self._title_field.setText(tags.title)
        self._artist_field.setText(tags.artist)
        self._description_field.setText(tags.comment)
        self._genre_field.setText(tags.genre)
        self._album_field.setText(tags.album)

    def _on_save(self) -> None:
        title = self._title_field.text().strip()
        if not title:
            self._status.setText(f"{self._title_label_text} cannot be empty.")
            self._status.show()
            self._title_field.setFocus()
            return
        try:
            write_tags(
                self._path,
                title=title,
                artist=self._artist_field.text().strip(),
                description=self._description_field.text().strip(),
                genre=(
                    self._genre_field.text().strip()
                    if self._mapping.genre_slot is not None
                    else None
                ),
                album=self._album_field.text().strip(),
            )
        except MetadataError as exc:
            QMessageBox.warning(self, "Could not save metadata", str(exc))
            return
        self.accept()
