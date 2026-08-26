"""Apply filename-format casing to slot input fields."""

from __future__ import annotations

from PyQt6.QtWidgets import QLineEdit

from karaoke_blast.utils.filename_rename import FilenameFormat, apply_slot_casing


def cased_slot_text(text: str, kind: str, fmt: FilenameFormat) -> str:
    """Return *text* with the configured casing for *kind*."""
    stripped = text.strip()
    if not stripped:
        return ""
    return apply_slot_casing(stripped, kind, fmt)


def apply_casing_to_field(field: QLineEdit, kind: str, fmt: FilenameFormat) -> bool:
    """Normalize a slot field to configured casing. Returns True if text changed."""
    text = field.text()
    leading_len = len(text) - len(text.lstrip(" "))
    trailing_len = len(text) - len(text.rstrip(" "))
    core = text.strip()
    if not core:
        return False

    cased_core = apply_slot_casing(core, kind, fmt)
    cased = (" " * leading_len) + cased_core + (" " * trailing_len)
    if text == cased:
        return False

    cursor = field.cursorPosition()
    was_at_end = cursor >= len(text)
    field.blockSignals(True)
    field.setText(cased)
    if was_at_end:
        field.setCursorPosition(len(cased))
    else:
        field.setCursorPosition(min(cursor, len(cased)))
    field.blockSignals(False)
    return True
