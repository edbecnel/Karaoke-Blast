"""Dialog for creating or editing a video type."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.ui.format_config_widget import FormatConfigWidget
from karaoke_blast.ui.visible_space_field import VisibleSpaceLineEdit
from karaoke_blast.utils.video_types import (
    VideoTypeProfile,
    create_custom_video_type,
    default_custom_format,
    reset_builtin_video_type,
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
QLineEdit:disabled {
    color: #888;
    background-color: #252536;
}
"""

_HINT_STYLE = "color: #888; font-size: 11px; background: transparent;"
_ERROR_STYLE = "color: #ff6b81; font-size: 12px; background: transparent;"

_BUTTON_STYLE = """
QPushButton {
    background-color: #2d2d42;
    color: white;
    border: 1px solid #5a5a72;
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #3a3a52;
    border-color: #7a7a92;
}
"""


class VideoTypeEditorDialog(QDialog):
    """Create or edit a video type name and rename format."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        profile: VideoTypeProfile | None = None,
    ) -> None:
        super().__init__(parent)
        self._source = profile.copy() if profile is not None else None
        self._result_profile: VideoTypeProfile | None = None
        is_edit = profile is not None

        self.setWindowTitle("Edit Video Type" if is_edit else "Add Video Type")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hint = QLabel(
            "Configure slot labels, separators, and casing."
            if is_edit
            else "Choose a name and configure the filename slots for this type."
        )
        if is_edit and profile is not None and profile.builtin:
            hint.setText(
                "Built-in type names are read-only. "
                "Slot labels, separators, and casing can be edited."
            )
        hint.setWordWrap(True)
        hint.setStyleSheet(_HINT_STYLE)
        layout.addWidget(hint)

        name_row = QVBoxLayout()
        name_row.setSpacing(4)
        name_label = QLabel("Type name")
        name_label.setStyleSheet("color: #ccc; font-size: 12px;")
        name_row.addWidget(name_label)
        self._name_field = VisibleSpaceLineEdit()
        self._name_field.setStyleSheet(_FIELD_STYLE)
        self._name_field.setPlaceholderText("e.g. Documentaries")
        if profile is not None:
            self._name_field.setText(profile.name)
        name_row.addWidget(self._name_field)
        if profile is not None and profile.builtin:
            self._name_field.setReadOnly(True)
            builtin_hint = QLabel("Read-only for built-in types.")
            builtin_hint.setStyleSheet(_HINT_STYLE)
            name_row.addWidget(builtin_hint)
        layout.addLayout(name_row)

        self._format_widget = FormatConfigWidget()
        initial_format = (
            profile.rename_format.copy()
            if profile is not None
            else default_custom_format()
        )
        self._format_widget.set_format(initial_format)
        layout.addWidget(self._format_widget)

        if profile is not None and profile.builtin:
            reset_row = QVBoxLayout()
            reset_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
            reset_btn = QPushButton("Reset to factory default")
            reset_btn.setStyleSheet(_BUTTON_STYLE)
            reset_btn.clicked.connect(self._reset_builtin)
            reset_row.addWidget(reset_btn)
            layout.addLayout(reset_row)

        self._error_label = QLabel()
        self._error_label.setStyleSheet(_ERROR_STYLE)
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def profile(self) -> VideoTypeProfile | None:
        return self._result_profile.copy() if self._result_profile is not None else None

    def _reset_builtin(self) -> None:
        if self._source is None or not self._source.builtin:
            return
        confirm = QMessageBox.question(
            self,
            "Reset Video Type",
            f"Reset \"{self._source.name}\" to its factory default?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        restored = reset_builtin_video_type(self._source)
        self._format_widget.set_format(restored.rename_format.copy())

    def _accept(self) -> None:
        name = self._name_field.text().strip()
        if not name:
            self._error_label.setText("Enter a type name.")
            self._error_label.show()
            return

        rename_format = self._format_widget.format()
        primary_index = rename_format.song_slot_index()
        if primary_index is not None:
            primary_label = rename_format.slots[primary_index].label.strip()
            if not primary_label:
                self._error_label.setText("Enter a label for the primary slot.")
                self._error_label.show()
                return

        self._error_label.hide()

        if self._source is None:
            self._result_profile = create_custom_video_type(
                name,
                rename_format=rename_format,
            )
        else:
            updated = self._source.copy()
            if not updated.builtin:
                updated.name = name
            updated.rename_format = rename_format
            self._result_profile = updated
        self.accept()
