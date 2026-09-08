"""Tests for media folder scanning."""

from pathlib import Path

from karaoke_blast.utils.video_scanner import scan_videos


def test_scan_videos_skips_macos_appledouble_files_by_default(tmp_path: Path) -> None:
    (tmp_path / "Episode 1.mp4").write_bytes(b"video")
    (tmp_path / "._Episode 1.mp4").write_bytes(b"metadata")

    paths = scan_videos(tmp_path)

    assert paths == [tmp_path / "Episode 1.mp4"]


def test_scan_videos_includes_appledouble_files_when_disabled(tmp_path: Path) -> None:
    (tmp_path / "Episode 1.mp4").write_bytes(b"video")
    appledouble = tmp_path / "._Episode 1.mp4"
    appledouble.write_bytes(b"metadata")

    paths = scan_videos(tmp_path, hide_appledouble_files=False)

    assert set(paths) == {tmp_path / "Episode 1.mp4", appledouble}
