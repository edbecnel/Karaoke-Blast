"""Tests for YouTube stream format fallbacks."""

from karaoke_blast.services.youtube_extractor import YOUTUBE_PLAYER_CLIENT_FALLBACKS
from karaoke_blast.services.youtube_stream import (
    STREAM_FORMAT_FALLBACKS,
    _http_headers_from_info,
    _stream_url_is_readable,
)


def test_stream_format_fallbacks_non_empty_and_permissive_last() -> None:
    assert STREAM_FORMAT_FALLBACKS
    assert STREAM_FORMAT_FALLBACKS[-1] == "best"


def test_player_client_fallbacks_include_android_web() -> None:
    assert YOUTUBE_PLAYER_CLIENT_FALLBACKS
    assert ["android", "web"] in YOUTUBE_PLAYER_CLIENT_FALLBACKS


def test_http_headers_add_referer_from_webpage_url() -> None:
    headers = _http_headers_from_info(
        {"webpage_url": "https://www.youtube.com/watch?v=abc"},
        watch_url="https://www.youtube.com/watch?v=abc",
    )
    assert headers["Referer"] == "https://www.youtube.com/watch?v=abc"


def test_stream_url_is_readable_rejects_http_403() -> None:
    assert (
        _stream_url_is_readable(
            "https://example.com/video.mp4",
            {},
        )
        is False
    )
