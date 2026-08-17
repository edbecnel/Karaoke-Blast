"""Persist unified local and YouTube play history."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from karaoke_blast.models.play_history_entry import PlayHistoryEntry
from karaoke_blast.models.youtube_video import YouTubeVideo
from karaoke_blast.storage.local_play_history import LocalPlayHistory
from karaoke_blast.storage.paths import config_dir
from karaoke_blast.storage.youtube_play_history import (
    YouTubePlayHistory,
    _video_from_dict,
    _video_to_dict,
)

logger = logging.getLogger(__name__)

MAX_HISTORY = 200


def _history_file() -> Path:
    return config_dir() / "play_history.json"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_played_at(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _entry_to_dict(entry: PlayHistoryEntry) -> dict:
    data: dict[str, object] = {
        "kind": entry.kind,
        "played_at": entry.played_at.astimezone(timezone.utc).isoformat(),
    }
    if entry.kind == "local" and entry.path is not None:
        data["path"] = str(entry.path)
    elif entry.kind == "youtube" and entry.video is not None:
        data["video"] = _video_to_dict(entry.video)
    return data


def _entry_from_dict(data: dict) -> PlayHistoryEntry | None:
    kind = data.get("kind")
    played_at = _parse_played_at(data.get("played_at"))
    if kind not in ("local", "youtube") or played_at is None:
        return None
    if kind == "local":
        path_value = data.get("path")
        if not isinstance(path_value, str) or not path_value:
            return None
        return PlayHistoryEntry(kind="local", played_at=played_at, path=Path(path_value))
    video_data = data.get("video")
    if not isinstance(video_data, dict):
        return None
    video = _video_from_dict(video_data)
    if video is None:
        return None
    return PlayHistoryEntry(kind="youtube", played_at=played_at, video=video)


class PlayHistory:
    """Read and write unified play history."""

    def __init__(self) -> None:
        self._entries: list[PlayHistoryEntry] = []
        self.load()

    def load(self) -> None:
        path = _history_file()
        if path.exists():
            self._entries = self._load_unified(path)
            return
        self._entries = self._migrate_legacy()
        if self._entries:
            self.save()

    def _load_unified(self, path: Path) -> list[PlayHistoryEntry]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw = data.get("entries", [])
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load play history: %s", exc)
            return []
        entries: list[PlayHistoryEntry] = []
        if not isinstance(raw, list):
            return entries
        for item in raw:
            if isinstance(item, dict):
                entry = _entry_from_dict(item)
                if entry is not None:
                    entries.append(entry)
        entries.sort(key=lambda entry: entry.played_at, reverse=True)
        return entries[:MAX_HISTORY]

    def _migrate_legacy(self) -> list[PlayHistoryEntry]:
        local = LocalPlayHistory()
        youtube = YouTubePlayHistory()
        now = _utc_now()
        entries: list[PlayHistoryEntry] = []
        offset = 0
        for path in local.paths():
            entries.append(
                PlayHistoryEntry(
                    kind="local",
                    played_at=now.replace(microsecond=0) - timedelta(seconds=offset + 1),
                    path=path,
                )
            )
            offset += 2
        for video in youtube.videos():
            entries.append(
                PlayHistoryEntry(
                    kind="youtube",
                    played_at=now.replace(microsecond=0) - timedelta(seconds=offset + 1),
                    video=video,
                )
            )
            offset += 2
        entries.sort(key=lambda entry: entry.played_at, reverse=True)
        return entries[:MAX_HISTORY]

    def save(self) -> None:
        data = {"entries": [_entry_to_dict(entry) for entry in self._entries]}
        try:
            _history_file().write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not save play history: %s", exc)

    def add_local(self, path: Path) -> None:
        self._add(PlayHistoryEntry(kind="local", played_at=_utc_now(), path=path))

    def add_youtube(self, video: YouTubeVideo) -> None:
        self._add(PlayHistoryEntry(kind="youtube", played_at=_utc_now(), video=video))

    def _add(self, entry: PlayHistoryEntry) -> None:
        key = entry.key()
        kept = [existing for existing in self._entries if existing.key() != key]
        self._entries = [entry, *kept][:MAX_HISTORY]
        self.save()

    def remove(self, entry: PlayHistoryEntry) -> None:
        key = entry.key()
        self._entries = [existing for existing in self._entries if existing.key() != key]
        self.save()

    def remove_local(self, path: Path) -> None:
        try:
            key = f"local:{path.resolve()}"
        except OSError:
            key = f"local:{path}"
        self._entries = [entry for entry in self._entries if entry.key() != key]
        self.save()

    def remove_youtube(self, video_id: str) -> None:
        key = f"youtube:{video_id}"
        self._entries = [entry for entry in self._entries if entry.key() != key]
        self.save()

    def rename_local(self, old_path: Path, new_path: Path) -> None:
        try:
            old_resolved = old_path.resolve()
        except OSError:
            old_resolved = old_path
        updated: list[PlayHistoryEntry] = []
        changed = False
        for entry in self._entries:
            if entry.kind == "local" and entry.path is not None:
                try:
                    matches = entry.path.resolve() == old_resolved
                except OSError:
                    matches = entry.path == old_path
                if matches:
                    updated.append(
                        PlayHistoryEntry(
                            kind="local",
                            played_at=entry.played_at,
                            path=new_path,
                        )
                    )
                    changed = True
                    continue
            updated.append(entry)
        if changed:
            self._entries = updated
            self.save()

    def clear(self) -> None:
        self._entries.clear()
        self.save()

    def entries(self) -> list[PlayHistoryEntry]:
        return list(self._entries)
