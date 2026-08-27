"""Media type dropdown for the startup screen."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSizePolicy, QWidget

from karaoke_blast.utils.video_types import (
    BUILTIN_ANY_ID,
    VideoTypeProfile,
    find_video_type,
)

_COMBO_STYLE = """
QComboBox {
    background-color: #2d2d42;
    color: #ffffff;
    border: 1px solid #5a5a72;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 16px;
    min-height: 20px;
}
QComboBox:hover {
    border-color: #7a7a92;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #ffffff;
    margin-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    color: #ffffff;
    border: 1px solid #5a5a72;
    selection-background-color: #e94560;
    selection-color: #ffffff;
    outline: none;
    font-size: 16px;
    padding: 4px;
}
"""

_LABEL_STYLE = "color: #ccc; font-size: 16px; background: transparent;"


class StartupMediaTypeSelector(QWidget):
    """Dropdown for selecting the active media type on the startup screen."""

    type_changed = pyqtSignal(object)

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

        label = QLabel("Media type:")
        label.setStyleSheet(_LABEL_STYLE)
        layout.addWidget(label)

        self._combo = QComboBox()
        self._combo.setStyleSheet(_COMBO_STYLE)
        self._combo.setMinimumWidth(360)
        self._combo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self._combo, 1)

        self._rebuild_combo()

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
        self._building = False

    def active_id(self) -> str:
        return self._active_id

    def _rebuild_combo(self) -> None:
        self._combo.blockSignals(True)
        self._combo.clear()
        for profile in self._video_types:
            self._combo.addItem(profile.name, profile.id)
        index = self._combo.findData(self._active_id)
        if index < 0:
            index = self._combo.findData(BUILTIN_ANY_ID)
        if index < 0 and self._combo.count() > 0:
            index = 0
        if index >= 0:
            self._combo.setCurrentIndex(index)
            self._active_id = str(self._combo.currentData())
        self._combo.blockSignals(False)

    def _on_combo_changed(self, _index: int) -> None:
        if self._building:
            return
        profile_id = self._combo.currentData()
        if not isinstance(profile_id, str):
            return
        self._active_id = profile_id
        profile = find_video_type(self._video_types, profile_id)
        if profile is not None:
            self.type_changed.emit(profile.copy())
