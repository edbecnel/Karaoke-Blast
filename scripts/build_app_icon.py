"""Build a macOS .icns file from the bundled app PNG icon."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication

ICON_SIZES = (
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
)


def render_icon(png_path: Path, size: int) -> QPixmap:
    pixmap = QPixmap(str(png_path))
    if pixmap.isNull():
        raise FileNotFoundError(f"Could not load icon: {png_path}")
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    scaled = image.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    return QPixmap.fromImage(scaled)


def build_icns(png_path: Path, output_path: Path) -> None:
    app = QApplication([])
    iconset_dir = Path(tempfile.mkdtemp(suffix=".iconset"))

    try:
        for size, filename in ICON_SIZES:
            pixmap = render_icon(png_path, size)
            pixmap.save(str(iconset_dir / filename), "PNG")

        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(output_path)],
            check=True,
        )
    finally:
        shutil.rmtree(iconset_dir, ignore_errors=True)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <icon.png> <output.icns>", file=sys.stderr)
        return 1

    png_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    if not png_path.is_file():
        print(f"Icon not found: {png_path}", file=sys.stderr)
        return 1

    build_icns(png_path, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
