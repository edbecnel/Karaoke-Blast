"""On-screen playback controls."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QWidget,
)

BUTTON_STYLE = (
    "QPushButton { background: transparent; color: white; border: none;"
    " font-size: 18px; min-width: 40px; min-height: 36px; border-radius: 4px; }"
    "QPushButton:hover { background: rgba(255, 255, 255, 40); }"
    "QPushButton:pressed { background: rgba(255, 255, 255, 70); }"
)

PLAY_STYLE = (
    "QPushButton { background: #e94560; color: white; border: none;"
    " font-size: 18px; min-width: 44px; min-height: 36px; border-radius: 6px; }"
    "QPushButton:hover { background: #ff6b81; }"
)

PIN_STYLE = (
    "QPushButton { background: transparent; color: white; border: none;"
    " font-size: 18px; min-width: 40px; min-height: 36px; border-radius: 4px; }"
    "QPushButton:hover { background: rgba(255, 255, 255, 40); }"
    "QPushButton:pressed { background: rgba(255, 255, 255, 70); }"
    "QPushButton:checked { background: rgba(233, 69, 96, 120); }"
)

SLIDER_STYLE = (
    "QSlider::groove:horizontal { height: 4px; background: rgba(255,255,255,80);"
    " border-radius: 2px; }"
    "QSlider::handle:horizontal { width: 14px; margin: -5px 0; background: white;"
    " border-radius: 7px; }"
    "QSlider::sub-page:horizontal { background: #e94560; border-radius: 2px; }"
)


class ControlsBar(QWidget):
    """Bottom playback control bar."""

    play_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    previous_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    rewind_clicked = pyqtSignal()
    forward_clicked = pyqtSignal()
    volume_changed = pyqtSignal(int)
    mute_toggled = pyqtSignal()
    list_toggled = pyqtSignal()
    pin_toggled = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            "background-color: rgba(0, 0, 0, 180);"
            " border-top: 1px solid rgba(255, 255, 255, 30);"
        )
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(4)

        self._prev_btn = self._make_button("⏮", "Previous song")
        self._rewind_btn = self._make_button("⏪", "Rewind 10 seconds")
        self._play_btn = self._make_button("▶", "Play", style=PLAY_STYLE)
        self._pause_btn = self._make_button("⏸", "Pause")
        self._stop_btn = self._make_button("⏹", "Stop")
        self._forward_btn = self._make_button("⏩", "Fast forward 10 seconds")
        self._next_btn = self._make_button("⏭", "Next song")

        self._prev_btn.clicked.connect(self.previous_clicked)
        self._rewind_btn.clicked.connect(self.rewind_clicked)
        self._play_btn.clicked.connect(self.play_clicked)
        self._pause_btn.clicked.connect(self.pause_clicked)
        self._stop_btn.clicked.connect(self.stop_clicked)
        self._forward_btn.clicked.connect(self.forward_clicked)
        self._next_btn.clicked.connect(self.next_clicked)

        layout.addWidget(self._prev_btn)
        layout.addWidget(self._rewind_btn)
        layout.addWidget(self._play_btn)
        layout.addWidget(self._pause_btn)
        layout.addWidget(self._stop_btn)
        layout.addWidget(self._forward_btn)
        layout.addWidget(self._next_btn)

        self._list_btn = self._make_button("☰", "Song list (L)")
        self._list_btn.clicked.connect(self.list_toggled)
        layout.addWidget(self._list_btn)

        self._pin_btn = self._make_button("📌", "Pin controls (always visible)", style=PIN_STYLE)
        self._pin_btn.setCheckable(True)
        self._pin_btn.toggled.connect(self._on_pin_toggled)
        layout.addWidget(self._pin_btn)
        layout.addStretch()

        self._mute_btn = self._make_button("🔊", "Mute / unmute")
        self._mute_btn.clicked.connect(self.mute_toggled)
        layout.addWidget(self._mute_btn)

        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.setFixedWidth(120)
        self._volume_slider.setStyleSheet(SLIDER_STYLE)
        self._volume_slider.valueChanged.connect(self._on_volume_slider)
        layout.addWidget(self._volume_slider)

        self._volume_label = QLabel("80%")
        self._volume_label.setStyleSheet("color: white; font-size: 12px; min-width: 36px;")
        self._volume_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._volume_label)

    def _make_button(self, text: str, tooltip: str, *, style: str = BUTTON_STYLE) -> QPushButton:
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(style)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def _on_pin_toggled(self, pinned: bool) -> None:
        self._pin_btn.setToolTip(
            "Unpin controls (auto-hide)" if pinned else "Pin controls (always visible)"
        )
        self.pin_toggled.emit(pinned)

    def set_pinned(self, pinned: bool) -> None:
        self._pin_btn.blockSignals(True)
        self._pin_btn.setChecked(pinned)
        self._pin_btn.blockSignals(False)
        self._pin_btn.setToolTip(
            "Unpin controls (auto-hide)" if pinned else "Pin controls (always visible)"
        )

    def is_pinned(self) -> bool:
        return self._pin_btn.isChecked()

    def _on_volume_slider(self, value: int) -> None:
        self._volume_label.setText(f"{value}%")
        self.volume_changed.emit(value)

    def set_volume(self, value: int, *, emit: bool = False) -> None:
        value = max(0, min(100, value))
        self._volume_slider.blockSignals(True)
        self._volume_slider.setValue(value)
        self._volume_slider.blockSignals(False)
        self._volume_label.setText(f"{value}%")
        if emit:
            self.volume_changed.emit(value)

    def set_muted(self, muted: bool) -> None:
        self._mute_btn.setText("🔇" if muted else "🔊")

    def volume(self) -> int:
        return self._volume_slider.value()

    def adjust_volume(self, delta: int) -> int:
        value = max(0, min(100, self._volume_slider.value() + delta))
        self.set_volume(value, emit=True)
        return value

    def show_bar(self) -> None:
        self.show()
        self.raise_()
