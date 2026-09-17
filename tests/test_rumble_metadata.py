"""Tests for Rumble embed id parsing from page HTML and yt-dlp info."""

from karaoke_blast.services.rumble_metadata import (
    _embed_id_from_html,
    _embed_id_from_info_dict,
)


def test_embed_id_from_embed_url_json() -> None:
    html = '{"embedUrl":"https://rumble.com/embed/vpkdo2/","title":"Karaoke"}'
    assert _embed_id_from_html(html) == "vpkdo2"


def test_embed_id_prefers_last_when_multiple() -> None:
    html = "/embed/vs6jry/ other /embed/vpkdo2/"
    assert _embed_id_from_html(html) == "vpkdo2"


def test_embed_id_from_ytdlp_process_false_result() -> None:
    info = {
        "ie_key": "RumbleEmbed",
        "url": "https://rumble.com/embed/vpkdo2",
        "id": None,
    }
    assert _embed_id_from_info_dict(info) == "vpkdo2"
