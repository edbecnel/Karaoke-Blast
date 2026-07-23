"""Scan a folder for video files."""

from pathlib import Path

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v")


def scan_videos(folder: Path, *, recursive: bool = False) -> list[Path]:
    """Return video files in *folder* (unsorted).

    By default only the immediate folder contents are scanned. Set *recursive*
    to include nested subfolders (future use).
    """
    folder = folder.resolve()
    if not folder.is_dir():
        return []

    paths: list[Path] = []
    iterator = folder.rglob("*") if recursive else folder.iterdir()

    for entry in iterator:
        if entry.is_file() and entry.suffix.lower() in VIDEO_EXTENSIONS:
            paths.append(entry)

    return paths
