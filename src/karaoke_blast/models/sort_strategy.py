"""Sort strategies for video playlists."""

from collections.abc import Callable
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


def sort_paths(
    paths: list[Path],
    strategy: SortStrategy,
    *,
    name_key: Callable[[Path], str] | None = None,
) -> list[Path]:
    """Return a new list of paths sorted by *strategy*.

    *name_key* supplies the A→Z / Z→A comparison string (display label).
    When omitted, the file name is used.
    """
    if strategy in {SortStrategy.NAME_ASC, SortStrategy.NAME_DESC}:
        resolve_name = name_key if name_key is not None else (lambda path: path.name)

        def _name_sort_key(path: Path) -> str:
            try:
                return resolve_name(path).casefold()
            except OSError:
                return path.name.casefold()

        return sorted(
            paths,
            key=_name_sort_key,
            reverse=strategy == SortStrategy.NAME_DESC,
        )
    if strategy == SortStrategy.DATE_ASC:
        return sorted(paths, key=lambda p: p.stat().st_mtime)
    if strategy == SortStrategy.DATE_DESC:
        return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)
    return list(paths)
