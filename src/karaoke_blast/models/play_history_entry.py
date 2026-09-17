"""Unified play-history entries for local files and YouTube videos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from karaoke_blast.models.rumble_video import RumbleVideo
from karaoke_blast.models.youtube_video import YouTubeVideo


def _resolve_path(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


@dataclass(frozen=True)
class PlayHistoryEntry:
    kind: Literal["local", "youtube", "rumble"]
    played_at: datetime
    path: Path | None = None
    video: YouTubeVideo | None = None
    rumble: RumbleVideo | None = None

    def key(self) -> str:
        if self.kind == "local" and self.path is not None:
            return f"local:{_resolve_path(self.path)}"
        if self.kind == "youtube" and self.video is not None:
            return f"youtube:{self.video.video_id}"
        if self.kind == "rumble" and self.rumble is not None:
            return f"rumble:{self.rumble.page_url}"
        raise ValueError("Invalid history entry")
