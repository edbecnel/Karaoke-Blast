"""Union type for pasted online video sources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from karaoke_blast.models.rumble_video import RumbleVideo
from karaoke_blast.models.youtube_video import YouTubeVideo


@dataclass(frozen=True)
class OnlineVideo:
    """YouTube or Rumble item from paste URL / queue."""

    source: Literal["youtube", "rumble"]
    youtube: YouTubeVideo | None = None
    rumble: RumbleVideo | None = None

    @staticmethod
    def from_youtube(video: YouTubeVideo) -> OnlineVideo:
        return OnlineVideo(source="youtube", youtube=video)

    @staticmethod
    def from_rumble(video: RumbleVideo) -> OnlineVideo:
        return OnlineVideo(source="rumble", rumble=video)
