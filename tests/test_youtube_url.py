"""Tests for YouTube URL / video ID parsing."""

from karaoke_blast.utils.youtube_url import extract_video_id

_VIDEO = "0HDul-dUmk4"


def test_extract_raw_video_id() -> None:
    assert extract_video_id(_VIDEO) == _VIDEO


def test_extract_watch_url() -> None:
    assert extract_video_id(f"https://www.youtube.com/watch?v={_VIDEO}") == _VIDEO


def test_extract_live_url() -> None:
    assert extract_video_id(f"https://www.youtube.com/live/{_VIDEO}") == _VIDEO


def test_extract_search_bar_style_without_scheme() -> None:
    assert extract_video_id(f"www.youtube.com/watch?v={_VIDEO}") == _VIDEO


def test_extract_markdown_link() -> None:
    url = f"https://youtu.be/{_VIDEO}"
    assert extract_video_id(f"[song]({url})") == _VIDEO


def test_extract_nocookie_embed() -> None:
    assert (
        extract_video_id(f"https://www.youtube-nocookie.com/embed/{_VIDEO}")
        == _VIDEO
    )
