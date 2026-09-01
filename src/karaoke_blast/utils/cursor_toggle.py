"""Manually show or hide the mouse cursor (M-key toggle)."""

from __future__ import annotations

import logging
import sys
from ctypes import c_int, c_uint32, c_ulonglong, c_void_p

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

_blank_cursor: QCursor | None = None


def _blank_qt_cursor() -> QCursor:
    global _blank_cursor
    if _blank_cursor is None:
        _blank_cursor = QCursor(Qt.CursorShape.BlankCursor)
    return _blank_cursor


class ManualCursorToggle:
    """Toggle cursor visibility on demand without auto-hide or app-wide Qt overrides."""

    def __init__(self) -> None:
        self._widgets: tuple[QWidget, ...] = ()
        self._hidden = False

    def set_widgets(self, widgets: tuple[QWidget, ...]) -> None:
        self._widgets = widgets
        if self._hidden:
            self._apply_hidden_cursors()

    @property
    def hidden(self) -> bool:
        return self._hidden

    def toggle(self) -> bool:
        if self._hidden:
            self.show()
        else:
            self.hide()
        return self._hidden

    def hide(self) -> None:
        if self._hidden:
            return
        if _platform_hide_cursor():
            self._hidden = True
            return
        self._apply_hidden_cursors()
        self._hidden = True

    def show(self) -> None:
        if not self._hidden:
            return
        _platform_show_cursor()
        for widget in self._widgets:
            widget.unsetCursor()
        self._hidden = False

    def _apply_hidden_cursors(self) -> None:
        cursor = _blank_qt_cursor()
        for widget in self._widgets:
            widget.setCursor(cursor)


def _platform_hide_cursor() -> bool:
    if sys.platform == "darwin":
        return _macos_hide_cursor()
    if sys.platform == "win32":
        return _win32_hide_cursor()
    return False


def _platform_show_cursor() -> None:
    if sys.platform == "darwin":
        _macos_show_cursor()
    elif sys.platform == "win32":
        _win32_show_cursor()


def _macos_hide_cursor() -> bool:
    try:
        import ctypes

        cg = ctypes.CDLL(
            "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
        )
        cg.CGMainDisplayID.restype = c_uint32
        cg.CGDisplayHideCursor.argtypes = [c_uint32]
        cg.CGDisplayHideCursor.restype = c_int
        return cg.CGDisplayHideCursor(cg.CGMainDisplayID()) == 0
    except Exception as exc:
        logger.debug("macOS cursor hide failed: %s", exc)
        return False


def _macos_show_cursor() -> None:
    try:
        import ctypes

        cg = ctypes.CDLL(
            "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
        )
        cg.CGMainDisplayID.restype = c_uint32
        cg.CGDisplayShowCursor.argtypes = [c_uint32]
        cg.CGDisplayShowCursor.restype = c_int
        cg.CGDisplayShowCursor(cg.CGMainDisplayID())
    except Exception as exc:
        logger.debug("macOS cursor show failed: %s", exc)


def _win32_hide_cursor() -> bool:
    try:
        import ctypes

        return ctypes.windll.user32.ShowCursor(False) >= 0
    except Exception as exc:
        logger.debug("Windows cursor hide failed: %s", exc)
        return False


def _win32_show_cursor() -> None:
    try:
        import ctypes

        ctypes.windll.user32.ShowCursor(True)
    except Exception as exc:
        logger.debug("Windows cursor show failed: %s", exc)


def primary_mouse_buttons_pressed() -> bool:
    """Return True when the left or right mouse button is currently held down."""
    if sys.platform == "darwin":
        return _macos_primary_mouse_buttons_pressed()
    if sys.platform == "win32":
        return _win32_primary_mouse_buttons_pressed()
    return False


def _macos_primary_mouse_buttons_pressed() -> bool:
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

        nsevent = libobjc.objc_getClass(b"NSEvent")
        if not nsevent:
            return False
        mask = _msg(c_ulonglong, c_void_p, c_void_p)(
            nsevent,
            libobjc.sel_registerName(b"pressedMouseButtons"),
        )
        # Left = 1, right = 2.
        return bool(mask & 0x3)
    except Exception as exc:
        logger.debug("macOS mouse button query failed: %s", exc)
        return False


def _win32_primary_mouse_buttons_pressed() -> bool:
    try:
        import ctypes

        user32 = ctypes.windll.user32
        left = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
        right = bool(user32.GetAsyncKeyState(0x02) & 0x8000)
        return left or right
    except Exception as exc:
        logger.debug("Windows mouse button query failed: %s", exc)
        return False
