"""Mixed play-queue entries for local files and YouTube videos."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from karaoke_blast.models.youtube_video import YouTubeVideo


def _resolve_path(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


@dataclass(frozen=True)
class QueueItem:
    kind: Literal["local", "youtube"]
    path: Path | None = None
    video: YouTubeVideo | None = None

    def key(self) -> str:
        if self.kind == "local" and self.path is not None:
            return f"local:{_resolve_path(self.path)}"
        if self.kind == "youtube" and self.video is not None:
            return f"youtube:{self.video.video_id}"
        raise ValueError("Invalid queue item")


class MixedQueue:
    """FIFO queue of local and YouTube items played before resuming folder order."""

    def __init__(self) -> None:
        self._items: list[QueueItem] = []

    def enqueue(self, item: QueueItem) -> bool:
        key = item.key()
        if any(existing.key() == key for existing in self._items):
            return False
        self._items.append(item)
        return True

    def enqueue_local(self, path: Path) -> bool:
        return self.enqueue(QueueItem(kind="local", path=path))

    def enqueue_youtube(self, video: YouTubeVideo) -> bool:
        return self.enqueue(QueueItem(kind="youtube", video=video))

    def dequeue(self) -> QueueItem | None:
        if not self._items:
            return None
        return self._items.pop(0)

    def remove(self, item: QueueItem) -> None:
        key = item.key()
        self._items = [existing for existing in self._items if existing.key() != key]

    def remove_local(self, path: Path) -> None:
        key = f"local:{_resolve_path(path)}"
        self._items = [item for item in self._items if item.key() != key]

    def remove_youtube(self, video_id: str) -> None:
        key = f"youtube:{video_id}"
        self._items = [item for item in self._items if item.key() != key]

    def clear(self) -> None:
        self._items.clear()

    def set_order(self, items: list[QueueItem]) -> None:
        if len(items) != len(self._items):
            return
        if {item.key() for item in items} != {item.key() for item in self._items}:
            return
        self._items = list(items)

    def items(self) -> list[QueueItem]:
        return list(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def contains(self, item: QueueItem) -> bool:
        key = item.key()
        return any(existing.key() == key for existing in self._items)

    def contains_local(self, path: Path) -> bool:
        key = f"local:{_resolve_path(path)}"
        return any(item.key() == key for item in self._items)

    def contains_youtube(self, video_id: str) -> bool:
        key = f"youtube:{video_id}"
        return any(item.key() == key for item in self._items)
