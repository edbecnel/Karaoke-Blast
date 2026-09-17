"""Headless yt-dlp download worker for use in a child process."""

from __future__ import annotations

import json
import logging
import signal
import sys
from pathlib import Path
from typing import Any

from karaoke_blast.services.youtube_extractor import (
    YOUTUBE_PLAYER_CLIENT_FALLBACKS,
    apply_yt_dlp_runtime_opts,
    youtube_extractor_args,
)
from karaoke_blast.storage.paths import default_downloads_dir
from karaoke_blast.utils.runtime_deps import (
    configure_runtime_dependencies,
    resolve_ffmpeg_location,
)

logger = logging.getLogger(__name__)

VLC_FORMAT = (
    "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/"
    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
    "best[ext=mp4]/"
    "bestvideo[vcodec^=avc1]+bestaudio/"
    "bestvideo+bestaudio/"
    "best"
)

DOWNLOAD_FORMAT_FALLBACKS: tuple[str, ...] = (
    VLC_FORMAT,
    "bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best",
    "bestvideo+bestaudio/best",
    "bv*+ba/b",
    "best",
)


class DownloadCancelled(Exception):
    """Raised when a download is cancelled by the user."""


def cleanup_partial_download(video_id: str, output_dir: Path) -> None:
    """Remove incomplete download files for *video_id* from *output_dir*."""
    if not output_dir.is_dir():
        return
    marker = f" [{video_id}]."
    for path in output_dir.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if marker in name or name.endswith(f".{video_id}.part"):
            try:
                path.unlink()
            except OSError as exc:
                logger.warning("Could not remove partial download %s: %s", path, exc)
    for path in output_dir.glob(f"*{video_id}*.part"):
        if path.is_file():
            try:
                path.unlink()
            except OSError as exc:
                logger.warning("Could not remove partial download %s: %s", path, exc)


def downloaded_file_for(video_id: str, folder: Path | None = None) -> Path | None:
    """Return an existing download path for *video_id*, if any."""
    target_dir = folder or default_downloads_dir()
    if not target_dir.is_dir():
        return None
    suffix = f" [{video_id}]."
    for path in target_dir.iterdir():
        if path.is_file() and path.suffix.lower() == ".mp4" and suffix in path.name:
            return path
    return None


def _is_retryable_format_error(exc: BaseException) -> bool:
    """Return True when another format selector may succeed."""
    text = str(exc).lower()
    return any(
        phrase in text
        for phrase in (
            "not available",
            "no video formats",
            "requested format",
        )
    )


def _build_ydl_opts(
    output_dir: Path,
    *,
    progress_callback,
    format: str,
    player_client: list[str],
) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "restrictfilenames": True,
        "format": format,
        "merge_output_format": "mp4",
        "outtmpl": str(output_dir / "%(title).200B [%(id)s].%(ext)s"),
        "progress_hooks": [progress_callback],
        "extractor_args": youtube_extractor_args(player_client),
    }
    ffmpeg = resolve_ffmpeg_location()
    if ffmpeg is not None:
        opts["ffmpeg_location"] = ffmpeg
    apply_yt_dlp_runtime_opts(opts)
    return opts


def _resolve_downloaded_path(
    video_id: str,
    output_dir: Path,
    info: dict[str, Any] | None,
) -> Path | None:
    path = downloaded_file_for(video_id, output_dir)
    if path is not None:
        return path
    if not isinstance(info, dict):
        return None
    filepath = info.get("filepath") or info.get("_filename")
    if not isinstance(filepath, str):
        return None
    candidate = Path(filepath)
    if candidate.suffix.lower() != ".mp4":
        candidate = candidate.with_suffix(".mp4")
    return candidate if candidate.is_file() else None


def _friendly_download_error(exc: BaseException) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    if _is_retryable_format_error(exc):
        return "Could not find a downloadable format for this video."
    if "403" not in text and "forbidden" not in text.lower():
        return text
    from karaoke_blast.utils.runtime_deps import resolve_js_runtimes

    if resolve_js_runtimes():
        return text
    return (
        "YouTube returned 403 Forbidden. yt-dlp needs Deno (recommended) or Node "
        "to download videos. Install Deno from https://deno.com and try again."
    )


def _emit_event(event: dict[str, Any]) -> None:
    print(json.dumps(event, ensure_ascii=True), flush=True)


def run_download_in_process(
    *,
    video_id: str,
    title: str,
    watch_url: str,
    output_dir: Path,
    on_progress,
    is_cancelled=None,
) -> Path:
    """Download a video with yt-dlp in the current process."""
    def check_cancelled() -> None:
        if is_cancelled is not None and is_cancelled():
            raise YtDlpDownloadCancelled()

    configure_runtime_dependencies()
    try:
        import yt_dlp
        from yt_dlp.utils import DownloadCancelled as YtDlpDownloadCancelled
        from yt_dlp.utils import DownloadError
    except ImportError as exc:
        raise RuntimeError(f"yt-dlp is not installed: {exc}") from exc

    if resolve_ffmpeg_location() is None:
        raise RuntimeError("ffmpeg is not installed. Install ffmpeg and try again.")

    output_dir.mkdir(parents=True, exist_ok=True)
    existing = downloaded_file_for(video_id, output_dir)
    if existing is not None:
        return existing

    on_progress(0.0, "Starting download…")

    def on_ytdl_progress(progress: dict[str, Any]) -> None:
        check_cancelled()
        status = progress.get("status")
        if status == "downloading":
            total = progress.get("total_bytes") or progress.get("total_bytes_estimate")
            downloaded = progress.get("downloaded_bytes") or 0
            if total:
                percent = min(100.0, downloaded * 100.0 / total)
                text = f"Downloading… {percent:.0f}%"
            else:
                percent = 0.0
                text = "Downloading…"
            on_progress(percent, text)
        elif status == "finished":
            on_progress(100.0, "Merging…")

    info: dict[str, Any] | None = None
    try:
        last_error: DownloadError | None = None
        for player_client in YOUTUBE_PLAYER_CLIENT_FALLBACKS:
            for index, format_selector in enumerate(DOWNLOAD_FORMAT_FALLBACKS):
                try:
                    ydl_opts = _build_ydl_opts(
                        output_dir,
                        progress_callback=on_ytdl_progress,
                        format=format_selector,
                        player_client=player_client,
                    )
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        check_cancelled()
                        extracted = ydl.extract_info(watch_url, download=True)
                        check_cancelled()
                    info = extracted if isinstance(extracted, dict) else None
                    logger.debug(
                        "YouTube download for %s succeeded with client %s format %r",
                        video_id,
                        player_client,
                        format_selector,
                    )
                    last_error = None
                    break
                except DownloadError as exc:
                    last_error = exc
                    if (
                        index < len(DOWNLOAD_FORMAT_FALLBACKS) - 1
                        and _is_retryable_format_error(exc)
                    ):
                        cleanup_partial_download(video_id, output_dir)
                        logger.info(
                            "Client %s format %r failed for %s, trying next fallback: %s",
                            player_client,
                            format_selector,
                            video_id,
                            exc,
                        )
                        continue
                    break
            if info is not None:
                break
        if info is None and last_error is not None:
            raise RuntimeError(_friendly_download_error(last_error)) from last_error
    except (DownloadCancelled, YtDlpDownloadCancelled):
        cleanup_partial_download(video_id, output_dir)
        raise DownloadCancelled() from None

    path = _resolve_downloaded_path(video_id, output_dir, info)
    if path is None:
        raise RuntimeError("Download completed but output file was not found.")
    return path


def run_isolated_download(config_path: Path) -> int:
    """Perform a download and stream JSON progress events to stdout."""
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        video_id = str(data["video_id"])
        title = str(data.get("title", video_id))
        watch_url = str(data["watch_url"])
        output_dir = Path(str(data["output_dir"]))
    except (OSError, TypeError, ValueError, KeyError) as exc:
        _emit_event({"event": "failed", "message": f"Invalid download config: {exc}"})
        return 1

    cancelled = False

    def _on_sigterm(_signum: int, _frame: object) -> None:
        nonlocal cancelled
        cancelled = True

    previous_handler = signal.signal(signal.SIGTERM, _on_sigterm)
    try:
        path = run_download_in_process(
            video_id=video_id,
            title=title,
            watch_url=watch_url,
            output_dir=output_dir,
            on_progress=lambda percent, status: _emit_event(
                {
                    "event": "progress",
                    "title": title,
                    "percent": percent,
                    "status": status,
                }
            ),
            is_cancelled=lambda: cancelled,
        )
    except DownloadCancelled:
        _emit_event({"event": "cancelled"})
        return 2
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        logger.warning("Isolated YouTube download failed for %s: %s", video_id, exc)
        _emit_event({"event": "failed", "message": _friendly_download_error(exc)})
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous_handler)

    _emit_event({"event": "finished", "path": str(path)})
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        raise SystemExit(f"Usage: {Path(__file__).name} <config.json>")
    return run_isolated_download(Path(args[0]))


if __name__ == "__main__":
    raise SystemExit(main())
