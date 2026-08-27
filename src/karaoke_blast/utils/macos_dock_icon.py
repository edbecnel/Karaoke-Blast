"""Keep the macOS bundle Dock icon by clearing Qt/Python overrides."""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def clear_macos_dock_icon_override() -> bool:
    """Tell NSApplication to use the bundle icon instead of a runtime override."""
    if sys.platform != "darwin":
        return False
    try:
        import ctypes
        from ctypes import c_void_p

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
            return False

        _msg(None, c_void_p, c_void_p, c_void_p)(
            ns_app,
            libobjc.sel_registerName(b"setApplicationIconImage:"),
            None,
        )
        return True
    except Exception as exc:
        logger.debug("Could not clear macOS dock icon override: %s", exc)
        return False
