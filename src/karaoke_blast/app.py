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

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication

from karaoke_blast.main_window import MainWindow
from karaoke_blast.utils.macos_dock_icon import clear_macos_dock_icon_override
from karaoke_blast.utils.resources import app_icon
from karaoke_blast.utils.runtime_deps import configure_runtime_dependencies

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

_APP_USER_MODEL_ID = "edbecnel.KaraokeBlast.1"


def _macos_activate_foreground() -> None:
    """Become a regular GUI app so Qt windows map on screen when launched from Finder."""
    if sys.platform != "darwin":
        return
    try:
        import ctypes
        from ctypes import c_int, c_void_p

        libobjc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
        libobjc.objc_getClass.restype = c_void_p
        libobjc.sel_registerName.restype = c_void_p

        def _msg(restype, *argtypes):
            func = libobjc.objc_msgSend
            func.restype = restype
            func.argtypes = argtypes
            return func

        ns_app = _msg(c_void_p, c_void_p, c_void_p)(
            libobjc.objc_getClass(b"NSApplication"),
            libobjc.sel_registerName(b"sharedApplication"),
        )
        if not ns_app:
            return

        # NSApplicationActivationPolicyRegular = 0
        _msg(c_int, c_void_p, c_void_p, c_int)(
            ns_app,
            libobjc.sel_registerName(b"setActivationPolicy:"),
            0,
        )
        _msg(None, c_void_p, c_void_p, c_int)(
            ns_app,
            libobjc.sel_registerName(b"activateIgnoringOtherApps:"),
            1,
        )
    except Exception as exc:
        logging.getLogger(__name__).debug("Could not activate macOS foreground app: %s", exc)


def _configure_windows_app_id() -> None:
    """Use our icon in the taskbar instead of the Python launcher icon."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_USER_MODEL_ID)
    except (AttributeError, OSError) as exc:
        logging.getLogger(__name__).warning("Could not set Windows AppUserModelID: %s", exc)


def _install_macos_dock_icon_guard(app: QApplication) -> None:
    """Undo Qt replacing the bundle Dock icon when windows map or focus changes."""
    clear_macos_dock_icon_override()
    for delay_ms in (0, 100, 500):
        QTimer.singleShot(delay_ms, clear_macos_dock_icon_override)
    app.focusWindowChanged.connect(lambda _window: clear_macos_dock_icon_override())


def run(initial_folder: Path | None = None) -> int:
    configure_runtime_dependencies()
    _configure_windows_app_id()
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName("Karaoke Blast")
    if sys.platform == "darwin":
        clear_macos_dock_icon_override()

    window = MainWindow(initial_folder=initial_folder)
    if sys.platform != "darwin":
        icon = app_icon()
        app.setWindowIcon(icon)
        window.setWindowIcon(icon)
    else:
        _install_macos_dock_icon_guard(app)

    window.show()
    _macos_activate_foreground()
    if sys.platform == "darwin":
        clear_macos_dock_icon_override()
    window.raise_()
    window.activateWindow()
    return app.exec()
