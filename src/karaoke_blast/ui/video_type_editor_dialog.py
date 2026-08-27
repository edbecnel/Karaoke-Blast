"""Dialog for creating or editing a media type."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.ui.format_config_widget import FormatConfigWidget
from karaoke_blast.ui.library_folder_picker_row import LibraryFolderPickerRow
from karaoke_blast.ui.metadata_mapping_widget import MetadataMappingWidget
from karaoke_blast.ui.visible_space_field import VisibleSpaceLineEdit
from karaoke_blast.utils.filename_rename import FilenameFormat
from karaoke_blast.utils.metadata_field_mapping import default_metadata_mapping
from karaoke_blast.utils.video_types import (
    MediaCategory,
    VideoTypeProfile,
    create_custom_video_type,
    default_custom_format,
    default_media_category,
    default_youtube_search_append,
    media_category_label,
    reset_builtin_video_type,
    shows_youtube_append_dropdown,
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

_CATEGORY_COMBO_STYLE = """
QComboBox {
    background-color: #2d2d42;
    color: #ffffff;
    border: 1px solid #5a5a72;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
}
QComboBox:focus {
    border-color: #e94560;
}
QComboBox:disabled {
    color: #888;
    background-color: #252536;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #ffffff;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    color: #ffffff;
    border: 1px solid #5a5a72;
    selection-background-color: #e94560;
    selection-color: #ffffff;
    outline: none;
}
"""


class VideoTypeEditorDialog(QDialog):
    """Create or edit a media type name, rename format, and metadata mapping."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        profile: VideoTypeProfile | None = None,
        recent_folders: list[Path] | None = None,
        pinned_folders: list[Path] | None = None,
        pinned_folder_label: str | None = None,
        on_folder_browsed: Callable[[Path], None] | None = None,
        initial_library_folder: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._source = profile.copy() if profile is not None else None
        self._result_profile: VideoTypeProfile | None = None
        is_edit = profile is not None

        self.setWindowTitle("Edit Media Type" if is_edit else "Add Media Type")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hint = QLabel(
            "Configure slot labels, separators, casing, and VLC metadata mapping."
            if is_edit
            else "Choose a name and configure the filename slots for this type."
        )
        if is_edit and profile is not None and profile.builtin:
            hint.setText(
                "Built-in type names are read-only. "
                "Slot labels, separators, casing, and metadata mapping can be edited."
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

        category_row = QVBoxLayout()
        category_row.setSpacing(4)
        category_label = QLabel("Media category")
        category_label.setStyleSheet("color: #ccc; font-size: 12px;")
        category_row.addWidget(category_label)
        self._category_combo = QComboBox()
        self._category_combo.setStyleSheet(_CATEGORY_COMBO_STYLE)
        for category in MediaCategory:
            self._category_combo.addItem(
                media_category_label(category),
                category.value,
            )
        if profile is not None:
            index = self._category_combo.findData(profile.media_category.value)
            if index >= 0:
                self._category_combo.setCurrentIndex(index)
        elif profile is None:
            none_index = self._category_combo.findData(MediaCategory.NONE.value)
            if none_index >= 0:
                self._category_combo.setCurrentIndex(none_index)
        if profile is not None and profile.builtin:
            self._category_combo.setEnabled(False)
            category_hint = QLabel("Read-only for built-in types.")
            category_hint.setStyleSheet(_HINT_STYLE)
            category_row.addWidget(category_hint)
        category_row.addWidget(self._category_combo)
        layout.addLayout(category_row)

        folder_row = QVBoxLayout()
        folder_row.setSpacing(4)
        folder_label = QLabel("Library folder")
        folder_label.setStyleSheet("color: #ccc; font-size: 12px;")
        folder_row.addWidget(folder_label)
        if profile is not None and profile.last_library_folder:
            initial_folder = Path(profile.last_library_folder)
        elif initial_library_folder is not None:
            initial_folder = initial_library_folder
        else:
            initial_folder = None
        self._folder_picker = LibraryFolderPickerRow(
            recent_folders=recent_folders,
            pinned_folders=pinned_folders,
            pinned_folder_label=pinned_folder_label,
            on_folder_browsed=on_folder_browsed,
            initial_folder=initial_folder,
        )
        folder_row.addWidget(self._folder_picker)
        layout.addLayout(folder_row)

        self._format_widget = FormatConfigWidget()
        initial_format = (
            profile.rename_format.copy()
            if profile is not None
            else default_custom_format()
        )
        self._format_widget.set_format(initial_format)
        self._format_widget.format_changed.connect(self._on_format_changed)
        layout.addWidget(self._format_widget)

        self._mapping_widget = MetadataMappingWidget()
        initial_mapping = (
            profile.resolved_metadata_mapping()
            if profile is not None
            else default_metadata_mapping(initial_format)
        )
        self._mapping_widget.set_format_and_mapping(initial_format, initial_mapping)
        layout.addWidget(self._mapping_widget)

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

    def _on_format_changed(self, fmt: FilenameFormat) -> None:
        self._mapping_widget.set_format_and_mapping(
            fmt,
            self._mapping_widget.mapping().normalize_for_format(fmt),
        )

    def _reset_builtin(self) -> None:
        if self._source is None or not self._source.builtin:
            return
        confirm = QMessageBox.question(
            self,
            "Reset Media Type",
            f"Reset \"{self._source.name}\" to its factory default?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        restored = reset_builtin_video_type(self._source)
        category_index = self._category_combo.findData(restored.media_category.value)
        if category_index >= 0:
            self._category_combo.setCurrentIndex(category_index)
        self._format_widget.set_format(restored.rename_format.copy())
        self._mapping_widget.set_format_and_mapping(
            restored.rename_format,
            restored.resolved_metadata_mapping(),
        )

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
        mapping = self._mapping_widget.mapping()
        description_slots = list(mapping.description_slots)
        category_value = self._category_combo.currentData()
        media_category = (
            MediaCategory(category_value)
            if isinstance(category_value, str)
            else MediaCategory.NONE
        )
        selected_folder = self._folder_picker.folder()
        library_folder = (
            str(selected_folder.resolve()) if selected_folder is not None else None
        )

        if self._source is None:
            self._result_profile = create_custom_video_type(
                name,
                rename_format=rename_format,
                media_category=media_category,
            )
            self._result_profile.metadata_field_mapping = mapping
            self._result_profile.metadata_comment_slot_indices = (
                description_slots or None
            )
            self._result_profile.last_library_folder = library_folder
        else:
            updated = self._source.copy()
            if not updated.builtin:
                updated.name = name
                updated.media_category = media_category
                if shows_youtube_append_dropdown(media_category):
                    if updated.youtube_search_append is None:
                        updated.youtube_search_append = default_youtube_search_append(
                            media_category
                        )
                else:
                    updated.youtube_search_append = None
                updated.youtube_append_karaoke = bool(updated.youtube_search_append)
            elif updated.builtin:
                updated.media_category = default_media_category(
                    updated.id,
                    builtin=True,
                )
            updated.rename_format = rename_format
            updated.metadata_field_mapping = mapping
            updated.metadata_comment_slot_indices = description_slots or None
            updated.last_library_folder = library_folder
            self._result_profile = updated
        self.accept()
