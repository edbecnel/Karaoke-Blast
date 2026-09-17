"""Parse YouTube video IDs from URLs and raw input."""

import re
from urllib.parse import parse_qs, unquote, urlparse

_VIDEO_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
_EMBEDDED_ID_RE = re.compile(
    r"(?:youtube\.com/watch\?[^#\s]*[&;]v=|youtu\.be/|/embed/|/shorts/|/live/|/v/)"
    r"([a-zA-Z0-9_-]{11})"
)
_PATH_ID_PREFIXES = ("/embed/", "/shorts/", "/live/", "/v/")


def _normalize_input(text: str) -> str:
    value = text.strip().strip("\ufeff")
    if not value:
        return value
    # Markdown links: [title](https://youtu.be/…)
    markdown = re.match(r"\[[^\]]*\]\(([^)]+)\)", value)
    if markdown:
        value = markdown.group(1).strip()
    if value.startswith("<") and value.endswith(">") and "://" in value:
        value = value[1:-1].strip()
    return unquote(value)


def _is_youtube_host(host: str) -> bool:
    host = host.lower().removeprefix("www.")
    if host in {"youtu.be", "m.youtube.com", "music.youtube.com"}:
        return True
    if host in {"youtube.com", "youtube-nocookie.com"}:
        return True
    return host.endswith(".youtube.com") or host.endswith(".youtube-nocookie.com")


def _id_from_path(path: str) -> str | None:
    if path.startswith("/watch/") and len(path) > len("/watch/"):
        candidate = path[len("/watch/") :].split("/")[0].split("?")[0]
        if _VIDEO_ID_RE.fullmatch(candidate):
            return candidate
    for prefix in _PATH_ID_PREFIXES:
        if path.startswith(prefix):
            rest = path[len(prefix) :].strip("/")
            candidate = rest.split("/")[0].split("?")[0]
            if _VIDEO_ID_RE.fullmatch(candidate):
                return candidate
    return None


def extract_video_id(text: str) -> str | None:
    """Return an 11-character YouTube video ID from a URL or raw ID."""
    value = _normalize_input(text)
    if not value:
        return None
    if _VIDEO_ID_RE.fullmatch(value):
        return value

    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.netloc or "").lower()
    path = parsed.path or ""

    if _is_youtube_host(host):
        if host.removeprefix("www.") == "youtu.be" and path.strip("/"):
            candidate = path.strip("/").split("/")[0].split("?")[0]
            if _VIDEO_ID_RE.fullmatch(candidate):
                return candidate
        from_path = _id_from_path(path)
        if from_path is not None:
            return from_path
        query = parse_qs(parsed.query)
        for key in ("v", "vi"):
            values = query.get(key)
            if values and _VIDEO_ID_RE.fullmatch(values[0]):
                return values[0]

    match = _EMBEDDED_ID_RE.search(value)
    if match:
        return match.group(1)
    loose = re.search(r"(?:^|[?&;])v=([a-zA-Z0-9_-]{11})", value)
    if loose:
        return loose.group(1)

    return None
