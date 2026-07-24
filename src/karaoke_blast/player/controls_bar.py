"""On-screen playback controls."""

import sys

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStyleFactory,
    QWidget,
)

# Fully specify border + background so Windows native chrome does not show through.
BUTTON_STYLE = (
    "QPushButton {"
    " background-color: rgba(0, 0, 0, 0); color: white;"
    " border: 0px solid transparent;"
    " font-size: 18px; min-width: 40px; min-height: 36px;"
    " padding: 4px; border-radius: 4px;"
    "}"
    "QPushButton:hover { background-color: rgba(255, 255, 255, 40); }"
    "QPushButton:pressed { background-color: rgba(255, 255, 255, 70); }"
    "QPushButton:focus { outline: none; border: 0px solid transparent; }"
)

PLAY_STYLE = (
    "QPushButton {"
    " background-color: #e94560; color: white;"
    " border: 0px solid transparent;"
    " font-size: 18px; min-width: 44px; min-height: 36px;"
    " padding: 4px; border-radius: 6px;"
    "}"
    "QPushButton:hover { background-color: #ff6b81; }"
    "QPushButton:pressed { background-color: #d63850; }"
    "QPushButton:focus { outline: none; border: 0px solid transparent; }"
)

PIN_STYLE = (
    "QPushButton {"
    " background-color: rgba(0, 0, 0, 0); color: white;"
    " border: 0px solid transparent;"
    " font-size: 18px; min-width: 40px; min-height: 36px;"
    " padding: 4px; border-radius: 4px;"
    "}"
    "QPushButton:hover { background-color: rgba(255, 255, 255, 40); }"
    "QPushButton:pressed { background-color: rgba(255, 255, 255, 70); }"
    "QPushButton:checked { background-color: rgba(233, 69, 96, 120); }"
    "QPushButton:focus { outline: none; border: 0px solid transparent; }"
)

SLIDER_STYLE = (
    "QSlider::groove:horizontal { height: 4px; background: rgba(255,255,255,80);"
    " border-radius: 2px; }"
    "QSlider::handle:horizontal { width: 14px; margin: -5px 0; background: white;"
    " border-radius: 7px; }"
    "QSlider::sub-page:horizontal { background: #e94560; border-radius: 2px; }"
)


def _transport_icons() -> dict[str, str]:
    """Media-control emoji render with light-blue button art on Windows; use plain glyphs there."""
    if sys.platform == "win32":
        return {
            "previous": "|<",
            "rewind": "<<",
            "stop": "■",
            "forward": ">>",
            "next": ">|",
        }
    return {
        "previous": "⏮",
        "rewind": "⏪",
        "stop": "⏹",
        "forward": "⏩",
        "next": "⏭",
    }


def _pause_icon() -> str:
    """⏸ renders with a light-blue emoji background on Windows."""
    return "Ⅱ" if sys.platform == "win32" else "⏸"


def _apply_windows_button_style(btn: QPushButton) -> None:
    """Windows native styles ignore transparent button sheets; Fusion honors them."""
    if sys.platform != "win32":
        return
    fusion = QStyleFactory.create("Fusion")
    if fusion is not None:
        btn.setStyle(fusion)
    btn.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class ControlsBar(QWidget):
    """Bottom playback control bar."""

    play_pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    previous_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    rewind_clicked = pyqtSignal()
    forward_clicked = pyqtSignal()
    volume_changed = pyqtSignal(int)
    mute_toggled = pyqtSignal()
    list_toggled = pyqtSignal()
    pin_toggled = pyqtSignal(bool)
    fullscreen_toggled = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("controlsBar")
        self.setStyleSheet(
            "#controlsBar {"
            " background-color: rgba(0, 0, 0, 180);"
            " border-top: 1px solid rgba(255, 255, 255, 30);"
            "}"
        )
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(4)

        icons = _transport_icons()
        self._prev_btn = self._make_button(icons["previous"], "Previous song")
        self._rewind_btn = self._make_button(icons["rewind"], "Rewind 10 seconds")
        self._play_pause_btn = self._make_button(
            "▶", "Play (Space)", style=PLAY_STYLE, flat=False
        )
        self._stop_btn = self._make_button(icons["stop"], "Stop")
        self._forward_btn = self._make_button(icons["forward"], "Fast forward 10 seconds")
        self._next_btn = self._make_button(icons["next"], "Next song")

        self._prev_btn.clicked.connect(self.previous_clicked)
        self._rewind_btn.clicked.connect(self.rewind_clicked)
        self._play_pause_btn.clicked.connect(self.play_pause_clicked)
        self._stop_btn.clicked.connect(self.stop_clicked)
        self._forward_btn.clicked.connect(self.forward_clicked)
        self._next_btn.clicked.connect(self.next_clicked)

        layout.addWidget(self._prev_btn)
        layout.addWidget(self._rewind_btn)
        layout.addWidget(self._play_pause_btn)
        layout.addWidget(self._stop_btn)
        layout.addWidget(self._forward_btn)
        layout.addWidget(self._next_btn)

        self._list_btn = self._make_button("☰", "Song list (L)")
        self._list_btn.clicked.connect(self.list_toggled)
        layout.addWidget(self._list_btn)

        self._fullscreen_btn = self._make_button("⛶", "Full screen (F)")
        self._fullscreen_btn.clicked.connect(self.fullscreen_toggled)
        layout.addWidget(self._fullscreen_btn)

        self._pin_btn = self._make_button(
            "📌", "Pin controls (always visible)", style=PIN_STYLE
        )
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
        self._volume_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._volume_label)

    def _make_button(
        self,
        text: str,
        tooltip: str,
        *,
        style: str = BUTTON_STYLE,
        flat: bool = True,
    ) -> QPushButton:
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setFlat(flat)
        btn.setAutoDefault(False)
        btn.setDefault(False)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _apply_windows_button_style(btn)
        btn.setStyleSheet(style)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def set_playing(self, playing: bool) -> None:
        if playing:
            self._play_pause_btn.setText(_pause_icon())
            self._play_pause_btn.setToolTip("Pause (Space)")
        else:
            self._play_pause_btn.setText("▶")
            self._play_pause_btn.setToolTip("Play (Space)")

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

    def set_fullscreen(self, fullscreen: bool) -> None:
        if fullscreen:
            self._fullscreen_btn.setText("⤡")
            self._fullscreen_btn.setToolTip("Exit full screen (Esc)")
        else:
            self._fullscreen_btn.setText("⛶")
            self._fullscreen_btn.setToolTip("Full screen (F)")

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
