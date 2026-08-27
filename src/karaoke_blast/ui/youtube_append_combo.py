"""Shared YouTube append-to-search combo widget."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from karaoke_blast.utils.video_types import (
    YOUTUBE_APPEND_COMBO_ITEMS,
    MediaCategory,
    shows_youtube_append_dropdown,
    youtube_append_combo_index,
    youtube_append_from_combo_index,
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


class YouTubeAppendComboRow(QWidget):
    """Label + combo for Karaoke / Videoke / None append-to-search."""

    append_changed = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel("Append to search:")
        label.setStyleSheet("color: #ccc; font-size: 12px;")
        layout.addWidget(label)

        self._combo = QComboBox()
        self._combo.setStyleSheet(_COMBO_STYLE)
        for display, value in YOUTUBE_APPEND_COMBO_ITEMS:
            self._combo.addItem(display, value)
        self._combo.currentIndexChanged.connect(self._on_index_changed)
        layout.addWidget(self._combo, 1)

        self._append: str | None = YOUTUBE_APPEND_COMBO_ITEMS[0][1]

    def configure(self, *, category: MediaCategory, append: str | None) -> None:
        visible = shows_youtube_append_dropdown(category)
        self.setVisible(visible)
        if not visible:
            return
        self._append = append
        self._combo.blockSignals(True)
        self._combo.setCurrentIndex(youtube_append_combo_index(append))
        self._combo.blockSignals(False)

    def append_value(self) -> str | None:
        return self._append

    def _on_index_changed(self, index: int) -> None:
        self._append = youtube_append_from_combo_index(index)
        self.append_changed.emit(self._append)
