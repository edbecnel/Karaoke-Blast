"""Dialog to edit Title, Artist, and Comment tags on a single media file."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.ui.visible_space_field import VisibleSpaceLineEdit
from karaoke_blast.utils.display import display_name
from karaoke_blast.utils.media_metadata import (
    MetadataError,
    read_tags,
    supports_metadata,
    write_tags,
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
    """Edit embedded Title, Artist, and Comments for one file."""

    def __init__(self, path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path = path
        self.setWindowTitle("Edit Metadata")
        self.setModal(True)
        self.setMinimumWidth(440)
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

        self._title_field = VisibleSpaceLineEdit()
        self._title_field.setStyleSheet(_FIELD_STYLE)
        self._title_field.setPlaceholderText("Song title (required)")
        title_label = QLabel("Song Title")
        title_label.setStyleSheet(_LABEL_STYLE)
        form.addRow(title_label, self._title_field)

        self._artist_field = VisibleSpaceLineEdit()
        self._artist_field.setStyleSheet(_FIELD_STYLE)
        self._artist_field.setPlaceholderText("Artist name")
        artist_label = QLabel("Artist Name")
        artist_label.setStyleSheet(_LABEL_STYLE)
        form.addRow(artist_label, self._artist_field)

        self._comment_field = VisibleSpaceLineEdit()
        self._comment_field.setStyleSheet(_FIELD_STYLE)
        self._comment_field.setPlaceholderText("Comments")
        comment_label = QLabel("Comments")
        comment_label.setStyleSheet(_LABEL_STYLE)
        form.addRow(comment_label, self._comment_field)

        layout.addLayout(form)

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

    def _load_tags(self) -> None:
        if not supports_metadata(self._path):
            suffix = self._path.suffix or "(no extension)"
            self._status.setText(
                f"This file type ({suffix}) does not support embedded metadata."
            )
            self._status.show()
            self._title_field.setEnabled(False)
            self._artist_field.setEnabled(False)
            self._comment_field.setEnabled(False)
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
        self._comment_field.setText(tags.comment)

    def _on_save(self) -> None:
        title = self._title_field.text().strip()
        if not title:
            self._status.setText("Song Title cannot be empty.")
            self._status.show()
            self._title_field.setFocus()
            return
        try:
            write_tags(
                self._path,
                title=title,
                artist=self._artist_field.text().strip(),
                comment=self._comment_field.text().strip(),
            )
        except MetadataError as exc:
            QMessageBox.warning(self, "Could not save metadata", str(exc))
            return
        self.accept()
