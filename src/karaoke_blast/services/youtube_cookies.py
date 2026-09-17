"""Optional browser cookies for yt-dlp YouTube requests."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from karaoke_blast.storage.paths import config_dir, default_youtube_cookies_file

logger = logging.getLogger(__name__)


def youtube_cookies_setup_page() -> Path:
    """HTML helper (bookmarklet + export instructions) in the repo tools folder."""
    return Path(__file__).resolve().parents[3] / "tools" / "youtube-cookies-setup.html"


def resolved_youtube_cookies_file() -> Path | None:
    """Return cookies.txt when present and non-empty."""
    path = default_youtube_cookies_file()
    try:
        if path.is_file() and path.stat().st_size > 0:
            return path
    except OSError as exc:
        logger.debug("Could not read YouTube cookies file %s: %s", path, exc)
    return None


def apply_youtube_cookies_opts(opts: dict[str, Any]) -> None:
    path = resolved_youtube_cookies_file()
    if path is not None:
        opts["cookiefile"] = str(path)
        logger.debug("Using YouTube cookies from %s", path)


def cookies_folder() -> Path:
    return config_dir()
