"""Parse Rumble video URLs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

_EMBED_ID_RE = re.compile(r"^[a-zA-Z0-9]+$")
# Watch URLs are /v{id}-slug.html where {id} includes the leading "v" (e.g. vs6jry, v1euzw6).
_PAGE_PATH_RE = re.compile(r"^/(v[a-zA-Z0-9]+)(?:-[^/]*)?\.html$", re.IGNORECASE)


@dataclass(frozen=True)
class RumbleUrlInfo:
    """Parsed Rumble link."""

    page_url: str
    page_video_id: str
    embed_id: str | None = None

    @property
    def playback_embed_id(self) -> str:
        return self.embed_id or self.page_video_id


def _normalize_input(text: str) -> str:
    return text.strip().strip("\ufeff")


def _is_rumble_host(host: str) -> bool:
    host = host.lower().removeprefix("www.")
    return host == "rumble.com"


def parse_rumble_url(text: str) -> RumbleUrlInfo | None:
    """Return page URL and ids from a Rumble watch or embed URL."""
    value = _normalize_input(text)
    if not value:
        return None

    parsed = urlparse(value if "://" in value else f"https://{value}")
    if not _is_rumble_host(parsed.netloc or ""):
        return None

    path = parsed.path or ""
    if path.startswith("/embed/"):
        rest = path[len("/embed/") :].strip("/").split("/")[0]
        if _EMBED_ID_RE.fullmatch(rest):
            page_url = f"https://rumble.com/embed/{rest}"
            return RumbleUrlInfo(
                page_url=page_url,
                page_video_id=rest,
                embed_id=rest,
            )
        return None

    match = _PAGE_PATH_RE.match(path)
    if not match:
        return None

    page_id = match.group(1)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or "rumble.com"
    page_url = f"{scheme}://{netloc}{path}"
    if parsed.query:
        page_url = f"{page_url}?{parsed.query}"
    return RumbleUrlInfo(page_url=page_url, page_video_id=page_id, embed_id=None)


def rumble_embed_url(embed_id: str) -> str:
    """Canonical embed URL used by yt-dlp (avoids Cloudflare on watch pages)."""
    return f"https://rumble.com/embed/{embed_id.strip()}/"
