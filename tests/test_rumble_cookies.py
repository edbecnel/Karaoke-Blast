"""Tests for optional Rumble cookies.txt resolution."""

from pathlib import Path

from karaoke_blast.services.rumble_cookies import resolved_rumble_cookies_file
from karaoke_blast.storage.paths import default_rumble_cookies_file


def test_resolved_cookies_none_when_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "karaoke_blast.services.rumble_cookies.default_rumble_cookies_file",
        lambda: tmp_path / "rumble_cookies.txt",
    )
    assert resolved_rumble_cookies_file() is None


def test_resolved_cookies_when_file_nonempty(tmp_path, monkeypatch) -> None:
    path = tmp_path / "rumble_cookies.txt"
    path.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    monkeypatch.setattr(
        "karaoke_blast.services.rumble_cookies.default_rumble_cookies_file",
        lambda: path,
    )
    assert resolved_rumble_cookies_file() == path


def test_default_cookies_path_under_config_dir() -> None:
    path = default_rumble_cookies_file()
    assert path.name == "rumble_cookies.txt"
    assert path.parent.name in {"Karaoke Blast", "karaoke-blast"}
