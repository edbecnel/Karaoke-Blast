"""Formatting helpers for UI display."""

from pathlib import Path


def display_name(path: Path) -> str:
    """Return the file or folder name without its extension."""
    if path.is_dir():
        return path.name
    return path.stem
