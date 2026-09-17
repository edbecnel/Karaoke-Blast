"""Tests for Rumble yt-dlp option builder."""

from pathlib import Path

from karaoke_blast.services.rumble_download_worker import (
    _ytdlp_url_for_rumble,
    build_rumble_ydl_opts,
    downloaded_file_for,
    rumble_ytdlp_referer,
)


def test_rumble_ytdlp_referer_uses_embed_for_embed_downloads() -> None:
    page = "https://rumble.com/v1abc-slug.html"
    embed = "https://rumble.com/embed/v19kdz0/"
    assert rumble_ytdlp_referer(page, embed) == embed
    assert rumble_ytdlp_referer(page, page) == page


def test_build_rumble_ydl_opts_embed_referer() -> None:
    page = "https://rumble.com/v1abc-slug.html"
    embed = "https://rumble.com/embed/xyz/"
    opts = build_rumble_ydl_opts(page, download=True, ytdlp_url=embed)
    assert opts["http_headers"]["Referer"] == embed


def test_build_rumble_ydl_opts_omits_exported_cookies(monkeypatch) -> None:
    monkeypatch.setattr(
        "karaoke_blast.services.youtube_cookies.apply_youtube_cookies_opts",
        lambda opts: opts.update({"cookiefile": "/tmp/cookies.txt"}),
    )
    opts = build_rumble_ydl_opts("https://rumble.com/v1abc.html", download=True)
    assert "cookiefile" not in opts


def test_build_rumble_ydl_opts_referer_and_no_youtube_args(monkeypatch) -> None:
    monkeypatch.setattr(
        "karaoke_blast.services.rumble_download_worker.apply_yt_dlp_runtime_opts",
        lambda opts, **kwargs: opts.update({"js_runtimes": {"node": {}}}),
    )
    monkeypatch.setattr(
        "karaoke_blast.services.rumble_download_worker.resolve_ffmpeg_location",
        lambda: "/usr/bin/ffmpeg",
    )
    monkeypatch.setattr(
        "karaoke_blast.services.rumble_download_worker._impersonate_available",
        lambda: True,
    )

    page = "https://rumble.com/v1euzw6-test.html"
    opts = build_rumble_ydl_opts(page, download=True)

    assert opts["http_headers"]["Referer"] == page
    from yt_dlp.networking.impersonate import ImpersonateTarget

    assert opts["impersonate"] == ImpersonateTarget.from_str("chrome")
    assert opts["merge_output_format"] == "mp4"
    assert "cookiefile" not in opts
    assert "extractor_args" not in opts
    assert opts["ffmpeg_location"] == "/usr/bin/ffmpeg"


def test_build_rumble_ydl_opts_skip_download() -> None:
    opts = build_rumble_ydl_opts("https://rumble.com/v1abc.html", download=False)
    assert opts.get("skip_download") is True


def test_ytdlp_url_prefers_embed(monkeypatch) -> None:
    page = "https://rumble.com/vs6jry-slug.html"
    monkeypatch.setattr(
        "karaoke_blast.services.rumble_metadata.resolve_rumble_embed_id",
        lambda url: "abc123" if url == page else None,
    )
    assert (
        _ytdlp_url_for_rumble(page, "vpkdo2", page_video_id="vs6jry")
        == "https://rumble.com/embed/vpkdo2/"
    )
    assert (
        _ytdlp_url_for_rumble(page, "vs6jry", page_video_id="vs6jry")
        == "https://rumble.com/embed/abc123/"
    )
    assert (
        _ytdlp_url_for_rumble(page, None, page_video_id="vs6jry")
        == "https://rumble.com/embed/abc123/"
    )


def test_downloaded_file_for_does_not_match_unrelated_youtube(tmp_path: Path) -> None:
    unrelated = tmp_path / "Fantasy Island - Photographs [dQw4w9WgXcQ].mp4"
    unrelated.write_bytes(b"x")
    page = "https://rumble.com/vs6jry-slug.html"
    assert downloaded_file_for("vs6jry", page, tmp_path) is None
    rumble_file = tmp_path / "Karaoke [rumble:vs6jry].mp4"
    rumble_file.write_bytes(b"xx")
    assert downloaded_file_for("vs6jry", page, tmp_path) == rumble_file
