"""Application bootstrap."""

import logging
import sys
from pathlib import Path

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
