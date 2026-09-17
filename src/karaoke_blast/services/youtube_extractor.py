"""Shared yt-dlp YouTube extractor settings."""

from __future__ import annotations

from importlib.util import find_spec
from typing import Any

from karaoke_blast.utils.runtime_deps import resolve_js_runtimes

# Try alternate YouTube clients when the default session has no progressive URLs.
YOUTUBE_PLAYER_CLIENT_FALLBACKS: tuple[list[str], ...] = (
    ["default", "-android_vr", "-web_safari"],
    ["android", "web"],
    ["ios", "mweb"],
    ["web"],
)


def _yt_dlp_ejs_available() -> bool:
    return find_spec("yt_dlp_ejs") is not None


def apply_yt_dlp_runtime_opts(opts: dict[str, Any], *, use_cookies: bool = True) -> None:
    from karaoke_blast.services.youtube_cookies import apply_youtube_cookies_opts

    js_runtimes = resolve_js_runtimes()
    if js_runtimes:
        opts["js_runtimes"] = js_runtimes
    if not _yt_dlp_ejs_available():
        opts["remote_components"] = ["ejs:github"]
    if use_cookies:
        apply_youtube_cookies_opts(opts)


def youtube_extractor_args(player_client: list[str]) -> dict[str, dict[str, list[str]]]:
    return {"youtube": {"player_client": player_client}}
