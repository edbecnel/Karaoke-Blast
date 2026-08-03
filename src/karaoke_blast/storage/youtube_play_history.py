"""Persist recently played YouTube videos."""

import json
import logging
from pathlib import Path

from karaoke_blast.models.youtube_video import YouTubeVideo
from karaoke_blast.storage.paths import config_dir

logger = logging.getLogger(__name__)

MAX_HISTORY = 200


def _history_file() -> Path:
    return config_dir() / "youtube_play_history.json"


def _video_to_dict(video: YouTubeVideo) -> dict:
    return {
        "video_id": video.video_id,
        "title": video.title,
        "channel": video.channel,
        "duration_seconds": video.duration_seconds,
        "thumbnail_url": video.thumbnail_url,
    }


def _video_from_dict(data: dict) -> YouTubeVideo | None:
    video_id = data.get("video_id")
    title = data.get("title")
    channel = data.get("channel")
    if not isinstance(video_id, str) or not isinstance(title, str) or not isinstance(channel, str):
        return None
    duration = data.get("duration_seconds")
    duration_seconds = int(duration) if isinstance(duration, (int, float)) else None
    thumbnail_url = data.get("thumbnail_url")
    return YouTubeVideo(
        video_id=video_id,
        title=title,
        channel=channel,
        duration_seconds=duration_seconds,
        thumbnail_url=thumbnail_url if isinstance(thumbnail_url, str) else None,
    )


class YouTubePlayHistory:
    """Read and write the list of recently played YouTube videos."""

    def __init__(self) -> None:
        self._videos: list[YouTubeVideo] = []
        self.load()

    def load(self) -> None:
        path = _history_file()
        if not path.exists():
            self._videos = []
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw = data.get("videos", [])
            videos: list[YouTubeVideo] = []
            for entry in raw:
                if isinstance(entry, dict):
                    video = _video_from_dict(entry)
                    if video is not None:
                        videos.append(video)
            self._videos = videos
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load YouTube play history: %s", exc)
            self._videos = []

    def save(self) -> None:
        data = {"videos": [_video_to_dict(video) for video in self._videos]}
        try:
            _history_file().write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not save YouTube play history: %s", exc)

    def add(self, video: YouTubeVideo) -> None:
        self._videos = [v for v in self._videos if v.video_id != video.video_id]
        self._videos.insert(0, video)
        self._videos = self._videos[:MAX_HISTORY]
        self.save()

    def remove(self, video_id: str) -> None:
        self._videos = [v for v in self._videos if v.video_id != video_id]
        self.save()

    def clear(self) -> None:
        self._videos.clear()
        self.save()

    def videos(self) -> list[YouTubeVideo]:
        return list(self._videos)
