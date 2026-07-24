"""Startup screen with a full-window logo background."""

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from karaoke_blast.utils.resources import logo_pixmap_source

_BACKGROUND = QColor(12, 10, 22)
_OVERLAY = QColor(12, 10, 22, 140)


class OpeningScreen(QWidget):
    """Empty state page that paints logo.png fitted inside the window."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._logo = logo_pixmap_source()
        self.setAutoFillBackground(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)
        self._content = QWidget()
        self._content.setAutoFillBackground(False)
        self._content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(32, 32, 32, 32)
        self._content_layout.setSpacing(14)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._content, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)

    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def _image_rect(self) -> QRect:
        scaled = self._logo.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        return QRect(x, y, scaled.width(), scaled.height())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), _BACKGROUND)
        image_rect = self._image_rect()
        painter.drawPixmap(image_rect, self._logo)
        painter.fillRect(image_rect, _OVERLAY)
        painter.end()
