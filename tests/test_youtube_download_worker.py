"""Tests for YouTube download format fallback logic."""

from karaoke_blast.services.youtube_download_worker import (
    DOWNLOAD_FORMAT_FALLBACKS,
    _friendly_download_error,
    _is_retryable_format_error,
)


class _FakeDownloadError(Exception):
    pass


def test_is_retryable_format_error_matches_not_available() -> None:
    exc = _FakeDownloadError(
        "ERROR: [youtube] abc: Requested format is not available. "
        "Use --list-formats for a list of available formats"
    )
    assert _is_retryable_format_error(exc) is True


def test_is_retryable_format_error_rejects_unrelated_errors() -> None:
    assert _is_retryable_format_error(RuntimeError("ffmpeg is not installed")) is False


def test_friendly_download_error_for_format_failure() -> None:
    exc = _FakeDownloadError("Requested format is not available")
    assert _friendly_download_error(exc) == (
        "Could not find a downloadable format for this video."
    )


def test_download_format_fallbacks_non_empty_and_permissive_last() -> None:
    assert DOWNLOAD_FORMAT_FALLBACKS
    last = DOWNLOAD_FORMAT_FALLBACKS[-1]
    assert last in {"best", "bv*+ba/b"}
