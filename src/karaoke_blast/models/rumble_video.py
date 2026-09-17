"""Rumble video metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RumbleVideo:
    page_url: str
    page_video_id: str
    title: str
    embed_id: str | None = None
    duration_seconds: int | None = None

    @property
    def playback_embed_id(self) -> str:
        if self.embed_id:
            return self.embed_id
        page_id = self.page_video_id
        if page_id and not page_id.startswith("v"):
            return f"v{page_id}"
        return page_id

    @property
    def embed_url(self) -> str:
        return f"https://rumble.com/embed/{self.playback_embed_id}/"
