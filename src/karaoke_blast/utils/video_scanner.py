"""Scan a folder for video and audio media files."""

from pathlib import Path

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v")
AUDIO_EXTENSIONS = (".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus", ".wma")
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS + AUDIO_EXTENSIONS


def is_audio_file(path: Path) -> bool:
    """Return True if *path* has a supported audio extension."""
    return path.suffix.lower() in AUDIO_EXTENSIONS


def scan_videos(folder: Path, *, recursive: bool = False) -> list[Path]:
    """Return media files in *folder* (unsorted).

    By default only the immediate folder contents are scanned. Set *recursive*
    to include nested subfolders.
    """
    folder = folder.resolve()
    if not folder.is_dir():
        return []

    paths: list[Path] = []
    iterator = folder.rglob("*") if recursive else folder.iterdir()

    for entry in iterator:
        if entry.is_file() and entry.suffix.lower() in MEDIA_EXTENSIONS:
            paths.append(entry)

    return paths


def folder_has_videos(folder: Path) -> bool:
    """Return True if *folder* or any descendant contains a supported media file."""
    folder = folder.resolve()
    if not folder.is_dir():
        return False

    for entry in folder.rglob("*"):
        if entry.is_file() and entry.suffix.lower() in MEDIA_EXTENSIONS:
            return True
    return False


def child_folders_with_videos(folder: Path) -> list[Path]:
    """Return immediate subfolders of *folder* that contain media somewhere underneath."""
    folder = folder.resolve()
    if not folder.is_dir():
        return []

    children: list[Path] = []
    try:
        entries = list(folder.iterdir())
    except OSError:
        return []

    for entry in entries:
        if entry.is_dir() and folder_has_videos(entry):
            children.append(entry)

    children.sort(key=lambda path: path.name.lower())
    return children
