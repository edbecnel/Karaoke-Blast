"""FIFO queue of YouTube videos to play after the current one."""

from karaoke_blast.models.youtube_video import YouTubeVideo


class YouTubeQueue:
    """Queue of YouTube videos played before returning to idle."""

    def __init__(self) -> None:
        self._items: list[YouTubeVideo] = []

    def enqueue(self, video: YouTubeVideo) -> bool:
        """Add *video* to the queue. Returns False if already queued."""
        if any(item.video_id == video.video_id for item in self._items):
            return False
        self._items.append(video)
        return True

    def dequeue(self) -> YouTubeVideo | None:
        if not self._items:
            return None
        return self._items.pop(0)

    def remove(self, video_id: str) -> None:
        self._items = [item for item in self._items if item.video_id != video_id]

    def clear(self) -> None:
        self._items.clear()

    def items(self) -> list[YouTubeVideo]:
        return list(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def contains(self, video_id: str) -> bool:
        return any(item.video_id == video_id for item in self._items)
