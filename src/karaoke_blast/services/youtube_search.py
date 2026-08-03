"""YouTube search backends and background worker."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Protocol

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from karaoke_blast.models.youtube_video import YouTubeVideo

logger = logging.getLogger(__name__)

DEFAULT_MAX_RESULTS = 15


class YouTubeSearchBackend(Protocol):
    def search(self, query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> list[YouTubeVideo]: ...


def _entry_to_video(entry: dict) -> YouTubeVideo | None:
    video_id = entry.get("id")
    if isinstance(video_id, dict):
        video_id = video_id.get("videoId") or video_id.get("id")
    if not video_id or not isinstance(video_id, str):
        return None
    title = entry.get("title") or entry.get("name") or "Untitled"
    channel = (
        entry.get("channel")
        or entry.get("uploader")
        or entry.get("channel_title")
        or "Unknown channel"
    )
    duration = entry.get("duration")
    if isinstance(duration, (int, float)):
        duration_seconds = int(duration)
    else:
        duration_seconds = None
    thumbnail = entry.get("thumbnail")
    thumbnail_url = None
    if isinstance(thumbnail, str):
        thumbnail_url = thumbnail
    elif isinstance(thumbnail, dict):
        thumbnail_url = thumbnail.get("url")
    return YouTubeVideo(
        video_id=video_id,
        title=str(title),
        channel=str(channel),
        duration_seconds=duration_seconds,
        thumbnail_url=thumbnail_url,
    )


class YtDlpSearchBackend:
    """Search YouTube via yt-dlp without an API key."""

    def search(self, query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> list[YouTubeVideo]:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
        }
        results: list[YouTubeVideo] = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
        entries = info.get("entries") if isinstance(info, dict) else None
        if not entries:
            return results
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            video = _entry_to_video(entry)
            if video is not None:
                results.append(video)
        return results


class YouTubeApiSearchBackend:
    """Search YouTube via the official Data API v3."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search(self, query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> list[YouTubeVideo]:
        search_params = urllib.parse.urlencode(
            {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": max_results,
                "key": self._api_key,
            }
        )
        search_url = f"https://www.googleapis.com/youtube/v3/search?{search_params}"
        search_payload = self._fetch_json(search_url)
        items = search_payload.get("items", [])
        video_ids: list[str] = []
        snippets: dict[str, dict] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            video_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet")
            if video_id and isinstance(snippet, dict):
                video_ids.append(video_id)
                snippets[video_id] = snippet
        if not video_ids:
            return []

        duration_by_id = self._fetch_durations(video_ids)
        results: list[YouTubeVideo] = []
        for video_id in video_ids:
            snippet = snippets[video_id]
            thumbnails = snippet.get("thumbnails", {})
            thumbnail_url = None
            for size in ("medium", "default", "high"):
                thumb = thumbnails.get(size)
                if isinstance(thumb, dict) and thumb.get("url"):
                    thumbnail_url = thumb["url"]
                    break
            results.append(
                YouTubeVideo(
                    video_id=video_id,
                    title=snippet.get("title", "Untitled"),
                    channel=snippet.get("channelTitle", "Unknown channel"),
                    duration_seconds=duration_by_id.get(video_id),
                    thumbnail_url=thumbnail_url,
                )
            )
        return results

    def _fetch_durations(self, video_ids: list[str]) -> dict[str, int | None]:
        params = urllib.parse.urlencode(
            {
                "part": "contentDetails",
                "id": ",".join(video_ids),
                "key": self._api_key,
            }
        )
        payload = self._fetch_json(f"https://www.googleapis.com/youtube/v3/videos?{params}")
        durations: dict[str, int | None] = {}
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            video_id = item.get("id")
            details = item.get("contentDetails", {})
            duration_text = details.get("duration")
            if isinstance(video_id, str):
                durations[video_id] = _parse_iso8601_duration(duration_text)
        return durations

    @staticmethod
    def _fetch_json(url: str) -> dict:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"YouTube API error ({exc.code}): {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach YouTube API: {exc.reason}") from exc
        if not isinstance(payload, dict):
            raise TypeError("Unexpected YouTube API response")
        return payload


def _parse_iso8601_duration(value: str | None) -> int | None:
    if not value or not value.startswith("PT"):
        return None
    hours = minutes = seconds = 0
    number = ""
    for char in value[2:]:
        if char.isdigit():
            number += char
            continue
        if not number:
            continue
        if char == "H":
            hours = int(number)
        elif char == "M":
            minutes = int(number)
        elif char == "S":
            seconds = int(number)
        number = ""
    total = hours * 3600 + minutes * 60 + seconds
    return total if total > 0 else None


class YouTubeSearchService:
    """Resolve the configured backend and run searches."""

    def __init__(
        self,
        *,
        backend_name: str = "yt-dlp",
        api_key: str | None = None,
    ) -> None:
        self._backend_name = backend_name
        self._api_key = api_key

    def search(self, query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> list[YouTubeVideo]:
        backend = self._resolve_backend()
        return backend.search(query, max_results=max_results)

    def _resolve_backend(self) -> YouTubeSearchBackend:
        if self._backend_name == "api":
            if not self._api_key:
                raise RuntimeError("YouTube API key is not configured.")
            return YouTubeApiSearchBackend(self._api_key)
        return YtDlpSearchBackend()


class YouTubeSearchWorker(QObject):
    """Run YouTube searches off the UI thread."""

    search_finished = pyqtSignal(list)
    search_failed = pyqtSignal(str)

    def __init__(
        self,
        *,
        backend_name: str = "yt-dlp",
        api_key: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._backend_name = backend_name
        self._api_key = api_key

    def run_search(self, query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> None:
        try:
            service = YouTubeSearchService(
                backend_name=self._backend_name,
                api_key=self._api_key,
            )
            results = service.search(query, max_results=max_results)
            self.search_finished.emit(results)
        except (RuntimeError, TypeError, OSError, ValueError) as exc:
            logger.warning("YouTube search failed: %s", exc)
            self.search_failed.emit(str(exc))


def start_search(
    *,
    query: str,
    backend_name: str,
    api_key: str | None,
    on_finished,
    on_failed,
    parent: QObject | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> QThread:
    """Launch a one-shot search thread and connect result signals."""
    thread = QThread(parent)
    worker = YouTubeSearchWorker(backend_name=backend_name, api_key=api_key)
    worker.moveToThread(thread)
    thread.started.connect(lambda: worker.run_search(query, max_results=max_results))
    worker.search_finished.connect(on_finished)
    worker.search_failed.connect(on_failed)
    worker.search_finished.connect(thread.quit)
    worker.search_failed.connect(thread.quit)
    worker.search_finished.connect(worker.deleteLater)
    worker.search_failed.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread
