"""macOS FLV remux cache for libVLC playback (stream copy to MP4)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from karaoke_blast.storage.paths import flv_compat_cache_dir
from karaoke_blast.utils.runtime_deps import resolve_ffmpeg_location, resolve_ffprobe_location

logger = logging.getLogger(__name__)

_META_FILENAME = "source.json"
_PLAYBACK_FILENAME = "playback.mp4"

# Codecs that can be muxed into MP4 without re-encoding (common karaoke FLV contents).
_VIDEO_COPY_CODECS = frozenset({"h264", "hevc", "mpeg4", "av1"})
_AUDIO_COPY_CODECS = frozenset({"aac", "mp3", "ac3", "eac3", "opus", "flac", "alac"})
_UNSUPPORTED_VIDEO_CODECS = frozenset({"vp6", "vp6a", "vp6f", "flv1", "h263", "msmpeg4v3"})


class FlvCompatError(Exception):
    """Base class for FLV compatibility failures."""


class FlvCompatUnsupported(FlvCompatError):
    """FLV cannot be remuxed without re-encoding."""


class FlvCompatProbeError(FlvCompatError):
    """FLV is missing, corrupt, or unreadable."""


class FlvCompatRemuxError(FlvCompatError):
    """Remux failed (ffmpeg error, disk space, etc.)."""


class FlvCompatCancelled(FlvCompatError):
    """Remux was cancelled."""


class FlvPlaybackAction(str, Enum):
    PLAY_DIRECT = "play_direct"
    PLAY_CACHED = "play_cached"
    PREPARE = "prepare"
    FAIL = "fail"


@dataclass(frozen=True)
class FlvPlaybackPlan:
    action: FlvPlaybackAction
    source: Path
    vlc_path: Path | None = None
    user_message: str | None = None


@dataclass(frozen=True)
class FlvCacheEntry:
    key: str
    directory: Path
    meta_path: Path
    playback_path: Path


def flv_compatibility_available() -> bool:
    return sys.platform == "darwin"


def flv_compatibility_enabled(settings_enabled: bool) -> bool:
    return flv_compatibility_available() and settings_enabled


def is_flv_file(path: Path) -> bool:
    return path.suffix.lower() == ".flv"


def cache_key_for_source(source: Path) -> str:
    """Stable cache id from resolved path, size, and mtime (invalidates on change)."""
    resolved = source.resolve()
    stat = resolved.stat()
    payload = f"{resolved}\0{stat.st_size}\0{stat.st_mtime_ns}".encode()
    return hashlib.sha256(payload).hexdigest()


def cache_entry_for_key(key: str) -> FlvCacheEntry:
    directory = flv_compat_cache_dir() / key
    return FlvCacheEntry(
        key=key,
        directory=directory,
        meta_path=directory / _META_FILENAME,
        playback_path=directory / _PLAYBACK_FILENAME,
    )


def _read_meta(meta_path: Path) -> dict[str, Any] | None:
    if not meta_path.is_file():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Ignoring invalid FLV cache metadata %s: %s", meta_path, exc)
        return None
    return data if isinstance(data, dict) else None


def _source_matches_meta(source: Path, meta: dict[str, Any]) -> bool:
    try:
        resolved = str(source.resolve())
        stat = source.stat()
    except OSError:
        return False
    if meta.get("source_path") != resolved:
        return False
    if meta.get("source_size") != stat.st_size:
        return False
    if meta.get("source_mtime_ns") != stat.st_mtime_ns:
        return False
    return True


def cached_playback_path(source: Path) -> Path | None:
    """Return a finished cached MP4 for *source*, or None if missing/stale."""
    if not is_flv_file(source):
        return None
    try:
        key = cache_key_for_source(source)
    except OSError:
        return None
    entry = cache_entry_for_key(key)
    if not entry.playback_path.is_file():
        return None
    meta = _read_meta(entry.meta_path)
    if meta is None or not _source_matches_meta(source, meta):
        return None
    return entry.playback_path


def _run_ffprobe_json(path: Path, ffprobe: str) -> dict[str, Any]:
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FlvCompatProbeError(f"Could not read FLV: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise FlvCompatProbeError(
            detail or "Could not read FLV (ffprobe failed)."
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise FlvCompatProbeError("Could not read FLV (invalid probe output).") from exc
    if not isinstance(payload, dict):
        raise FlvCompatProbeError("Could not read FLV (invalid probe output).")
    return payload


def assess_flv_remux_support(probe: dict[str, Any]) -> None:
    """Raise FlvCompatUnsupported when streams cannot be copied into MP4."""
    streams = probe.get("streams")
    if not isinstance(streams, list) or not streams:
        raise FlvCompatProbeError("FLV has no media streams.")

    has_video = False
    unsupported: list[str] = []

    for stream in streams:
        if not isinstance(stream, dict):
            continue
        codec_type = stream.get("codec_type")
        codec_name = str(stream.get("codec_name") or "").lower()
        if codec_type == "video":
            has_video = True
            if codec_name in _UNSUPPORTED_VIDEO_CODECS:
                unsupported.append(f"video ({codec_name})")
            elif codec_name and codec_name not in _VIDEO_COPY_CODECS:
                unsupported.append(f"video ({codec_name or 'unknown'})")
        elif codec_type == "audio":
            if codec_name and codec_name not in _AUDIO_COPY_CODECS:
                unsupported.append(f"audio ({codec_name})")

    if not has_video:
        raise FlvCompatProbeError("FLV has no video stream.")

    if unsupported:
        joined = ", ".join(unsupported)
        raise FlvCompatUnsupported(
            "This FLV uses codecs that cannot be converted without re-encoding "
            f"({joined}). Re-encode the file with ffmpeg or use MP4 instead."
        )


def probe_flv_for_remux(source: Path, *, ffprobe: str | None = None) -> dict[str, Any]:
    ffprobe_bin = ffprobe or resolve_ffprobe_location()
    if ffprobe_bin is None:
        raise FlvCompatProbeError("ffprobe is not available.")
    if not source.is_file():
        raise FlvCompatProbeError(f"File not found: {source.name}")
    probe = _run_ffprobe_json(source, ffprobe_bin)
    assess_flv_remux_support(probe)
    return probe


def plan_flv_playback(source: Path, *, compatibility_enabled: bool) -> FlvPlaybackPlan:
    """Decide how to play a local file (FLV compatibility applies on macOS only)."""
    source = Path(source)
    if not flv_compatibility_enabled(compatibility_enabled) or not is_flv_file(source):
        return FlvPlaybackPlan(action=FlvPlaybackAction.PLAY_DIRECT, source=source, vlc_path=source)

    cached = cached_playback_path(source)
    if cached is not None:
        return FlvPlaybackPlan(
            action=FlvPlaybackAction.PLAY_CACHED,
            source=source,
            vlc_path=cached,
        )

    if resolve_ffmpeg_location() is None or resolve_ffprobe_location() is None:
        return FlvPlaybackPlan(
            action=FlvPlaybackAction.PLAY_DIRECT,
            source=source,
            vlc_path=source,
            user_message=(
                "FLV Compatibility Mode needs ffmpeg (bundled with Karaoke Blast or on PATH). "
                "Playing the original FLV; playback may freeze on macOS."
            ),
        )

    return FlvPlaybackPlan(
        action=FlvPlaybackAction.PREPARE,
        source=source,
        vlc_path=None,
    )


def remux_flv_to_cache(
    source: Path,
    *,
    ffmpeg: str | None = None,
    ffprobe: str | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> Path:
    """Remux *source* FLV into the app cache; return path to cached MP4."""
    if is_cancelled and is_cancelled():
        raise FlvCompatCancelled()

    source = Path(source)
    probe_flv_for_remux(source, ffprobe=ffprobe)

    ffmpeg_bin = ffmpeg or resolve_ffmpeg_location()
    if ffmpeg_bin is None:
        raise FlvCompatRemuxError("ffmpeg is not available.")

    try:
        key = cache_key_for_source(source)
        stat = source.stat()
    except OSError as exc:
        raise FlvCompatProbeError(f"Cannot access FLV: {exc}") from exc

    existing = cached_playback_path(source)
    if existing is not None:
        return existing

    entry = cache_entry_for_key(key)
    entry.directory.mkdir(parents=True, exist_ok=True)
    temp_output = entry.directory / "playback.tmp.mp4"
    temp_meta = entry.meta_path.with_suffix(".json.part")

    if temp_output.is_file():
        try:
            temp_output.unlink()
        except OSError:
            pass

    cmd = [
        ffmpeg_bin,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(temp_output),
    ]

    if is_cancelled and is_cancelled():
        raise FlvCompatCancelled()

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        _safe_unlink(temp_output)
        if exc.errno == errno_enospc():
            raise FlvCompatRemuxError(
                "Not enough disk space to prepare this FLV for playback."
            ) from exc
        raise FlvCompatRemuxError(f"Could not run ffmpeg: {exc}") from exc

    try:
        while True:
            if is_cancelled and is_cancelled():
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                _safe_unlink(temp_output)
                raise FlvCompatCancelled()
            try:
                returncode = process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                continue
            break
        stdout, stderr = process.communicate(timeout=1)
    except FlvCompatCancelled:
        raise
    except subprocess.TimeoutExpired:
        process.kill()
        _safe_unlink(temp_output)
        raise FlvCompatRemuxError("FLV conversion timed out.") from None
    except OSError as exc:
        _safe_unlink(temp_output)
        raise FlvCompatRemuxError(f"FLV conversion failed: {exc}") from exc

    if returncode != 0:
        _safe_unlink(temp_output)
        detail = (stderr or stdout or "").strip()
        raise FlvCompatRemuxError(detail or "FLV conversion failed.")

    if not temp_output.is_file() or temp_output.stat().st_size == 0:
        _safe_unlink(temp_output)
        raise FlvCompatRemuxError("FLV conversion produced no output.")

    meta = {
        "source_path": str(source.resolve()),
        "source_size": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
        "cache_key": key,
    }
    try:
        temp_meta.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        os.replace(temp_output, entry.playback_path)
        os.replace(temp_meta, entry.meta_path)
    except OSError as exc:
        _safe_unlink(temp_output)
        _safe_unlink(temp_meta)
        if exc.errno == errno_enospc():
            raise FlvCompatRemuxError(
                "Not enough disk space to prepare this FLV for playback."
            ) from exc
        raise FlvCompatRemuxError(f"Could not finalize FLV cache: {exc}") from exc

    return entry.playback_path


def errno_enospc() -> int:
    return getattr(os, "ENOSPC", 28)


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.debug("Could not remove %s: %s", path, exc)


def iter_cache_entries() -> list[FlvCacheEntry]:
    root = flv_compat_cache_dir()
    if not root.is_dir():
        return []
    entries: list[FlvCacheEntry] = []
    for child in root.iterdir():
        if child.is_dir():
            entries.append(cache_entry_for_key(child.name))
    return entries


def clear_flv_compat_cache(*, exclude_paths: frozenset[Path] | None = None) -> tuple[int, int]:
    """Remove cached conversions. Returns (removed_count, skipped_in_use_count)."""
    exclude = {path.resolve() for path in (exclude_paths or frozenset())}
    removed = 0
    skipped = 0
    for entry in iter_cache_entries():
        playback = entry.playback_path
        if playback.is_file() and playback.resolve() in exclude:
            skipped += 1
            continue
        try:
            shutil.rmtree(entry.directory)
            removed += 1
        except OSError as exc:
            logger.warning("Could not remove FLV cache %s: %s", entry.directory, exc)
    return removed, skipped


def cache_total_bytes() -> int:
    total = 0
    for entry in iter_cache_entries():
        if entry.playback_path.is_file():
            try:
                total += entry.playback_path.stat().st_size
            except OSError:
                continue
    return total
