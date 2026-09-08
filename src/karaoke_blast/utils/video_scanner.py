"""Scan a folder for video and audio media files."""

from pathlib import Path

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v")
AUDIO_EXTENSIONS = (".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus", ".wma")
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS + AUDIO_EXTENSIONS


def is_audio_file(path: Path) -> bool:
    """Return True if *path* has a supported audio extension."""
    return path.suffix.lower() in AUDIO_EXTENSIONS


def is_macos_appledouble_file(path: Path) -> bool:
    """Return True for macOS AppleDouble sidecar files (``._`` prefix).

    These are created when copying files to non-native filesystems (e.g. exFAT
    on external drives) and are not playable media.
    """
    return path.name.startswith("._")


def _is_media_file(path: Path, *, hide_appledouble_files: bool = True) -> bool:
    if not path.is_file() or path.suffix.lower() not in MEDIA_EXTENSIONS:
        return False
    if hide_appledouble_files and is_macos_appledouble_file(path):
        return False
    return True


def scan_videos(
    folder: Path, *, recursive: bool = False, hide_appledouble_files: bool = True
) -> list[Path]:
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
        if _is_media_file(entry, hide_appledouble_files=hide_appledouble_files):
            paths.append(entry)

    return paths


def folder_has_videos(folder: Path, *, hide_appledouble_files: bool = True) -> bool:
    """Return True if *folder* or any descendant contains a supported media file."""
    folder = folder.resolve()
    if not folder.is_dir():
        return False

    for entry in folder.rglob("*"):
        if _is_media_file(entry, hide_appledouble_files=hide_appledouble_files):
            return True
    return False


def child_folders_with_videos(
    folder: Path, *, hide_appledouble_files: bool = True
) -> list[Path]:
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
        if entry.is_dir() and folder_has_videos(
            entry, hide_appledouble_files=hide_appledouble_files
        ):
            children.append(entry)

    children.sort(key=lambda path: path.name.lower())
    return children
