"""Side-panel resize controls that stay hittable beside native video.

On macOS fullscreen, VLC's NSView often covers the QSplitter handle and
steals hover/cursor updates. The reliable hit target is a grip on the
non-native song list panel itself.
"""

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QSplitter, QSplitterHandle, QWidget

# Thin splitter gap; the panel edge grip is the real resize affordance.
HANDLE_WIDTH = 2
EDGE_GRIP_WIDTH = 6

HANDLE_STYLE = f"""
QSplitter::handle:horizontal {{
    background: transparent;
    width: {HANDLE_WIDTH}px;
}}
"""

GRIP_STYLE = "background: rgba(255, 255, 255, 30);"
GRIP_ACTIVE_STYLE = "background: rgba(233, 69, 96, 160);"

# Match SeekBar (40) + ControlsBar (56) fixed heights for the reveal hit area.
CONTROLS_BAR_HEIGHT = 56
SEEK_BAR_HEIGHT = 40
CONTROLS_REVEAL_HEIGHT = CONTROLS_BAR_HEIGHT + SEEK_BAR_HEIGHT


class PanelEdgeGrip(QWidget):
    """Right-edge drag strip hosted on the song list (non-native)."""

    dragged = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(EDGE_GRIP_WIDTH)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setStyleSheet(GRIP_STYLE)
        self.setToolTip("Drag to resize")
        self._dragging = False
        self._last_global_x = 0

    def _force_resize_cursor(self) -> None:
        self.setCursor(Qt.CursorShape.SizeHorCursor)

    def enterEvent(self, event) -> None:
        self._force_resize_cursor()
        super().enterEvent(event)

    def event(self, event: QEvent) -> bool:
        if event.type() in (
            QEvent.Type.HoverEnter,
            QEvent.Type.HoverMove,
            QEvent.Type.MouseMove,
        ):
            self._force_resize_cursor()
        return super().event(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._last_global_x = int(event.globalPosition().x())
            self.setStyleSheet(GRIP_ACTIVE_STYLE)
            self._force_resize_cursor()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._force_resize_cursor()
        if self._dragging:
            global_x = int(event.globalPosition().x())
            delta = global_x - self._last_global_x
            self._last_global_x = global_x
            if delta:
                self.dragged.emit(delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.setStyleSheet(GRIP_STYLE)
            self._force_resize_cursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ControlsRevealZone(QWidget):
    """Bottom hover strip that stays hittable when auto-hidden controls are collapsed."""

    hovered = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)
        self.setStyleSheet("background: transparent;")

    def enterEvent(self, event) -> None:
        self.hovered.emit()
        super().enterEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.hovered.emit()
        super().mouseMoveEvent(event)


class PanelSplitterHandle(QSplitterHandle):
    """Fallback handle; may be covered by VLC in fullscreen."""

    def __init__(self, orientation: Qt.Orientation, parent: QSplitter) -> None:
        super().__init__(orientation, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.SizeHorCursor)

    def enterEvent(self, event) -> None:
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        super().enterEvent(event)

    def event(self, event: QEvent) -> bool:
        if event.type() in (
            QEvent.Type.HoverEnter,
            QEvent.Type.HoverMove,
            QEvent.Type.MouseMove,
        ):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        return super().event(event)


class PanelSplitter(QSplitter):
    """QSplitter paired with PanelEdgeGrip for fullscreen-safe resizing."""

    def __init__(self, orientation: Qt.Orientation = Qt.Orientation.Horizontal) -> None:
        super().__init__(orientation)
        self.setHandleWidth(HANDLE_WIDTH)
        self.setStyleSheet(HANDLE_STYLE)

    def createHandle(self) -> QSplitterHandle:
        return PanelSplitterHandle(self.orientation(), self)
