"""Resolve Rumble embed ids and titles via yt-dlp."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import time

from karaoke_blast.models.rumble_video import RumbleVideo
from karaoke_blast.services.rumble_download_worker import build_rumble_ydl_opts
from karaoke_blast.services.rumble_page_fetch import fetch_rumble_page_html
from karaoke_blast.utils.runtime_deps import (
    configure_runtime_dependencies,
    resolve_yt_dlp_binary,
    subprocess_path_env,
)

logger = logging.getLogger(__name__)

_YTDLP_ATTEMPTS = 6
_YTDLP_RETRY_DELAY_S = 0.45

_EMBED_IN_HTML_RE = re.compile(r"/embed/([a-zA-Z0-9]+)")
_EMBED_URL_JSON_RE = re.compile(
    r'"embedUrl"\s*:\s*"https://rumble\.com/embed/([a-zA-Z0-9]+)',
    re.IGNORECASE,
)


def _embed_id_from_info_dict(info: dict) -> str | None:
    for key in ("url", "webpage_url", "original_url", "embed_url"):
        value = info.get(key)
        if isinstance(value, str):
            match = _EMBED_IN_HTML_RE.search(value)
            if match:
                return match.group(1)
    video_id = info.get("id")
    if isinstance(video_id, str) and video_id.strip():
        return video_id.strip()
    return None


def _embed_id_via_ytdlp(page_url: str) -> str | None:
    """Use yt-dlp with cookies; process=False stops before embedJS (avoids extra 403s)."""
    configure_runtime_dependencies()
    try:
        import yt_dlp
    except ImportError:
        return None

    opts = build_rumble_ydl_opts(page_url, download=False)
    last_error: Exception | None = None
    for attempt in range(_YTDLP_ATTEMPTS):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(page_url, download=False, process=False)
            if isinstance(info, dict):
                embed_id = _embed_id_from_info_dict(info)
                if embed_id:
                    return embed_id
        except Exception as exc:
            last_error = exc
            logger.debug(
                "Rumble yt-dlp embed lookup attempt %s failed for %s: %s",
                attempt + 1,
                page_url,
                exc,
            )
        if attempt < _YTDLP_ATTEMPTS - 1:
            time.sleep(_YTDLP_RETRY_DELAY_S * (attempt + 1))
    if last_error is not None:
        logger.debug("Rumble yt-dlp embed lookup gave up for %s", page_url)
    return None


def _embed_id_via_ytdlp_cli(page_url: str) -> str | None:
    """Fallback to a system yt-dlp binary (often Homebrew) when the library path fails."""
    binary = resolve_yt_dlp_binary()
    if binary is None:
        return None

    cmd = [
        binary,
        "--no-warnings",
        "--no-playlist",
        "-j",
        "--skip-download",
        "--impersonate",
        "chrome",
        page_url,
    ]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=subprocess_path_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("Rumble yt-dlp CLI failed for %s: %s", page_url, exc)
        return None
    if completed.returncode != 0:
        logger.debug(
            "Rumble yt-dlp CLI exit %s for %s: %s",
            completed.returncode,
            page_url,
            (completed.stderr or completed.stdout or "")[:300],
        )
        return None
    try:
        info = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(info, dict):
        return None
    return _embed_id_from_info_dict(info)


def resolve_rumble_embed_id(page_url: str) -> str | None:
    """Return embed id for playback, or None if extraction fails."""
    # HTML + curl_cffi avoids yt-dlp 403s from stale exported cookies on watch pages.
    embed = _embed_id_from_html_fetch(page_url)
    if embed is not None:
        return embed
    embed = _embed_id_via_ytdlp_cli(page_url)
    if embed is not None:
        return embed
    return _embed_id_via_ytdlp(page_url)


def _embed_id_from_html(html: str) -> str | None:
    match = _EMBED_URL_JSON_RE.search(html)
    if match:
        return match.group(1)
    matches = list(dict.fromkeys(_EMBED_IN_HTML_RE.findall(html)))
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    return matches[-1]


def _embed_id_from_html_fetch(page_url: str) -> str | None:
    html = fetch_rumble_page_html(page_url)
    if html is None:
        return None
    return _embed_id_from_html(html[:800_000])


def _title_from_html(html: str) -> str | None:
    match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    if not match:
        return None
    title = match.group(1).strip()
    if title.endswith(" - Rumble"):
        title = title[: -len(" - Rumble")].strip()
    return title or None


def _fetch_title(page_url: str) -> str | None:
    binary = resolve_yt_dlp_binary()
    if binary is None:
        return None
    cmd = [
        binary,
        "--no-warnings",
        "--no-playlist",
        "-j",
        "--skip-download",
        "--impersonate",
        "chrome",
        page_url,
    ]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=subprocess_path_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        info = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    if isinstance(info, dict):
        title = info.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    return None


def enrich_rumble_video(video: RumbleVideo) -> RumbleVideo:
    """Fill embed_id and title when missing."""
    embed_id = video.embed_id
    title = video.title
    if embed_id is None:
        embed_id = resolve_rumble_embed_id(video.page_url)
    if embed_id is None:
        logger.warning(
            "Rumble embed id not resolved for %s; will try watch-page playback",
            video.page_url,
        )
    if title in ("", video.page_url, video.page_video_id):
        title = _fetch_title(video.page_url) or title
    if title in ("", video.page_url, video.page_video_id):
        html = fetch_rumble_page_html(video.page_url)
        if html is not None:
            title = _title_from_html(html) or title
    return RumbleVideo(
        page_url=video.page_url,
        page_video_id=video.page_video_id,
        title=title,
        embed_id=embed_id,
        duration_seconds=video.duration_seconds,
    )
