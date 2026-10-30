"""Tests for macOS FLV compatibility remux cache."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from karaoke_blast.services.flv_compat import (
    FlvCompatUnsupported,
    FlvPlaybackAction,
    assess_flv_remux_support,
    cache_entry_for_key,
    cache_key_for_source,
    cached_playback_path,
    clear_flv_compat_cache,
    plan_flv_playback,
    remux_flv_to_cache,
)
from karaoke_blast.utils.runtime_deps import resolve_ffmpeg_location


def _probe_h264_aac() -> dict:
    return {
        "streams": [
            {"codec_type": "video", "codec_name": "h264"},
            {"codec_type": "audio", "codec_name": "aac"},
        ]
    }


def test_assess_flv_remux_support_accepts_h264_aac() -> None:
    assess_flv_remux_support(_probe_h264_aac())


def test_assess_flv_remux_support_rejects_vp6() -> None:
    probe = {
        "streams": [
            {"codec_type": "video", "codec_name": "vp6"},
            {"codec_type": "audio", "codec_name": "mp3"},
        ]
    }
    with pytest.raises(FlvCompatUnsupported, match="re-encoding"):
        assess_flv_remux_support(probe)


def test_cache_key_changes_when_mtime_changes(tmp_path: Path) -> None:
    flv = tmp_path / "song.flv"
    flv.write_bytes(b"flv")
    key1 = cache_key_for_source(flv)
    flv.write_bytes(b"flv-updated")
    key2 = cache_key_for_source(flv)
    assert key1 != key2


def test_cached_playback_invalidates_when_source_changes(tmp_path: Path, monkeypatch) -> None:
    from karaoke_blast.services import flv_compat as flv_compat_module

    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    monkeypatch.setattr(flv_compat_module, "flv_compat_cache_dir", lambda: cache_root)

    flv = tmp_path / "karaoke.flv"
    flv.write_bytes(b"original")
    key = cache_key_for_source(flv)
    entry = cache_entry_for_key(key)
    entry.directory.mkdir(parents=True)
    entry.playback_path.write_bytes(b"mp4")
    entry.meta_path.write_text(
        json.dumps(
            {
                "source_path": str(flv.resolve()),
                "source_size": flv.stat().st_size,
                "source_mtime_ns": flv.stat().st_mtime_ns,
            }
        ),
        encoding="utf-8",
    )
    assert cached_playback_path(flv) == entry.playback_path

    flv.write_bytes(b"changed")
    assert cached_playback_path(flv) is None


def test_plan_flv_playback_non_macos_plays_direct(tmp_path: Path) -> None:
    flv = tmp_path / "x.flv"
    flv.write_bytes(b"x")
    with patch.object(sys, "platform", "win32"):
        plan = plan_flv_playback(flv, compatibility_enabled=True)
    assert plan.action == FlvPlaybackAction.PLAY_DIRECT
    assert plan.vlc_path == flv


def test_plan_flv_playback_macos_cached(tmp_path: Path, monkeypatch) -> None:
    from karaoke_blast.services import flv_compat as flv_compat_module

    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    monkeypatch.setattr(flv_compat_module, "flv_compat_cache_dir", lambda: cache_root)

    flv = tmp_path / "song.flv"
    flv.write_bytes(b"data")
    key = cache_key_for_source(flv)
    entry = cache_entry_for_key(key)
    entry.directory.mkdir(parents=True)
    entry.playback_path.write_bytes(b"cached-mp4")
    entry.meta_path.write_text(
        json.dumps(
            {
                "source_path": str(flv.resolve()),
                "source_size": flv.stat().st_size,
                "source_mtime_ns": flv.stat().st_mtime_ns,
            }
        ),
        encoding="utf-8",
    )

    with patch.object(sys, "platform", "darwin"):
        plan = plan_flv_playback(flv, compatibility_enabled=True)
    assert plan.action == FlvPlaybackAction.PLAY_CACHED
    assert plan.vlc_path == entry.playback_path


def test_clear_flv_compat_cache_skips_excluded(tmp_path: Path, monkeypatch) -> None:
    from karaoke_blast.services import flv_compat as flv_compat_module

    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    monkeypatch.setattr(flv_compat_module, "flv_compat_cache_dir", lambda: cache_root)

    entry = cache_entry_for_key("abc123")
    entry.directory.mkdir(parents=True)
    entry.playback_path.write_bytes(b"mp4")

    removed, skipped = clear_flv_compat_cache(
        exclude_paths=frozenset({entry.playback_path.resolve()})
    )
    assert removed == 0
    assert skipped == 1
    assert entry.playback_path.is_file()

    removed2, skipped2 = clear_flv_compat_cache()
    assert removed2 == 1
    assert skipped2 == 0


@pytest.mark.skipif(resolve_ffmpeg_location() is None, reason="ffmpeg not installed")
def test_remux_flv_to_cache_stream_copy(tmp_path: Path, monkeypatch) -> None:
    from karaoke_blast.services import flv_compat as flv_compat_module

    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    monkeypatch.setattr(flv_compat_module, "flv_compat_cache_dir", lambda: cache_root)

    ffmpeg = resolve_ffmpeg_location()
    assert ffmpeg is not None
    source = tmp_path / "sample.flv"
    create = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=1:size=320x240:rate=10",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-shortest",
        "-f",
        "flv",
        str(source),
    ]
    import subprocess

    result = subprocess.run(create, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr

    original_bytes = source.read_bytes()
    out = remux_flv_to_cache(source)
    assert out.is_file()
    assert out.stat().st_size > 0
    assert source.read_bytes() == original_bytes
    out2 = remux_flv_to_cache(source)
    assert out2 == out
