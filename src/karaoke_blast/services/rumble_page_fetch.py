"""Fetch Rumble watch pages with browser impersonation and optional cookies."""

from __future__ import annotations

import http.cookiejar
import logging
import time
from pathlib import Path

from karaoke_blast.services.rumble_cookies import resolved_rumble_cookies_file

logger = logging.getLogger(__name__)

_FETCH_ATTEMPTS = 6
_RETRY_DELAY_S = 0.4


def _load_cookie_jar(path: Path) -> http.cookiejar.MozillaCookieJar | None:
    if not path.is_file():
        return None
    jar = http.cookiejar.MozillaCookieJar(str(path))
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except OSError as exc:
        logger.debug("Could not load cookies from %s: %s", path, exc)
        return None
    return jar


def _cookies_for_request(jar: http.cookiejar.MozillaCookieJar | None) -> dict[str, str]:
    if jar is None:
        return {}
    # Send the full Netscape jar; Cloudflare/Rumble often need __cf_bm and session cookies.
    return {cookie.name: cookie.value for cookie in jar}


def _page_looks_like_watch(html: str) -> bool:
    if len(html) < 10_000:
        return False
    lowered = html.lower()
    if "challenges.cloudflare.com" in lowered and "embedurl" not in lowered:
        return False
    return "embedurl" in lowered or "/embed/" in lowered


def _fetch_once(page_url: str, cookies: dict[str, str]) -> str | None:
    try:
        from curl_cffi import requests
    except ImportError:
        return None

    try:
        response = requests.get(
            page_url,
            impersonate="chrome",
            cookies=cookies or None,
            headers={
                "Referer": page_url,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=45,
        )
    except OSError as exc:
        logger.debug("Rumble page fetch failed for %s: %s", page_url, exc)
        return None

    if response.status_code != 200:
        logger.debug(
            "Rumble page fetch HTTP %s for %s", response.status_code, page_url
        )
        return None
    text = response.text
    if not _page_looks_like_watch(text):
        logger.debug("Rumble page fetch got non-watch HTML for %s", page_url)
        return None
    return text


def fetch_rumble_page_html(page_url: str) -> str | None:
    """Return watch-page HTML, retrying through Cloudflare intermittency."""
    path = resolved_rumble_cookies_file()
    jar = _load_cookie_jar(path) if path is not None else None
    cookies = _cookies_for_request(jar)

    for attempt in range(_FETCH_ATTEMPTS):
        html = _fetch_once(page_url, cookies)
        if html is not None:
            return html
        if attempt < _FETCH_ATTEMPTS - 1:
            time.sleep(_RETRY_DELAY_S * (attempt + 1))
    return None
