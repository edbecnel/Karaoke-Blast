"""Load bundled icons and other static assets."""

import sys
from importlib.resources import files
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap

_ICON_SIZES = (16, 32, 48, 64, 128, 256, 512)


def _asset_path(name: str) -> Path:
    return Path(files("karaoke_blast.assets") / name)


def icon_path() -> Path:
    return _asset_path("icon.png")


def icon_ico_path() -> Path:
    return _asset_path("icon.ico")


def logo_path() -> Path:
    return _asset_path("logo.png")


def _load_pixmap(path: Path) -> QPixmap:
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        raise FileNotFoundError(f"Could not load image: {path}")
    return pixmap


def _scaled_square_pixmap(path: Path, size: int) -> QPixmap:
    pixmap = _load_pixmap(path)
    return pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _icon_from_png() -> QIcon:
    path = icon_path()
    icon = QIcon()
    for size in _ICON_SIZES:
        icon.addPixmap(_scaled_square_pixmap(path, size))
    return icon


def app_icon() -> QIcon:
    if sys.platform == "win32":
        ico_path = icon_ico_path()
        if ico_path.is_file():
            icon = QIcon(str(ico_path))
            if not icon.isNull():
                return icon
    return _icon_from_png()


def icon_pixmap(size: int = 128) -> QPixmap:
    return _scaled_square_pixmap(icon_path(), size)


def logo_pixmap(max_size: int = 128) -> QPixmap:
    pixmap = logo_pixmap_source()
    if pixmap.width() <= max_size and pixmap.height() <= max_size:
        return pixmap
    return pixmap.scaled(
        max_size,
        max_size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def logo_pixmap_source() -> QPixmap:
    return _load_pixmap(logo_path())


def logo_default_window_size(max_dimension: int = 840) -> tuple[int, int]:
    pixmap = logo_pixmap_source()
    if pixmap.width() <= 0 or pixmap.height() <= 0:
        return max_dimension, max_dimension
    scale = max_dimension / max(pixmap.width(), pixmap.height())
    return int(pixmap.width() * scale), int(pixmap.height() * scale)
