"""YouTube video metadata."""

from dataclasses import dataclass


@dataclass(frozen=True)
class YouTubeVideo:
    video_id: str
    title: str
    channel: str
    duration_seconds: int | None = None
    thumbnail_url: str | None = None

    @property
    def watch_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"
