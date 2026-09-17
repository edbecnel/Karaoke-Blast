"""Resolve YouTube stream URLs for VLC playback."""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal, pyqtSlot

from karaoke_blast.models.youtube_video import YouTubeVideo
from karaoke_blast.services.youtube_download_worker import _is_retryable_format_error
from karaoke_blast.services.youtube_extractor import (
    YOUTUBE_PLAYER_CLIENT_FALLBACKS,
    apply_yt_dlp_runtime_opts,
    youtube_extractor_args,
)
from karaoke_blast.utils.runtime_deps import configure_runtime_dependencies

logger = logging.getLogger(__name__)

# Progressive formats with a direct ``url`` field (VLC cannot play separate A/V without merge).
STREAM_FORMAT_FALLBACKS: tuple[str, ...] = (
    "best[height<=1080][ext=mp4]/best[height<=720][ext=mp4]/best[ext=mp4]/best",
    "best[height<=720]/best",
    "best",
)


@dataclass(frozen=True)
class YouTubeStreamPlayback:
    url: str
    http_headers: dict[str, str]


def _build_stream_ydl_opts(format_selector: str, player_client: list[str]) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": format_selector,
        "extractor_args": youtube_extractor_args(player_client),
    }
    apply_yt_dlp_runtime_opts(opts)
    return opts


def _stream_url_from_info(info: dict[str, Any]) -> str | None:
    url = info.get("url")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        return url
    return None


def _http_headers_from_info(
    info: dict[str, Any],
    *,
    watch_url: str | None = None,
) -> dict[str, str]:
    raw = info.get("http_headers")
    headers: dict[str, str] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(key, str) and isinstance(value, str) and value:
                headers[key] = value
    if not any(key.lower() == "referer" for key in headers):
        referer = info.get("webpage_url")
        if isinstance(referer, str) and referer:
            headers["Referer"] = referer
        elif watch_url:
            headers["Referer"] = watch_url
    return headers


def _stream_url_is_readable(url: str, headers: dict[str, str]) -> bool:
    """Return True when VLC should be able to open the progressive stream URL."""
    request_headers = dict(headers)
    request_headers.setdefault("Range", "bytes=0-1023")
    request = urllib.request.Request(url, headers=request_headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read(256)
        return True
    except urllib.error.HTTPError as exc:
        if exc.code in {403, 404, 410}:
            return False
        return 200 <= exc.code < 300
    except OSError:
        return False


def resolve_youtube_stream_playback(
    watch_url: str,
    *,
    is_cancelled: Callable[[], bool] | None = None,
) -> YouTubeStreamPlayback:
    """Return a direct progressive stream URL and HTTP headers for VLC."""
    configure_runtime_dependencies()
    try:
        import yt_dlp
        from yt_dlp.utils import DownloadError
    except ImportError as exc:
        raise RuntimeError(f"yt-dlp is not installed: {exc}") from exc

    last_error: BaseException | None = None
    for player_client in YOUTUBE_PLAYER_CLIENT_FALLBACKS:
        for index, format_selector in enumerate(STREAM_FORMAT_FALLBACKS):
            if is_cancelled is not None and is_cancelled():
                raise RuntimeError("YouTube stream lookup cancelled.")
            try:
                ydl_opts = _build_stream_ydl_opts(format_selector, player_client)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(watch_url, download=False)
                if not isinstance(info, dict):
                    raise RuntimeError("Could not read YouTube stream metadata.")
                stream_url = _stream_url_from_info(info)
                if stream_url is None:
                    last_error = DownloadError("No direct stream URL in selected format.")
                    if index < len(STREAM_FORMAT_FALLBACKS) - 1:
                        continue
                    break
                headers = _http_headers_from_info(info, watch_url=watch_url)
                if not _stream_url_is_readable(stream_url, headers):
                    last_error = DownloadError(
                        "YouTube returned HTTP 403 for the selected stream."
                    )
                    logger.info(
                        "Stream URL not readable for %s (client %s format %r)",
                        watch_url,
                        player_client,
                        format_selector,
                    )
                    if index < len(STREAM_FORMAT_FALLBACKS) - 1:
                        continue
                    break
                logger.debug(
                    "YouTube stream for %s resolved with client %s format %r",
                    watch_url,
                    player_client,
                    format_selector,
                )
                return YouTubeStreamPlayback(url=stream_url, http_headers=headers)
            except DownloadError as exc:
                last_error = exc
                if index < len(STREAM_FORMAT_FALLBACKS) - 1 and _is_retryable_format_error(
                    exc
                ):
                    logger.info(
                        "Stream client %s format %r failed, trying next fallback: %s",
                        player_client,
                        format_selector,
                        exc,
                    )
                    continue
                break
            except Exception as exc:
                last_error = exc
                if index < len(STREAM_FORMAT_FALLBACKS) - 1 and _is_retryable_format_error(
                    exc
                ):
                    continue
                break

    if last_error is not None:
        text = str(last_error).strip() or last_error.__class__.__name__
        lowered = text.lower()
        if "403" in lowered or "forbidden" in lowered:
            raise RuntimeError(
                "YouTube blocked streaming for this video (HTTP 403). "
                "Update yt-dlp (pip install -U yt-dlp), then try again or use Download."
            ) from last_error
        if "not available" in lowered:
            raise RuntimeError(
                "Could not find a playable YouTube stream. "
                "Update yt-dlp and ensure Deno or Node is installed, then try again."
            ) from last_error
        raise RuntimeError(text) from last_error
    raise RuntimeError("Could not find a playable stream for this video.")


class YouTubeStreamWorker(QObject):
    """Resolve a YouTube stream URL off the UI thread."""

    stream_ready = pyqtSignal(object, object)
    stream_failed = pyqtSignal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._video: YouTubeVideo | None = None
        self._cancel_requested = False

    def prepare(self, video: YouTubeVideo) -> None:
        self._video = video
        self._cancel_requested = False

    @pyqtSlot()
    def request_cancel(self) -> None:
        self._cancel_requested = True

    @pyqtSlot()
    def run(self) -> None:
        video = self._video
        if video is None:
            return
        try:
            playback = resolve_youtube_stream_playback(
                video.watch_url,
                is_cancelled=lambda: self._cancel_requested,
            )
        except RuntimeError as exc:
            self.stream_failed.emit(video.video_id, str(exc))
            return
        if self._cancel_requested:
            return
        self.stream_ready.emit(playback, video)


def start_youtube_stream(
    *,
    video: YouTubeVideo,
    on_ready,
    on_failed,
    parent: QObject | None = None,
) -> tuple[QThread, YouTubeStreamWorker]:
    """Launch a one-shot stream-resolution thread."""
    thread = QThread(parent)
    worker = YouTubeStreamWorker()
    worker.prepare(video)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.stream_ready.connect(on_ready, Qt.ConnectionType.QueuedConnection)
    worker.stream_failed.connect(on_failed, Qt.ConnectionType.QueuedConnection)
    worker.stream_ready.connect(thread.quit)
    worker.stream_failed.connect(thread.quit)
    worker.stream_ready.connect(worker.deleteLater)
    worker.stream_failed.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread, worker
