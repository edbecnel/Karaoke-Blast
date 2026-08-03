"""Parse YouTube video IDs from URLs and raw input."""

import re
from urllib.parse import parse_qs, urlparse

_VIDEO_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


def extract_video_id(text: str) -> str | None:
    """Return an 11-character YouTube video ID from a URL or raw ID."""
    value = text.strip()
    if not value:
        return None
    if _VIDEO_ID_RE.fullmatch(value):
        return value

    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.netloc or "").lower().removeprefix("www.")
    path = parsed.path or ""

    if host in {"youtu.be", "youtube.com", "m.youtube.com", "music.youtube.com"}:
        if host == "youtu.be" and path.strip("/"):
            candidate = path.strip("/").split("/")[0]
            if _VIDEO_ID_RE.fullmatch(candidate):
                return candidate
        if path.startswith("/embed/"):
            candidate = path.split("/")[2] if len(path.split("/")) > 2 else ""
            if _VIDEO_ID_RE.fullmatch(candidate):
                return candidate
        if path.startswith("/shorts/"):
            candidate = path.split("/")[2] if len(path.split("/")) > 2 else ""
            if _VIDEO_ID_RE.fullmatch(candidate):
                return candidate
        query = parse_qs(parsed.query)
        for key in ("v", "vi"):
            values = query.get(key)
            if values and _VIDEO_ID_RE.fullmatch(values[0]):
                return values[0]

    return None
