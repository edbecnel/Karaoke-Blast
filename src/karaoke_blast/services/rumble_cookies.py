"""Optional browser cookies for Rumble page fetch and embedded player."""

from __future__ import annotations

import logging
from pathlib import Path

from karaoke_blast.storage.paths import default_rumble_cookies_file

logger = logging.getLogger(__name__)


def resolved_rumble_cookies_file() -> Path | None:
    """Return rumble_cookies.txt when present and non-empty."""
    path = default_rumble_cookies_file()
    try:
        if path.is_file() and path.stat().st_size > 0:
            return path
    except OSError as exc:
        logger.debug("Could not read Rumble cookies file %s: %s", path, exc)
    return None
