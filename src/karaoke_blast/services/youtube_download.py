"""YouTube video download via yt-dlp (background worker)."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal

from karaoke_blast.models.youtube_video import YouTubeVideo
from karaoke_blast.storage.paths import downloads_dir

logger = logging.getLogger(__name__)

VLC_FORMAT = (
    "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/"
    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
    "best[ext=mp4]/best"
)

# GUI launches on macOS often omit Homebrew from PATH.
_FFMPEG_SEARCH_DIRS = (
    "/opt/homebrew/bin",
    "/usr/local/bin",
)


def resolve_ffmpeg_location() -> str | None:
    """Return an ffmpeg binary path, including common install locations."""
    found = shutil.which("ffmpeg")
    if found:
        return found

    extra_dirs = [d for d in _FFMPEG_SEARCH_DIRS if os.path.isdir(d)]
    if extra_dirs:
        found = shutil.which("ffmpeg", path=os.pathsep.join(extra_dirs))
        if found:
            return found

    for directory in extra_dirs:
        candidate = Path(directory) / "ffmpeg"
        if candidate.is_file():
            return str(candidate)

    return None


def downloaded_file_for(video_id: str, folder: Path | None = None) -> Path | None:
    """Return an existing download path for *video_id*, if any."""
    target_dir = folder or downloads_dir()
    if not target_dir.is_dir():
        return None
    suffix = f" [{video_id}]."
    for path in target_dir.iterdir():
        if path.is_file() and path.suffix.lower() == ".mp4" and suffix in path.name:
            return path
    return None


def _build_ydl_opts(
    output_dir: Path,
    *,
    progress_callback,
) -> dict:
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "restrictfilenames": True,
        "format": VLC_FORMAT,
        "merge_output_format": "mp4",
        "outtmpl": str(output_dir / "%(title).200B [%(id)s].%(ext)s"),
        "progress_hooks": [progress_callback],
    }
    ffmpeg = resolve_ffmpeg_location()
    if ffmpeg is not None:
        opts["ffmpeg_location"] = ffmpeg
    return opts


class YouTubeDownloadWorker(QObject):
    """Run a single yt-dlp download off the UI thread."""

    progress_updated = pyqtSignal(str, float, str)
    download_finished = pyqtSignal(object, object)
    download_failed = pyqtSignal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._video: YouTubeVideo | None = None

    def run_download(self, video: YouTubeVideo) -> None:
        self._video = video
        try:
            import yt_dlp
            from yt_dlp.utils import DownloadError
        except ImportError as exc:
            self.download_failed.emit(video.video_id, f"yt-dlp is not installed: {exc}")
            return

        try:
            if resolve_ffmpeg_location() is None:
                self.download_failed.emit(
                    video.video_id,
                    "ffmpeg is not installed. Install ffmpeg and try again.",
                )
                return

            output_dir = downloads_dir()
            existing = downloaded_file_for(video.video_id, output_dir)
            if existing is not None:
                self.download_finished.emit(existing, video)
                return

            def on_progress(data: dict) -> None:
                if self._video is None:
                    return
                status = data.get("status")
                if status == "downloading":
                    total = data.get("total_bytes") or data.get("total_bytes_estimate")
                    downloaded = data.get("downloaded_bytes") or 0
                    if total:
                        percent = min(100.0, downloaded * 100.0 / total)
                        text = f"Downloading… {percent:.0f}%"
                    else:
                        percent = 0.0
                        text = "Downloading…"
                    self.progress_updated.emit(self._video.title, percent, text)
                elif status == "finished":
                    self.progress_updated.emit(self._video.title, 100.0, "Merging…")

            ydl_opts = _build_ydl_opts(output_dir, progress_callback=on_progress)
            url = video.watch_url
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

            path = downloaded_file_for(video.video_id, output_dir)
            if path is None and isinstance(info, dict):
                filepath = info.get("filepath") or info.get("_filename")
                if isinstance(filepath, str):
                    candidate = Path(filepath)
                    if candidate.suffix.lower() != ".mp4":
                        candidate = candidate.with_suffix(".mp4")
                    if candidate.is_file():
                        path = candidate

            if path is None or not path.is_file():
                raise RuntimeError("Download completed but output file was not found.")

            self.download_finished.emit(path, video)
        except (OSError, RuntimeError, TypeError, ValueError, DownloadError) as exc:
            logger.warning("YouTube download failed for %s: %s", video.video_id, exc)
            self.download_failed.emit(video.video_id, str(exc))


def start_download(
    *,
    video: YouTubeVideo,
    on_progress,
    on_finished,
    on_failed,
    parent: QObject | None = None,
) -> tuple[QThread, YouTubeDownloadWorker]:
    """Launch a one-shot download thread and connect result signals."""
    thread = QThread(parent)
    worker = YouTubeDownloadWorker()
    worker.moveToThread(thread)
    thread.started.connect(lambda: worker.run_download(video))
    worker.progress_updated.connect(on_progress, Qt.ConnectionType.QueuedConnection)
    worker.download_finished.connect(on_finished, Qt.ConnectionType.QueuedConnection)
    worker.download_failed.connect(on_failed, Qt.ConnectionType.QueuedConnection)
    worker.download_finished.connect(thread.quit)
    worker.download_failed.connect(thread.quit)
    worker.download_finished.connect(worker.deleteLater)
    worker.download_failed.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread, worker
