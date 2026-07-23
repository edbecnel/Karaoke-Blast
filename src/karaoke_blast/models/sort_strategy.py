"""Sort strategies for video playlists."""

from enum import Enum
from pathlib import Path


class SortStrategy(Enum):
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    DATE_ASC = "date_asc"
    DATE_DESC = "date_desc"

    @property
    def label(self) -> str:
        return _LABELS[self]


_LABELS = {
    SortStrategy.NAME_ASC: "Name (A → Z)",
    SortStrategy.NAME_DESC: "Name (Z → A)",
    SortStrategy.DATE_ASC: "Date (Oldest first)",
    SortStrategy.DATE_DESC: "Date (Newest first)",
}


def sort_paths(paths: list[Path], strategy: SortStrategy) -> list[Path]:
    """Return a new list of paths sorted by *strategy*."""
    if strategy == SortStrategy.NAME_ASC:
        return sorted(paths, key=lambda p: p.name.lower())
    if strategy == SortStrategy.NAME_DESC:
        return sorted(paths, key=lambda p: p.name.lower(), reverse=True)
    if strategy == SortStrategy.DATE_ASC:
        return sorted(paths, key=lambda p: p.stat().st_mtime)
    if strategy == SortStrategy.DATE_DESC:
        return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)
    return list(paths)
