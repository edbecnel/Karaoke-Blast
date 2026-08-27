"""Application config directory paths."""

import os
import sys
from pathlib import Path


def config_dir() -> Path:
    if sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "Karaoke Blast"
    elif sys.platform == "win32":
        path = Path(os.environ.get("APPDATA", Path.home())) / "Karaoke Blast"
    else:
        path = Path.home() / ".config" / "karaoke-blast"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_downloads_dir() -> Path:
    """Default directory for YouTube videos downloaded for offline playback."""
    path = config_dir() / "youtube-downloads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_default_downloads_dir(path: Path) -> bool:
    """Return True when *path* is the built-in YouTube downloads folder."""
    return path.resolve() == default_downloads_dir().resolve()


def pinned_downloads_folder_label(path: Path) -> str:
    """Label for the pinned default downloads folder on the start screen."""
    if is_default_downloads_dir(path):
        return "YouTube Downloads"
    return path.name or str(path)
