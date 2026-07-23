"""Load bundled icons and other static assets."""

from importlib.resources import files
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

_ICON_SIZES = (16, 32, 48, 64, 128, 256, 512)


def icon_path() -> Path:
    return Path(files("karaoke_blast.assets") / "icon.svg")


def _render_svg(size: int) -> QPixmap:
    renderer = QSvgRenderer(str(icon_path()))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def app_icon() -> QIcon:
    icon = QIcon()
    for size in _ICON_SIZES:
        icon.addPixmap(_render_svg(size))
    return icon


def icon_pixmap(size: int = 128) -> QPixmap:
    return _render_svg(size)
