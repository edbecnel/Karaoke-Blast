"""Rumble video download via yt-dlp (background worker)."""

from __future__ import annotations

import logging
import time
from importlib.util import find_spec
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot

from karaoke_blast.models.rumble_video import RumbleVideo
from karaoke_blast.services.rumble_metadata import enrich_rumble_video
from karaoke_blast.services.rumble_download_worker import (
    cleanup_partial_download,
    downloaded_file_for,
    run_rumble_download_in_process,
)
from karaoke_blast.utils.runtime_deps import configure_runtime_dependencies, resolve_ffmpeg_location

logger = logging.getLogger(__name__)

_PROGRESS_EMIT_INTERVAL_S = 0.2
_PROGRESS_PERCENT_DELTA = 0.5


class RumbleDownloadWorker(QObject):
    progress_updated = pyqtSignal(str, float, str)
    download_finished = pyqtSignal(object, object)
    download_failed = pyqtSignal(str, str)
    download_cancelled = pyqtSignal(str)
    cancel_triggered = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._video: RumbleVideo | None = None
        self._output_dir: Path | None = None
        self._last_progress_emit = 0.0
        self._last_percent = -1.0
        self._cancel_requested = False

    def prepare(self, video: RumbleVideo, output_dir: Path) -> None:
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

    def _run_download(self, video: RumbleVideo, output_dir: Path) -> None:
        configure_runtime_dependencies()
        video = enrich_rumble_video(video)
        if find_spec("yt_dlp") is None:
            self.download_failed.emit(video.page_url, "yt-dlp is not installed.")
            return
        if resolve_ffmpeg_location() is None:
            self.download_failed.emit(
                video.page_url,
                "ffmpeg is not installed. Install ffmpeg and try again.",
            )
            return
        existing = downloaded_file_for(video.page_video_id, video.page_url, output_dir)
        if existing is not None:
            self.download_finished.emit(existing, video)
            return

        def on_progress(percent: float, status: str) -> None:
            now = time.monotonic()
            if (
                now - self._last_progress_emit < _PROGRESS_EMIT_INTERVAL_S
                and abs(percent - self._last_percent) < _PROGRESS_PERCENT_DELTA
            ):
                return
            self._last_progress_emit = now
            self._last_percent = percent
            self.progress_updated.emit(video.title, percent, status)

        try:
            path = run_rumble_download_in_process(
                page_url=video.page_url,
                page_video_id=video.page_video_id,
                title=video.title,
                embed_id=video.embed_id,
                output_dir=output_dir,
                on_progress=on_progress,
                is_cancelled=lambda: self._cancel_requested,
            )
        except Exception as exc:
            if self._cancel_requested:
                cleanup_partial_download(
                    video.page_video_id, video.page_url, output_dir
                )
                self.download_cancelled.emit(video.page_url)
                return
            logger.warning("Rumble download failed for %s: %s", video.page_url, exc)
            self.download_failed.emit(video.page_url, str(exc))
            return
        if self._cancel_requested:
            cleanup_partial_download(video.page_video_id, video.page_url, output_dir)
            self.download_cancelled.emit(video.page_url)
            return
        self.download_finished.emit(path, video)


def start_rumble_download(
    *,
    video: RumbleVideo,
    output_dir: Path,
    on_progress,
    on_finished,
    on_failed,
    on_cancelled,
    parent: QObject | None = None,
) -> tuple[QThread, RumbleDownloadWorker]:
    thread = QThread(parent)
    worker = RumbleDownloadWorker()
    worker.prepare(video, output_dir)
    worker.moveToThread(thread)
    worker.cancel_triggered.connect(worker.request_cancel, Qt.ConnectionType.DirectConnection)
    thread.started.connect(worker.run)
    worker.progress_updated.connect(on_progress, Qt.ConnectionType.QueuedConnection)
    worker.download_finished.connect(on_finished, Qt.ConnectionType.QueuedConnection)
    worker.download_failed.connect(on_failed, Qt.ConnectionType.QueuedConnection)
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
