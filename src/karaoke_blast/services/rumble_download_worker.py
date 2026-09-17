"""yt-dlp download worker for Rumble videos."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from karaoke_blast.services.youtube_extractor import apply_yt_dlp_runtime_opts
from karaoke_blast.utils.rumble_url import rumble_embed_url
from karaoke_blast.utils.runtime_deps import (
    configure_runtime_dependencies,
    resolve_ffmpeg_location,
    resolve_yt_dlp_binary,
    subprocess_path_env,
)

logger = logging.getLogger(__name__)

RUMBLE_FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"


def rumble_ytdlp_referer(page_url: str, ytdlp_url: str) -> str:
    """Referer for yt-dlp; watch-page Referer breaks Rumble embed metadata (403)."""
    if "/embed/" in ytdlp_url:
        return ytdlp_url.rstrip("/") + "/"
    return page_url


def _impersonate_available() -> bool:
    try:
        import curl_cffi  # noqa: F401
    except ImportError:
        return False
    return True


def _apply_rumble_impersonate(opts: dict[str, Any]) -> None:
    """yt-dlp 2026+ expects ImpersonateTarget, not the string \"chrome\"."""
    if not _impersonate_available():
        return
    try:
        from yt_dlp.networking.impersonate import ImpersonateTarget
    except ImportError:
        return
    try:
        opts["impersonate"] = ImpersonateTarget.from_str("chrome")
    except (ValueError, TypeError):
        pass


def build_rumble_ydl_opts(
    page_url: str,
    *,
    download: bool,
    ytdlp_url: str | None = None,
) -> dict[str, Any]:
    target = ytdlp_url or page_url
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "http_headers": {"Referer": rumble_ytdlp_referer(page_url, target)},
    }
    if download:
        opts["format"] = RUMBLE_FORMAT
        opts["merge_output_format"] = "mp4"
    else:
        opts["skip_download"] = True
    _apply_rumble_impersonate(opts)
    # Exported Netscape cookies often make Rumble watch-page requests 403; impersonate alone works.
    apply_yt_dlp_runtime_opts(opts, use_cookies=False)
    ffmpeg = resolve_ffmpeg_location()
    if ffmpeg is not None:
        opts["ffmpeg_location"] = ffmpeg
    return opts


def _safe_id(page_url: str, page_video_id: str) -> str:
    return page_video_id or re.sub(r"[^a-zA-Z0-9_-]+", "_", page_url)[:80]


def _download_marker(page_video_id: str, page_url: str) -> str:
    token = _safe_id(page_url, page_video_id)
    return f" [rumble:{token}]."


def downloaded_file_for(page_video_id: str, page_url: str, output_dir: Path) -> Path | None:
    if not output_dir.is_dir():
        return None
    marker = _download_marker(page_video_id, page_url)
    for path in output_dir.iterdir():
        if (
            path.is_file()
            and path.suffix.lower() == ".mp4"
            and marker in path.name
            and path.stat().st_size > 0
        ):
            return path
    return None


def _rumble_download_error_retryable(message: str) -> bool:
    lowered = message.lower()
    return "403" in message or "impersonate" in lowered or "forbidden" in lowered


def _ytdlp_url_for_rumble(
    page_url: str,
    embed_id: str | None,
    *,
    page_video_id: str = "",
) -> str:
    """Prefer embed URLs; watch pages often 403 when cookies are passed to yt-dlp."""
    trusted = embed_id
    if trusted and page_video_id and trusted == page_video_id:
        trusted = None
    if trusted:
        return rumble_embed_url(trusted)
    from karaoke_blast.services.rumble_metadata import resolve_rumble_embed_id

    resolved = resolve_rumble_embed_id(page_url)
    if resolved and resolved != page_video_id:
        return rumble_embed_url(resolved)
    if resolved:
        return rumble_embed_url(resolved)
    return page_url


def _cli_referer_attempts(page_url: str, ytdlp_url: str) -> list[str | None]:
    """Referer values to try; None omits the header (Rumble is picky)."""
    return [
        rumble_ytdlp_referer(page_url, ytdlp_url),
        ytdlp_url.rstrip("/") + "/",
        "https://rumble.com/",
        None,
    ]


def _run_ytdlp_cli_download(
    *,
    binary: str,
    ytdlp_url: str,
    referer: str | None,
    format_selector: str,
    outtmpl: str,
    on_progress,
    is_cancelled=None,
) -> tuple[int, list[str]]:
    from yt_dlp.utils import DownloadCancelled as YtDlpDownloadCancelled

    def check_cancelled() -> None:
        if is_cancelled is not None and is_cancelled():
            raise YtDlpDownloadCancelled()

    cmd = [
        binary,
        "--no-warnings",
        "--no-playlist",
        "--impersonate",
        "chrome",
    ]
    if referer is not None:
        cmd.extend(["--add-header", f"Referer:{referer}"])
    cmd.extend(
        [
            "-f",
            format_selector,
            "--merge-output-format",
            "mp4",
            "-o",
            outtmpl,
            ytdlp_url,
        ]
    )
    ffmpeg = resolve_ffmpeg_location()
    if ffmpeg is not None:
        cmd[1:1] = ["--ffmpeg-location", ffmpeg]

    output_tail: list[str] = []
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=subprocess_path_env(),
    )
    try:
        if proc.stdout is not None:
            for line in proc.stdout:
                check_cancelled()
                stripped = line.strip()
                if stripped:
                    output_tail.append(stripped)
                    if len(output_tail) > 12:
                        output_tail.pop(0)
                match = re.search(r"\[download\]\s+(\d+(?:\.\d+)?)%", line)
                if match:
                    percent = float(match.group(1))
                    on_progress(percent, f"Downloading… {percent:.0f}%")
        return_code = proc.wait(timeout=7200)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError("Rumble download timed out.") from None
    finally:
        if proc.stdout is not None:
            proc.stdout.close()
    check_cancelled()
    return return_code, output_tail


def _run_rumble_download_via_cli(
    *,
    page_url: str,
    page_video_id: str,
    embed_id: str | None,
    output_dir: Path,
    on_progress,
    is_cancelled=None,
) -> Path:
    """Use system yt-dlp (Homebrew) — most reliable for Rumble embed downloads."""
    binary = resolve_yt_dlp_binary()
    if binary is None:
        raise RuntimeError(
            "Rumble download needs yt-dlp with browser impersonation. "
            "Install curl_cffi in this Python environment (pip install curl_cffi) "
            "or install yt-dlp via Homebrew."
        )

    ytdlp_url = _ytdlp_url_for_rumble(
        page_url, embed_id, page_video_id=page_video_id
    )
    if "/embed/" not in ytdlp_url:
        raise RuntimeError(
            "Could not resolve this Rumble video for download. "
            "Try Play first, or paste the link again."
        )

    token = _safe_id(page_url, page_video_id)
    outtmpl = str(output_dir / f"%(title).200B [rumble:{token}].%(ext)s")
    format_attempts = (RUMBLE_FORMAT, "best")
    last_detail = ""
    on_progress(0.0, "Downloading…")

    for format_selector in format_attempts:
        for referer in _cli_referer_attempts(page_url, ytdlp_url):
            return_code, output_tail = _run_ytdlp_cli_download(
                binary=binary,
                ytdlp_url=ytdlp_url,
                referer=referer,
                format_selector=format_selector,
                outtmpl=outtmpl,
                on_progress=on_progress,
                is_cancelled=is_cancelled,
            )
            if return_code == 0:
                path = downloaded_file_for(page_video_id, page_url, output_dir)
                if path is not None:
                    return path
                raise RuntimeError("Download finished but output file was not found.")
            last_detail = output_tail[-1] if output_tail else ""
            if "403" not in last_detail and "forbidden" not in last_detail.lower():
                break

    detail = last_detail
    if "403" in detail or "forbidden" in detail.lower():
        raise RuntimeError(
            "Rumble blocked the download (HTTP 403). Try again in a moment."
        )
    if detail.startswith("ERROR:"):
        raise RuntimeError(detail.removeprefix("ERROR:").strip())
    raise RuntimeError(
        detail or "Rumble download failed. Check your network connection and try again."
    )


def cleanup_partial_download(page_video_id: str, page_url: str, output_dir: Path) -> None:
    if not output_dir.is_dir():
        return
    marker = _download_marker(page_video_id, page_url).strip()
    for path in output_dir.iterdir():
        if marker in path.name and path.suffix.lower() in {".mp4", ".part", ".ytdl"}:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def run_rumble_download_in_process(
    *,
    page_url: str,
    page_video_id: str,
    title: str,
    embed_id: str | None = None,
    output_dir: Path,
    on_progress,
    is_cancelled=None,
) -> Path:
    configure_runtime_dependencies()
    try:
        import yt_dlp
        from yt_dlp.utils import DownloadCancelled as YtDlpDownloadCancelled
        from yt_dlp.utils import DownloadError
    except ImportError as exc:
        raise RuntimeError(f"yt-dlp is not installed: {exc}") from exc

    if resolve_ffmpeg_location() is None:
        raise RuntimeError("ffmpeg is not installed. Install ffmpeg and try again.")

    def check_cancelled() -> None:
        if is_cancelled is not None and is_cancelled():
            raise YtDlpDownloadCancelled()

    output_dir.mkdir(parents=True, exist_ok=True)
    existing = downloaded_file_for(page_video_id, page_url, output_dir)
    if existing is not None:
        return existing

    token = _safe_id(page_url, page_video_id)
    on_progress(0.0, "Starting download…")

    ytdlp_url = _ytdlp_url_for_rumble(
        page_url, embed_id, page_video_id=page_video_id
    )

    cli = resolve_yt_dlp_binary()
    if cli is not None:
        return _run_rumble_download_via_cli(
            page_url=page_url,
            page_video_id=page_video_id,
            embed_id=embed_id,
            output_dir=output_dir,
            on_progress=on_progress,
            is_cancelled=is_cancelled,
        )

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

    ydl_opts = build_rumble_ydl_opts(
        page_url, download=True, ytdlp_url=ytdlp_url
    )
    ydl_opts["outtmpl"] = str(
        output_dir / f"%(title).200B [rumble:{token}].%(ext)s"
    )
    ydl_opts["progress_hooks"] = [on_ytdl_progress]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            check_cancelled()
            info = ydl.extract_info(ytdlp_url, download=True)
            check_cancelled()
    except DownloadError as exc:
        message = str(exc).strip() or "Rumble download failed."
        if _rumble_download_error_retryable(message) and resolve_yt_dlp_binary() is not None:
            return _run_rumble_download_via_cli(
                page_url=page_url,
                page_video_id=page_video_id,
                embed_id=embed_id,
                output_dir=output_dir,
                on_progress=on_progress,
                is_cancelled=is_cancelled,
            )
        if _rumble_download_error_retryable(message) and not _impersonate_available():
            raise RuntimeError(
                "Rumble download needs browser impersonation. "
                "Run: pip install curl_cffi — or install yt-dlp via Homebrew — "
                "and export rumble.com cookies (Preferences → cookies folder)."
            ) from exc
        if "403" in message or "forbidden" in message.lower():
            raise RuntimeError(
                "Rumble blocked the download (HTTP 403). Try again in a moment."
            ) from exc
        raise RuntimeError(message) from exc
    except YtDlpDownloadCancelled:
        cleanup_partial_download(page_video_id, page_url, output_dir)
        raise

    path = downloaded_file_for(page_video_id, page_url, output_dir)
    if path is not None:
        return path
    if isinstance(info, dict):
        filepath = info.get("requested_downloads")
        if isinstance(filepath, list) and filepath:
            first = filepath[0]
            if isinstance(first, dict) and isinstance(first.get("filepath"), str):
                candidate = Path(first["filepath"])
                if candidate.is_file():
                    return candidate
        merged = info.get("_filename") or info.get("filepath")
        if isinstance(merged, str):
            candidate = Path(merged)
            if candidate.is_file():
                return candidate
    raise RuntimeError("Download finished but output file was not found.")
