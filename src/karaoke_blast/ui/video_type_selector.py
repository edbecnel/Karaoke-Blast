"""Video type selector for rename and metadata workflows."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)

from karaoke_blast.ui.video_type_editor_dialog import VideoTypeEditorDialog
from karaoke_blast.utils.video_types import (
    BUILTIN_SONGS_ID,
    VideoTypeProfile,
    find_video_type,
    reset_builtin_video_type,
)

_COMBO_STYLE = """
QComboBox {
    background-color: #2d2d42;
    color: #ffffff;
    border: 1px solid #5a5a72;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
QComboBox:hover {
    border-color: #7a7a92;
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
QPushButton:disabled {
    color: #666;
    border-color: #3a3a52;
}
"""

_LABEL_STYLE = "color: #ccc; font-size: 13px; background: transparent;"


class VideoTypeSelectorWidget(QWidget):
    """Dropdown and actions for selecting and managing video types."""

    type_changed = pyqtSignal(object)
    types_changed = pyqtSignal(object)

    def __init__(
        self,
        *,
        video_types: list[VideoTypeProfile],
        active_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._video_types = [profile.copy() for profile in video_types]
        self._active_id = active_id
        self._building = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel("Video type:")
        label.setStyleSheet(_LABEL_STYLE)
        layout.addWidget(label)

        self._combo = QComboBox()
        self._combo.setStyleSheet(_COMBO_STYLE)
        self._combo.setMinimumWidth(160)
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self._combo, 1)

        self._add_btn = QPushButton("Add…")
        self._add_btn.setStyleSheet(_BUTTON_STYLE)
        self._add_btn.clicked.connect(self._add_type)
        layout.addWidget(self._add_btn)

        self._edit_btn = QPushButton("Edit…")
        self._edit_btn.setStyleSheet(_BUTTON_STYLE)
        self._edit_btn.setToolTip(
            "Edit slot labels and format (built-in type names are read-only)"
        )
        self._edit_btn.clicked.connect(self._edit_type)
        layout.addWidget(self._edit_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setStyleSheet(_BUTTON_STYLE)
        self._delete_btn.setToolTip("Built-in types cannot be deleted")
        self._delete_btn.clicked.connect(self._delete_type)
        layout.addWidget(self._delete_btn)

        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setStyleSheet(_BUTTON_STYLE)
        self._reset_btn.setToolTip("Restore factory defaults for built-in types")
        self._reset_btn.clicked.connect(self._reset_type)
        layout.addWidget(self._reset_btn)

        self._rebuild_combo()
        self._update_action_states()

    def open_manager(self) -> None:
        """Open the full video types manager dialog."""
        from karaoke_blast.ui.video_types_manager_dialog import VideoTypesManagerDialog

        dialog = VideoTypesManagerDialog(
            video_types=self._video_types,
            active_id=self._active_id,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._video_types = dialog.video_types()
        self._active_id = dialog.active_id()
        self._rebuild_combo()
        self._update_action_states()
        self.types_changed.emit(self.video_types())
        active = find_video_type(self._video_types, self._active_id)
        if active is not None:
            self.type_changed.emit(active.copy())

    def video_types(self) -> list[VideoTypeProfile]:
        return [profile.copy() for profile in self._video_types]

    def active_id(self) -> str:
        return self._active_id

    def active_profile(self) -> VideoTypeProfile:
        profile = find_video_type(self._video_types, self._active_id)
        if profile is not None:
            return profile.copy()
        return self._video_types[0].copy()

    def set_video_types(
        self,
        video_types: list[VideoTypeProfile],
        *,
        active_id: str | None = None,
    ) -> None:
        self._building = True
        self._video_types = [profile.copy() for profile in video_types]
        if active_id is not None:
            if find_video_type(self._video_types, active_id) is not None:
                self._active_id = active_id
        self._rebuild_combo()
        self._update_action_states()
        self._building = False

    def set_active_id(self, active_id: str) -> None:
        if find_video_type(self._video_types, active_id) is None:
            return
        self._building = True
        self._active_id = active_id
        index = self._combo.findData(active_id)
        if index >= 0:
            self._combo.setCurrentIndex(index)
        self._update_action_states()
        self._building = False

    def update_active_profile(self, profile: VideoTypeProfile) -> None:
        for index, existing in enumerate(self._video_types):
            if existing.id == profile.id:
                self._video_types[index] = profile.copy()
                break
        if profile.id == self._active_id:
            self.type_changed.emit(profile.copy())

    def _rebuild_combo(self) -> None:
        self._combo.blockSignals(True)
        self._combo.clear()
        for profile in self._video_types:
            self._combo.addItem(profile.name, profile.id)
        index = self._combo.findData(self._active_id)
        if index < 0:
            index = self._combo.findData(BUILTIN_SONGS_ID)
        if index < 0 and self._combo.count() > 0:
            index = 0
        if index >= 0:
            self._combo.setCurrentIndex(index)
            self._active_id = str(self._combo.currentData())
        self._combo.blockSignals(False)

    def _update_action_states(self) -> None:
        profile = find_video_type(self._video_types, self._active_id)
        is_builtin = profile is not None and profile.builtin
        self._edit_btn.setEnabled(profile is not None)
        self._delete_btn.setEnabled(profile is not None and not profile.builtin)
        self._reset_btn.setEnabled(is_builtin)

    def _on_combo_changed(self, _index: int) -> None:
        if self._building:
            return
        profile_id = self._combo.currentData()
        if not isinstance(profile_id, str):
            return
        self._active_id = profile_id
        self._update_action_states()
        profile = find_video_type(self._video_types, profile_id)
        if profile is not None:
            self.type_changed.emit(profile.copy())

    def _add_type(self) -> None:
        dialog = VideoTypeEditorDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        profile = dialog.profile()
        if profile is None:
            return
        self._video_types.append(profile)
        self._active_id = profile.id
        self._rebuild_combo()
        self._update_action_states()
        self.types_changed.emit(self.video_types())
        self.type_changed.emit(profile.copy())

    def _edit_type(self) -> None:
        profile = find_video_type(self._video_types, self._active_id)
        if profile is None:
            return
        dialog = VideoTypeEditorDialog(self, profile=profile)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.profile()
        if updated is None:
            return
        for index, existing in enumerate(self._video_types):
            if existing.id == updated.id:
                self._video_types[index] = updated
                break
        self._rebuild_combo()
        self._update_action_states()
        self.types_changed.emit(self.video_types())
        self.type_changed.emit(updated.copy())

    def _delete_type(self) -> None:
        profile = find_video_type(self._video_types, self._active_id)
        if profile is None or profile.builtin:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Video Type",
            f"Delete the custom type \"{profile.name}\"?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._video_types = [item for item in self._video_types if item.id != profile.id]
        self._active_id = BUILTIN_SONGS_ID
        self._rebuild_combo()
        self._update_action_states()
        self.types_changed.emit(self.video_types())
        active = find_video_type(self._video_types, self._active_id)
        if active is not None:
            self.type_changed.emit(active.copy())

    def _reset_type(self) -> None:
        profile = find_video_type(self._video_types, self._active_id)
        if profile is None or not profile.builtin:
            return
        confirm = QMessageBox.question(
            self,
            "Reset Video Type",
            f"Reset \"{profile.name}\" to its factory default?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        restored = reset_builtin_video_type(profile)
        for index, existing in enumerate(self._video_types):
            if existing.id == restored.id:
                self._video_types[index] = restored
                break
        self._update_action_states()
        self.types_changed.emit(self.video_types())
        self.type_changed.emit(restored.copy())
