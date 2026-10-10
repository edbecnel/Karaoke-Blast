"""Detect whether the cursor is over this app's topmost application window."""

from __future__ import annotations

import logging
import os
import sys

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

# macOS Dock / menu bar sit above normal application windows (layer 0).
_MACOS_MAX_APPLICATION_WINDOW_LAYER = 19


def cursor_over_topmost_application_window(widget: QWidget) -> bool:
    """True when the frontmost normal window under the cursor belongs to this process."""
    global_pos = QCursor.pos()
    if not widget.isVisible():
        return False
    if sys.platform == "darwin":
        return _macos_cursor_over_topmost_application_window(global_pos)
    if sys.platform == "win32":
        return _win32_cursor_over_topmost_application_window(global_pos)
    return widget.isActiveWindow()


def _macos_cursor_over_topmost_application_window(global_pos: QPoint) -> bool:
    try:
        import ctypes
        from ctypes import POINTER, Structure, byref, c_bool, c_double, c_int, c_long, c_uint32, c_void_p

        cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

        class CGPoint(Structure):
            _fields_ = [("x", c_double), ("y", c_double)]

        class CGSize(Structure):
            _fields_ = [("width", c_double), ("height", c_double)]

        class CGRect(Structure):
            _fields_ = [("origin", CGPoint), ("size", CGSize)]

        cg.CGWindowListCopyWindowInfo.argtypes = [c_uint32, c_uint32]
        cg.CGWindowListCopyWindowInfo.restype = c_void_p
        cg.CGRectMakeWithDictionaryRepresentation.argtypes = [c_void_p, POINTER(CGRect)]
        cg.CGRectMakeWithDictionaryRepresentation.restype = c_bool

        cf.CFArrayGetCount.argtypes = [c_void_p]
        cf.CFArrayGetCount.restype = c_long
        cf.CFArrayGetValueAtIndex.argtypes = [c_void_p, c_long]
        cf.CFArrayGetValueAtIndex.restype = c_void_p
        cf.CFDictionaryGetValue.argtypes = [c_void_p, c_void_p]
        cf.CFDictionaryGetValue.restype = c_void_p
        cf.CFNumberGetValue.argtypes = [c_void_p, c_int, c_void_p]
        cf.CFNumberGetValue.restype = c_bool
        cf.CFRelease.argtypes = [c_void_p]

        k_num = ctypes.c_void_p.in_dll(cg, "kCGWindowNumber")
        k_layer = ctypes.c_void_p.in_dll(cg, "kCGWindowLayer")
        k_bounds = ctypes.c_void_p.in_dll(cg, "kCGWindowBounds")
        k_alpha = ctypes.c_void_p.in_dll(cg, "kCGWindowAlpha")
        k_owner_pid = ctypes.c_void_p.in_dll(cg, "kCGWindowOwnerPID")

        k_on_screen_only = 1 << 0
        k_exclude_desktop = 1 << 4

        windows = cg.CGWindowListCopyWindowInfo(k_on_screen_only | k_exclude_desktop, 0)
        if not windows:
            return False

        x = float(global_pos.x())
        y = float(global_pos.y())
        our_pid = os.getpid()

        def _cf_number(value: c_void_p) -> int | None:
            if not value:
                return None
            out = ctypes.c_longlong()
            if not cf.CFNumberGetValue(value, 4, byref(out)):
                return None
            return int(out.value)

        def _cf_double(value: c_void_p) -> float:
            if not value:
                return 1.0
            out = c_double()
            if not cf.CFNumberGetValue(value, 13, byref(out)):
                return 1.0
            return float(out.value)

        try:
            count = cf.CFArrayGetCount(windows)
            for index in range(count):
                info = cf.CFArrayGetValueAtIndex(windows, index)
                layer = _cf_number(cf.CFDictionaryGetValue(info, k_layer))
                if layer is None or layer < 0 or layer > _MACOS_MAX_APPLICATION_WINDOW_LAYER:
                    continue
                if _cf_double(cf.CFDictionaryGetValue(info, k_alpha)) <= 0.01:
                    continue
                rect = CGRect()
                bounds = cf.CFDictionaryGetValue(info, k_bounds)
                if not bounds or not cg.CGRectMakeWithDictionaryRepresentation(bounds, byref(rect)):
                    continue
                left = rect.origin.x
                top = rect.origin.y
                right = left + rect.size.width
                bottom = top + rect.size.height
                if not (left <= x < right and top <= y < bottom):
                    continue
                owner_pid = _cf_number(cf.CFDictionaryGetValue(info, k_owner_pid))
                return owner_pid == our_pid
        finally:
            cf.CFRelease(windows)
    except Exception as exc:
        logger.debug("macOS topmost window query failed: %s", exc)
    return False


def _win32_cursor_over_topmost_application_window(global_pos: QPoint) -> bool:
    try:
        import ctypes
        from ctypes import wintypes

        class POINT(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

        user32 = ctypes.windll.user32
        pt = POINT(global_pos.x(), global_pos.y())
        hwnd = user32.WindowFromPoint(pt)
        if not hwnd:
            return False
        root = user32.GetAncestor(hwnd, 2)  # GA_ROOT
        if not root:
            root = hwnd
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(root, ctypes.byref(pid))
        return int(pid.value) == os.getpid()
    except Exception as exc:
        logger.debug("Windows topmost window query failed: %s", exc)
        return False
