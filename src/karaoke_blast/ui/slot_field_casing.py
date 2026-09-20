"""Apply filename-format casing to slot input fields."""

from __future__ import annotations

from PyQt6.QtWidgets import QLineEdit

from karaoke_blast.utils.filename_rename import FilenameFormat, apply_slot_casing


def cased_slot_text(text: str, slot_index: int, fmt: FilenameFormat) -> str:
    """Return *text* with the configured casing for *slot_index*."""
    stripped = text.strip()
    if not stripped:
        return ""
    return apply_slot_casing(stripped, slot_index, fmt)


def apply_casing_to_field(field: QLineEdit, slot_index: int, fmt: FilenameFormat) -> bool:
    """Normalize a slot field to configured casing. Returns True if text changed."""
    core = field.text()
    if not core.strip():
        return False
    cased_core = apply_slot_casing(core, slot_index, fmt)
    if cased_core == core:
        return False
    field.setText(cased_core)
    return True
