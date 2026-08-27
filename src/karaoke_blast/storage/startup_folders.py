"""Build recent and pinned folder lists for the startup screen."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from karaoke_blast.storage.paths import is_default_downloads_dir, pinned_downloads_folder_label


@dataclass(frozen=True)
class StartupFolderLists:
    recent: list[Path]
    pinned: list[Path]
    pinned_label: str | None


def startup_folder_lists(
    folder_history: list[Path],
    downloads_dir: Path,
) -> StartupFolderLists:
    """Return folder lists for the startup screen and folder menus."""
    downloads = downloads_dir.resolve()
    if is_default_downloads_dir(downloads_dir):
        recent = [folder for folder in folder_history if folder.resolve() != downloads]
        return StartupFolderLists(
            recent=recent,
            pinned=[downloads_dir],
            pinned_label=pinned_downloads_folder_label(downloads_dir),
        )
    return StartupFolderLists(
        recent=list(folder_history),
        pinned=[],
        pinned_label=None,
    )
