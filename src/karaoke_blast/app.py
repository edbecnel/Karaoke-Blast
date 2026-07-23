"""Application bootstrap."""

import logging
import os
import sys
from importlib.util import find_spec
from pathlib import Path


def _configure_qt_plugin_path() -> None:
    """Point Qt at PyQt6's bundled plugins (avoids broken system/conda Qt paths)."""
    spec = find_spec("PyQt6")
    if spec is None or spec.origin is None:
        return
    platforms = Path(spec.origin).resolve().parent / "Qt6" / "plugins" / "platforms"
    if platforms.is_dir():
        os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(platforms))


_configure_qt_plugin_path()

from PyQt6.QtWidgets import QApplication

from karaoke_blast.main_window import MainWindow
from karaoke_blast.utils.resources import app_icon

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def run(initial_folder: Path | None = None) -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Karaoke Blast")
    icon = app_icon()
    app.setWindowIcon(icon)

    window = MainWindow(initial_folder=initial_folder)
    window.setWindowIcon(icon)
    window.show()
    return app.exec()
