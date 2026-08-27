"""Dialog for managing video types: select, add, edit, and delete."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.ui.video_type_editor_dialog import VideoTypeEditorDialog
from karaoke_blast.utils.filename_rename import format_preview
from karaoke_blast.utils.video_types import (
    BUILTIN_SONGS_ID,
    VideoTypeProfile,
    find_video_type,
    reset_builtin_video_type,
)

_DIALOG_STYLE = """
QDialog {
    background-color: #1e1e2e;
}
QListWidget {
    background-color: #2d2d42;
    color: #ffffff;
    border: 1px solid #5a5a72;
    border-radius: 4px;
    padding: 4px;
    font-size: 13px;
    outline: none;
}
QListWidget::item {
    padding: 8px 10px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #e94560;
    color: #ffffff;
}
QListWidget::item:hover {
    background-color: #3a3a52;
}
"""

_BUTTON_STYLE = """
QPushButton {
    background-color: #2d2d42;
    color: white;
    border: 1px solid #5a5a72;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #3a3a52;
    border-color: #7a7a92;
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
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 12px;
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

_HINT_STYLE = "color: #888; font-size: 11px; background: transparent;"
_PREVIEW_STYLE = "color: #7ee787; font-size: 12px; background: transparent;"
_ACTIVE_STYLE = "color: #e94560; font-size: 12px; font-weight: 600; background: transparent;"


class VideoTypesManagerDialog(QDialog):
    """Select, add, edit, and delete video types."""

    def __init__(
        self,
        *,
        video_types: list[VideoTypeProfile],
        active_id: str,
        parent: QWidget | None = None,
        folder_picker_provider: Callable[[], dict] | None = None,
        recent_folders: list[Path] | None = None,
        pinned_folders: list[Path] | None = None,
        pinned_folder_label: str | None = None,
        on_folder_browsed: Callable[[Path], None] | None = None,
        resolve_library_folder: Callable[[VideoTypeProfile], Path | None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._video_types = [profile.copy() for profile in video_types]
        self._active_id = active_id
        self._folder_picker_provider = folder_picker_provider
        self._recent_folders = list(recent_folders or [])
        self._pinned_folders = list(pinned_folders or [])
        self._pinned_folder_label = pinned_folder_label
        self._on_folder_browsed = on_folder_browsed
        self._resolve_library_folder = resolve_library_folder

        self.setWindowTitle("Media Types")
        self.setModal(True)
        self.setMinimumSize(480, 420)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hint = QLabel(
            "Built-in types (Karaoke, Music (Videos), Music (Audio), TV Shows, "
            "Movies, Personal Videos) cannot be deleted. "
            "Their names and media category are read-only, but slot labels and "
            "format can be edited. Custom types can be renamed, edited, or deleted."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(_HINT_STYLE)
        layout.addWidget(hint)

        self._active_label = QLabel()
        self._active_label.setStyleSheet(_ACTIVE_STYLE)
        layout.addWidget(self._active_label)

        self._list = QListWidget()
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        self._list.itemDoubleClicked.connect(self._set_selected_active)
        layout.addWidget(self._list, 1)

        self._preview_label = QLabel()
        self._preview_label.setStyleSheet(_PREVIEW_STYLE)
        self._preview_label.setWordWrap(True)
        layout.addWidget(self._preview_label)

        self._builtin_note = QLabel()
        self._builtin_note.setStyleSheet(_HINT_STYLE)
        self._builtin_note.setWordWrap(True)
        self._builtin_note.hide()
        layout.addWidget(self._builtin_note)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        self._add_btn = QPushButton("Add…")
        self._add_btn.setStyleSheet(_BUTTON_STYLE)
        self._add_btn.clicked.connect(self._add_type)
        button_row.addWidget(self._add_btn)

        self._edit_btn = QPushButton("Edit…")
        self._edit_btn.setStyleSheet(_BUTTON_STYLE)
        self._edit_btn.setToolTip(
            "Edit slot labels and format (built-in type names stay read-only)"
        )
        self._edit_btn.clicked.connect(self._edit_type)
        button_row.addWidget(self._edit_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setStyleSheet(_BUTTON_STYLE)
        self._delete_btn.setToolTip("Remove custom types (built-in types cannot be deleted)")
        self._delete_btn.clicked.connect(self._delete_type)
        button_row.addWidget(self._delete_btn)

        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setStyleSheet(_BUTTON_STYLE)
        self._reset_btn.setToolTip("Restore factory defaults for built-in types")
        self._reset_btn.clicked.connect(self._reset_type)
        button_row.addWidget(self._reset_btn)

        button_row.addStretch()

        self._use_btn = QPushButton("Use Selected")
        self._use_btn.setStyleSheet(_PRIMARY_BUTTON_STYLE)
        self._use_btn.clicked.connect(self._set_selected_active)
        button_row.addWidget(self._use_btn)

        layout.addLayout(button_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setText("Done")
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self._refresh_list()
        self._select_active_in_list()

    def video_types(self) -> list[VideoTypeProfile]:
        return [profile.copy() for profile in self._video_types]

    def active_id(self) -> str:
        return self._active_id

    def _selected_profile(self) -> VideoTypeProfile | None:
        item = self._list.currentItem()
        if item is None:
            return None
        profile_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(profile_id, str):
            return None
        return find_video_type(self._video_types, profile_id)

    def _refresh_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for profile in self._video_types:
            prefix = "● " if profile.id == self._active_id else "   "
            suffix = " (built-in)" if profile.builtin else ""
            item = QListWidgetItem(f"{prefix}{profile.name}{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, profile.id)
            self._list.addItem(item)
        self._list.blockSignals(False)
        self._update_active_label()
        self._on_selection_changed()

    def _select_active_in_list(self) -> None:
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item is None:
                continue
            profile_id = item.data(Qt.ItemDataRole.UserRole)
            if profile_id == self._active_id:
                self._list.setCurrentRow(row)
                return
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _update_active_label(self) -> None:
        active = find_video_type(self._video_types, self._active_id)
        if active is None:
            self._active_label.setText("Active: —")
            return
        self._active_label.setText(f"Active: {active.name}")

    def _on_selection_changed(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            self._preview_label.clear()
            self._builtin_note.hide()
            self._edit_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            self._reset_btn.setEnabled(False)
            self._use_btn.setEnabled(False)
            return

        preview = format_preview(profile.rename_format)
        self._preview_label.setText(f"Pattern: {preview}" if preview else "Pattern: —")
        if profile.builtin:
            self._builtin_note.setText(
                f"\"{profile.name}\" is a built-in type. Its name is read-only, "
                "but you can edit slot labels and format."
            )
            self._builtin_note.show()
        else:
            self._builtin_note.hide()
        self._edit_btn.setEnabled(True)
        self._delete_btn.setEnabled(not profile.builtin)
        self._reset_btn.setEnabled(profile.builtin)
        self._use_btn.setEnabled(profile.id != self._active_id)

    def _replace_profile(self, profile: VideoTypeProfile) -> None:
        for index, existing in enumerate(self._video_types):
            if existing.id == profile.id:
                self._video_types[index] = profile.copy()
                return
        self._video_types.append(profile.copy())

    def _set_selected_active(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        self._active_id = profile.id
        self._refresh_list()
        self._select_active_in_list()

    def _editor_folder_kwargs(self, profile: VideoTypeProfile | None = None) -> dict:
        if self._folder_picker_provider is not None:
            kwargs = dict(self._folder_picker_provider())
        else:
            kwargs = {
                "recent_folders": self._recent_folders,
                "pinned_folders": self._pinned_folders,
                "pinned_folder_label": self._pinned_folder_label,
                "on_folder_browsed": self._on_folder_browsed,
            }
        initial_library_folder: Path | None = None
        if profile is not None:
            if profile.last_library_folder:
                initial_library_folder = Path(profile.last_library_folder)
            else:
                resolver = kwargs.get("resolve_library_folder", self._resolve_library_folder)
                if resolver is not None:
                    initial_library_folder = resolver(profile)
        kwargs["initial_library_folder"] = initial_library_folder
        kwargs.pop("resolve_library_folder", None)
        return kwargs

    def _add_type(self) -> None:
        dialog = VideoTypeEditorDialog(self, **self._editor_folder_kwargs())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        profile = dialog.profile()
        if profile is None:
            return
        self._video_types.append(profile)
        self._active_id = profile.id
        self._refresh_list()
        self._select_active_in_list()

    def _edit_type(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        dialog = VideoTypeEditorDialog(
            self,
            profile=profile,
            **self._editor_folder_kwargs(profile),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.profile()
        if updated is None:
            return
        self._replace_profile(updated)
        self._refresh_list()
        self._select_profile_by_id(updated.id)

    def _select_profile_by_id(self, profile_id: str) -> None:
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == profile_id:
                self._list.setCurrentRow(row)
                return

    def _delete_type(self) -> None:
        profile = self._selected_profile()
        if profile is None or profile.builtin:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Media Type",
            f"Delete the custom type \"{profile.name}\"?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._video_types = [item for item in self._video_types if item.id != profile.id]
        if self._active_id == profile.id:
            self._active_id = BUILTIN_SONGS_ID
        self._refresh_list()
        self._select_active_in_list()

    def _reset_type(self) -> None:
        profile = self._selected_profile()
        if profile is None or not profile.builtin:
            return
        confirm = QMessageBox.question(
            self,
            "Reset Media Type",
            f"Reset \"{profile.name}\" to its factory default?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        restored = reset_builtin_video_type(profile)
        self._replace_profile(restored)
        self._refresh_list()
        self._select_profile_by_id(restored.id)
