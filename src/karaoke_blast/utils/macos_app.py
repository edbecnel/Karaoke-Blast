"""macOS application activation helpers."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from ctypes import c_int, c_void_p

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication, QWidget

logger = logging.getLogger(__name__)


def activate_foreground() -> None:
    """Bring the app to the foreground above other windows."""
    if sys.platform != "darwin":
        return
    try:
        import ctypes

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
        logger.debug("Could not activate macOS foreground app: %s", exc)


def order_native_window_front(widget: QWidget) -> None:
    """Raise a widget's native window on macOS."""
    if sys.platform != "darwin":
        return
    try:
        import ctypes

        view = c_void_p(int(widget.winId()))
        if not view.value:
            return

        libobjc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
        libobjc.objc_getClass.restype = c_void_p
        libobjc.sel_registerName.restype = c_void_p

        def _msg(restype, *argtypes):
            func = libobjc.objc_msgSend
            func.restype = restype
            func.argtypes = argtypes
            return func

        window = _msg(c_void_p, c_void_p, c_void_p)(
            view,
            libobjc.sel_registerName(b"window"),
        )
        if not window:
            return

        _msg(None, c_void_p, c_void_p)(
            window,
            libobjc.sel_registerName(b"orderFrontRegardless"),
        )
        _msg(None, c_void_p, c_void_p, c_void_p)(
            window,
            libobjc.sel_registerName(b"makeKeyAndOrderFront:"),
            None,
        )
    except Exception as exc:
        logger.debug("Could not order native window front: %s", exc)


def bring_widgets_forward(*widgets: QWidget | None) -> None:
    """Raise widgets and request application focus."""
    activate_foreground()
    for widget in widgets:
        if widget is None:
            continue
        widget.show()
        widget.raise_()
        widget.activateWindow()
        handle = widget.windowHandle()
        if handle is not None:
            handle.requestActivate()
        order_native_window_front(widget)

    app = QApplication.instance()
    if app is not None:
        app.processEvents()


def wait_until(
    predicate: Callable[[], bool],
    *,
    timeout_ms: int = 500,
    interval_ms: int = 16,
) -> bool:
    """Process events until *predicate* is true or *timeout_ms* elapses."""
    if predicate():
        return True

    app = QApplication.instance()
    loop = QEventLoop()
    elapsed = 0
    timer = QTimer()
    timer.setInterval(interval_ms)

    def tick() -> None:
        nonlocal elapsed
        if app is not None:
            app.processEvents()
        if predicate():
            timer.stop()
            loop.quit()
            return
        elapsed += interval_ms
        if elapsed >= timeout_ms:
            timer.stop()
            loop.quit()

    timer.timeout.connect(tick)
    timer.start()
    loop.exec()
    return predicate()
