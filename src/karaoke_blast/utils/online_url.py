"""Parse pasted YouTube or Rumble URLs."""

from __future__ import annotations

from karaoke_blast.models.online_video import OnlineVideo
from karaoke_blast.models.rumble_video import RumbleVideo
from karaoke_blast.models.youtube_video import YouTubeVideo
from karaoke_blast.utils.rumble_url import parse_rumble_url
from karaoke_blast.utils.youtube_url import extract_video_id


def parse_pasted_online_url(text: str) -> OnlineVideo | None:
    video_id = extract_video_id(text)
    if video_id is not None:
        label = text.strip() or video_id
        return OnlineVideo.from_youtube(
            YouTubeVideo(video_id=video_id, title=label, channel="YouTube")
        )
    rumble = parse_rumble_url(text)
    if rumble is not None:
        label = text.strip() or rumble.page_video_id
        return OnlineVideo.from_rumble(
            RumbleVideo(
                page_url=rumble.page_url,
                page_video_id=rumble.page_video_id,
                title=label,
                embed_id=rumble.embed_id,
            )
        )
    return None
