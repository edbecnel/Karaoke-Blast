"""Prevent display sleep and system idle sleep during playback."""

from __future__ import annotations

import logging
import sys
from ctypes import POINTER, byref, c_char_p, c_int, c_uint32, c_void_p

logger = logging.getLogger(__name__)

_REASON = "Karaoke Blast playback"
_MAC_ASSERTION_TYPES = (
    "PreventUserIdleDisplaySleep",
    "PreventUserIdleSystemSleep",
)

# Windows SetThreadExecutionState flags.
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002
_ES_INHIBIT = _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED


class SleepInhibitor:
    """Keep the display and system awake while playback is active."""

    def __init__(self) -> None:
        self._active = False
        self._mac_assertion_ids: list[int] = []

    @property
    def active(self) -> bool:
        return self._active

    def set_active(self, active: bool) -> None:
        if active == self._active:
            return
        if active:
            self._acquire()
        else:
            self._release()
        self._active = active

    def _acquire(self) -> None:
        if sys.platform == "darwin":
            self._mac_acquire()
        elif sys.platform == "win32":
            self._win32_acquire()

    def _release(self) -> None:
        if sys.platform == "darwin":
            self._mac_release()
        elif sys.platform == "win32":
            self._win32_release()

    def _mac_acquire(self) -> None:
        if self._mac_assertion_ids:
            return
        for assertion_type in _MAC_ASSERTION_TYPES:
            assertion_id = _macos_create_assertion(assertion_type, _REASON)
            if assertion_id is not None:
                self._mac_assertion_ids.append(assertion_id)

    def _mac_release(self) -> None:
        for assertion_id in self._mac_assertion_ids:
            _macos_release_assertion(assertion_id)
        self._mac_assertion_ids.clear()

    def _win32_acquire(self) -> None:
        try:
            import ctypes

            ctypes.windll.kernel32.SetThreadExecutionState(_ES_INHIBIT)
        except OSError as exc:
            logger.debug("Windows sleep inhibition failed: %s", exc)

    def _win32_release(self) -> None:
        try:
            import ctypes

            ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
        except OSError as exc:
            logger.debug("Windows sleep inhibition release failed: %s", exc)


def _macos_create_assertion(assertion_type: str, reason: str) -> int | None:
    try:
        import ctypes

        cf = ctypes.CDLL(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
        )
        iokit = ctypes.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")

        cf.CFStringCreateWithCString.argtypes = [c_void_p, c_char_p, c_uint32]
        cf.CFStringCreateWithCString.restype = c_void_p
        cf.CFRelease.argtypes = [c_void_p]

        iokit.IOPMAssertionCreateWithName.argtypes = [
            c_void_p,
            c_uint32,
            c_void_p,
            POINTER(c_uint32),
        ]
        iokit.IOPMAssertionCreateWithName.restype = c_int
        iokit.IOPMAssertionRelease.argtypes = [c_uint32]
        iokit.IOPMAssertionRelease.restype = c_int

        type_ref = cf.CFStringCreateWithCString(
            None, assertion_type.encode("utf-8"), 0x08000100
        )
        reason_ref = cf.CFStringCreateWithCString(
            None, reason.encode("utf-8"), 0x08000100
        )
        assertion_id = c_uint32(0)
        try:
            err = iokit.IOPMAssertionCreateWithName(
                type_ref,
                255,  # kIOPMAssertionLevelOn
                reason_ref,
                byref(assertion_id),
            )
            if err != 0:
                logger.debug(
                    "IOPMAssertionCreateWithName(%s) failed: %s",
                    assertion_type,
                    err,
                )
                return None
            return int(assertion_id.value)
        finally:
            cf.CFRelease(type_ref)
            cf.CFRelease(reason_ref)
    except OSError as exc:
        logger.debug("macOS sleep assertion create failed: %s", exc)
        return None


def _macos_release_assertion(assertion_id: int) -> None:
    try:
        import ctypes

        iokit = ctypes.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
        iokit.IOPMAssertionRelease.argtypes = [c_uint32]
        iokit.IOPMAssertionRelease.restype = c_int
        iokit.IOPMAssertionRelease(assertion_id)
    except OSError as exc:
        logger.debug("macOS sleep assertion release failed: %s", exc)
