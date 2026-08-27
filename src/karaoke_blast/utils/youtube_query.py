"""Build YouTube search queries with optional append terms."""

from __future__ import annotations

_APPEND_LABEL_KARAOKE = "karaoke"


def build_youtube_search_query(
    song: str,
    artist: str | None = None,
    *,
    append_term: str | None = None,
    append_enabled: bool = True,
) -> str:
    """Combine song and artist, optionally appending *append_term* when not already present."""
    parts = [part.strip() for part in (song, artist) if part and part.strip()]
    query = " ".join(parts)
    if not query:
        return ""
    if (
        append_enabled
        and append_term
        and append_term.lower() not in query.lower()
    ):
        query = f"{query} {append_term}"
    return query


def build_karaoke_query(
    song: str,
    artist: str | None = None,
    *,
    append_karaoke: bool = True,
) -> str:
    """Backward-compatible wrapper around :func:`build_youtube_search_query`."""
    return build_youtube_search_query(
        song,
        artist,
        append_term=_APPEND_LABEL_KARAOKE if append_karaoke else None,
        append_enabled=append_karaoke,
    )
