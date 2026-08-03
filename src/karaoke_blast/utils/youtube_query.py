"""Build karaoke-oriented YouTube search queries."""


def build_karaoke_query(song: str, artist: str | None = None) -> str:
    """Combine song and artist, appending 'karaoke' when not already present."""
    parts = [part.strip() for part in (song, artist) if part and part.strip()]
    query = " ".join(parts)
    if not query:
        return ""
    if "karaoke" not in query.lower():
        query = f"{query} karaoke"
    return query
