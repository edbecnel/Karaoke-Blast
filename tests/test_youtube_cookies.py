"""Tests for optional YouTube cookies.txt resolution."""

from pathlib import Path

from karaoke_blast.services.youtube_cookies import resolved_youtube_cookies_file
from karaoke_blast.storage.paths import default_youtube_cookies_file


def test_resolved_cookies_none_when_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "karaoke_blast.services.youtube_cookies.default_youtube_cookies_file",
        lambda: tmp_path / "youtube_cookies.txt",
    )
    assert resolved_youtube_cookies_file() is None


def test_resolved_cookies_when_file_nonempty(tmp_path, monkeypatch) -> None:
    path = tmp_path / "youtube_cookies.txt"
    path.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    monkeypatch.setattr(
        "karaoke_blast.services.youtube_cookies.default_youtube_cookies_file",
        lambda: path,
    )
    assert resolved_youtube_cookies_file() == path


def test_default_cookies_path_under_config_dir() -> None:
    path = default_youtube_cookies_file()
    assert path.name == "youtube_cookies.txt"
    assert path.parent.name == "Karaoke Blast" or path.parent.name == "karaoke-blast"
