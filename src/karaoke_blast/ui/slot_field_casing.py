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
    cased = cased_slot_text(field.text(), kind, fmt)
    if field.text() == cased:
        return False
    cursor = field.cursorPosition()
    field.blockSignals(True)
    field.setText(cased)
    field.setCursorPosition(min(cursor, len(cased)))
    field.blockSignals(False)
    return True
