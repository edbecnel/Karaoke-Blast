#!/usr/bin/env python3
"""Fail installer builds if the bundled Python runtime lacks required packages."""

from __future__ import annotations

import sys


def main() -> int:
    errors: list[str] = []

    try:
        import curl_cffi  # noqa: F401
    except ImportError:
        errors.append(
            "curl_cffi is not installed (required for Rumble browser impersonation)"
        )

    try:
        from yt_dlp.networking.impersonate import ImpersonateTarget

        ImpersonateTarget.from_str("chrome")
    except ImportError:
        errors.append("yt-dlp impersonation support is not installed")
    except (TypeError, ValueError) as exc:
        errors.append(f"yt-dlp Chrome impersonation target failed: {exc}")

    try:
        from karaoke_blast.services.rumble_download_worker import (
            _apply_rumble_impersonate,
            _impersonate_available,
        )

        if not _impersonate_available():
            errors.append("curl_cffi is installed but impersonation is unavailable")
        else:
            opts: dict[str, object] = {}
            _apply_rumble_impersonate(opts)
            if "impersonate" not in opts:
                errors.append("Rumble yt-dlp options did not set impersonate")
    except ImportError as exc:
        errors.append(f"karaoke_blast is not importable: {exc}")

    if errors:
        for message in errors:
            print(f"verify-bundled-python-deps: {message}", file=sys.stderr)
        return 1

    print(
        "verify-bundled-python-deps: OK "
        "(curl_cffi, yt-dlp impersonation, karaoke_blast)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
