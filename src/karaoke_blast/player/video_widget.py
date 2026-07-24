"""Widget that hosts the VLC video output."""

import sys

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget


class VideoClickOverlay(QWidget):
    """Transparent layer above embedded VLC video to receive mouse input."""

    double_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class VideoWidget(QWidget):
    """Surface for embedding a VLC media player."""

    bind_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background-color: black;")
        self.setMinimumSize(640, 360)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self._player = None

    def win_id(self) -> int:
        return int(self.winId())

    def bind_player(self, player) -> None:
        """Attach *player* (python-vlc MediaPlayer) to this widget."""
        if not self.isVisible():
            return
        wid = self.win_id()
        if wid == 0:
            return
        if sys.platform == "win32":
            player.set_hwnd(wid)
        elif sys.platform == "darwin":
            player.set_nsobject(wid)
        else:
            player.set_xwindow(wid)

    def set_player(self, player) -> None:
        self._player = player
        self.bind_player(player)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._player is not None:
            self.bind_player(self._player)
        self.bind_requested.emit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._player is not None:
            self.bind_player(self._player)
