"""Helpers for persisted path lists."""

from __future__ import annotations

import tempfile
from pathlib import Path


def is_transient_path(path: Path) -> bool:
    """Return True for paths under the system temp directory (e.g. crash-test leftovers)."""
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    try:
        temp_root = Path(tempfile.gettempdir()).resolve()
    except OSError:
        return False
    if resolved == temp_root:
        return True
    return temp_root in resolved.parents
