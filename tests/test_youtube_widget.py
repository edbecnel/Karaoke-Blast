"""Tests for YouTube embed helper messages."""

from karaoke_blast.player.youtube_widget import _youtube_player_error_message


def test_youtube_player_error_message_known_codes() -> None:
    assert "owner" in _youtube_player_error_message(101).lower()
    assert _youtube_player_error_message(153).startswith("YouTube")


def test_youtube_player_error_message_unknown_code() -> None:
    assert _youtube_player_error_message(999) == "YouTube playback error (999)."
