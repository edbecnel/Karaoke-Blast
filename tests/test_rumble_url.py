"""Tests for Rumble URL parsing."""

from karaoke_blast.utils.rumble_url import parse_rumble_url


def test_parse_rumble_watch_page() -> None:
    info = parse_rumble_url("https://rumble.com/v1euzw6-my-slug.html")
    assert info is not None
    assert info.page_video_id == "v1euzw6"
    assert "/v1euzw6-" in info.page_url


def test_parse_rumble_watch_page_vs_prefix() -> None:
    info = parse_rumble_url(
        "https://rumble.com/vs6jry-america-ventura-highway-acoustic-guitar-karaoke-songs-with-lyrics.html"
    )
    assert info is not None
    assert info.page_video_id == "vs6jry"
    assert info.embed_id is None


def test_parse_rumble_embed_url() -> None:
    info = parse_rumble_url("https://rumble.com/embed/v1c8tyy/")
    assert info is not None
    assert info.page_video_id == "v1c8tyy"
    assert info.embed_id == "v1c8tyy"


def test_parse_rejects_non_rumble() -> None:
    assert parse_rumble_url("https://www.youtube.com/watch?v=abc") is None
    assert parse_rumble_url("not a url") is None
