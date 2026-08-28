"""YouTube video download via yt-dlp (background worker)."""

from __future__ import annotations

import logging
import time
from importlib.util import find_spec
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot

from karaoke_blast.models.youtube_video import YouTubeVideo
from karaoke_blast.services.youtube_download_worker import (
    DownloadCancelled,
    cleanup_partial_download,
    downloaded_file_for,
    run_download_in_process,
)
from karaoke_blast.utils.runtime_deps import resolve_ffmpeg_location

logger = logging.getLogger(__name__)

_PROGRESS_EMIT_INTERVAL_S = 0.2
_PROGRESS_PERCENT_DELTA = 0.5


def _friendly_download_error(exc: BaseException, *, detail: str = "") -> str:
    text = str(exc).strip() or detail.strip() or exc.__class__.__name__
    return text


class YouTubeDownloadWorker(QObject):
    """Run a single yt-dlp download off the UI thread."""

    progress_updated = pyqtSignal(str, float, str)
    download_finished = pyqtSignal(object, object)
    download_failed = pyqtSignal(str, str)
    download_cancelled = pyqtSignal(str)
    cancel_triggered = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._video: YouTubeVideo | None = None
        self._output_dir: Path | None = None
        self._last_progress_emit = 0.0
        self._last_percent = -1.0
        self._cancel_requested = False

    def prepare(self, video: YouTubeVideo, output_dir: Path) -> None:
        self._video = video
        self._output_dir = output_dir
        self._last_progress_emit = 0.0
        self._last_percent = -1.0
        self._cancel_requested = False

    @pyqtSlot()
    def request_cancel(self) -> None:
        self._cancel_requested = True

    @pyqtSlot()
    def run(self) -> None:
        video = self._video
        output_dir = self._output_dir
        if video is None or output_dir is None:
            return
        self._run_download(video, output_dir)

    def _emit_progress(self, percent: float, status: str) -> None:
        if self._video is None:
            return
        now = time.monotonic()
        if (
            self._last_percent >= 0.0
            and percent < 100.0
            and now - self._last_progress_emit < _PROGRESS_EMIT_INTERVAL_S
            and abs(percent - self._last_percent) < _PROGRESS_PERCENT_DELTA
        ):
            return
        self._last_progress_emit = now
        self._last_percent = percent
        self.progress_updated.emit(self._video.title, percent, status)

    def _run_download(self, video: YouTubeVideo, output_dir: Path) -> None:
        if find_spec("yt_dlp") is None:
            self.download_failed.emit(video.video_id, "yt-dlp is not installed.")
            return

        try:
            if resolve_ffmpeg_location() is None:
                self.download_failed.emit(
                    video.video_id,
                    "ffmpeg is not installed. Install ffmpeg and try again.",
                )
                return

            output_dir.mkdir(parents=True, exist_ok=True)
            existing = downloaded_file_for(video.video_id, output_dir)
            if existing is not None:
                self.download_finished.emit(existing, video)
                return

            path = run_download_in_process(
                video_id=video.video_id,
                title=video.title,
                watch_url=video.watch_url,
                output_dir=output_dir,
                on_progress=self._emit_progress,
                is_cancelled=lambda: self._cancel_requested,
            )
            self.download_finished.emit(path, video)
        except DownloadCancelled:
            cleanup_partial_download(video.video_id, output_dir)
            self.download_cancelled.emit(video.video_id)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning("YouTube download failed for %s: %s", video.video_id, exc)
            self.download_failed.emit(
                video.video_id,
                _friendly_download_error(exc, detail=str(exc)),
            )


def start_download(
    *,
    video: YouTubeVideo,
    output_dir: Path,
    on_progress,
    on_finished,
    on_failed,
    on_cancelled=None,
    parent: QObject | None = None,
) -> tuple[QThread, YouTubeDownloadWorker]:
    """Launch a one-shot download thread and connect result signals."""
    thread = QThread(parent)
    worker = YouTubeDownloadWorker()
    worker.prepare(video, output_dir)
    worker.moveToThread(thread)
    worker.cancel_triggered.connect(worker.request_cancel, Qt.ConnectionType.DirectConnection)
    thread.started.connect(worker.run)
    worker.progress_updated.connect(on_progress, Qt.ConnectionType.QueuedConnection)
    worker.download_finished.connect(on_finished, Qt.ConnectionType.QueuedConnection)
    worker.download_failed.connect(on_failed, Qt.ConnectionType.QueuedConnection)
    if on_cancelled is not None:
        worker.download_cancelled.connect(on_cancelled, Qt.ConnectionType.QueuedConnection)
    worker.download_finished.connect(thread.quit)
    worker.download_failed.connect(thread.quit)
    worker.download_cancelled.connect(thread.quit)
    worker.download_finished.connect(worker.deleteLater)
    worker.download_failed.connect(worker.deleteLater)
    worker.download_cancelled.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread, worker
