"""Auto-hiding playback position scrubber."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QWidget

from karaoke_blast.player.controls_bar import SLIDER_STYLE


def format_time(ms: int) -> str:
    if ms < 0:
        ms = 0
    total_seconds = ms // 1000
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


class SeekBar(QWidget):
    """Horizontal scrubber for the current video position."""

    seek_requested = pyqtSignal(int)
    interaction_started = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            "background-color: rgba(0, 0, 0, 180);"
            " border-top: 1px solid rgba(255, 255, 255, 20);"
        )
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(10)

        self._current_label = QLabel("0:00")
        self._current_label.setStyleSheet("color: white; font-size: 12px; min-width: 44px;")
        self._current_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._current_label)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.setEnabled(False)
        self._slider.setToolTip("Drag to change playback position")
        self._slider.setStyleSheet(SLIDER_STYLE)
        self._slider.sliderPressed.connect(self._on_slider_pressed)
        self._slider.sliderReleased.connect(self._on_slider_released)
        self._slider.sliderMoved.connect(self._on_slider_moved)
        self._slider.valueChanged.connect(self._on_slider_value_changed)
        layout.addWidget(self._slider, 1)

        self._duration_label = QLabel("0:00")
        self._duration_label.setStyleSheet("color: #b8b8c8; font-size: 12px; min-width: 44px;")
        self._duration_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._duration_label)

        self._scrubbing = False
        self._duration_ms = 0

    def is_scrubbing(self) -> bool:
        return self._scrubbing

    def reset(self) -> None:
        self._scrubbing = False
        self._duration_ms = 0
        self._slider.blockSignals(True)
        self._slider.setRange(0, 0)
        self._slider.setValue(0)
        self._slider.setEnabled(False)
        self._slider.blockSignals(False)
        self._current_label.setText("0:00")
        self._duration_label.setText("0:00")

    def set_duration(self, duration_ms: int) -> None:
        duration_ms = max(0, duration_ms)
        if duration_ms == self._duration_ms:
            return
        self._duration_ms = duration_ms
        self._slider.blockSignals(True)
        self._slider.setRange(0, duration_ms)
        self._slider.setEnabled(duration_ms > 0)
        self._slider.blockSignals(False)
        self._duration_label.setText(format_time(duration_ms))

    def set_position(self, position_ms: int) -> None:
        if self._scrubbing:
            return
        position_ms = max(0, position_ms)
        if self._duration_ms > 0:
            position_ms = min(position_ms, self._duration_ms)
        self._slider.blockSignals(True)
        self._slider.setValue(position_ms)
        self._slider.blockSignals(False)
        self._current_label.setText(format_time(position_ms))

    def _on_slider_pressed(self) -> None:
        self._scrubbing = True
        self.interaction_started.emit()

    def _on_slider_released(self) -> None:
        self._scrubbing = False
        self.seek_requested.emit(self._slider.value())

    def _on_slider_moved(self, value: int) -> None:
        self._current_label.setText(format_time(value))

    def _on_slider_value_changed(self, value: int) -> None:
        if self._scrubbing:
            self._current_label.setText(format_time(value))
