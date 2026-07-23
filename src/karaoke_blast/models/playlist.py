"""Playlist model — ordered list of video paths with navigation."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Playlist:
    paths: list[Path] = field(default_factory=list)
    index: int = 0

    @property
    def count(self) -> int:
        return len(self.paths)

    @property
    def position(self) -> int:
        """1-based position for display."""
        return self.index + 1 if self.paths else 0

    def current(self) -> Path | None:
        if not self.paths or self.index >= len(self.paths):
            return None
        return self.paths[self.index]

    def has_next(self) -> bool:
        return self.index + 1 < len(self.paths)

    def has_previous(self) -> bool:
        return self.index > 0

    def next(self) -> Path | None:
        if not self.has_next():
            return None
        self.index += 1
        return self.current()

    def previous(self) -> Path | None:
        if not self.has_previous():
            return None
        self.index -= 1
        return self.current()

    def go_to(self, index: int) -> Path | None:
        if index < 0 or index >= len(self.paths):
            return None
        self.index = index
        return self.current()

    def reorder(self, paths: list[Path], *, keep_path: Path | None = None) -> None:
        """Replace paths and preserve position of *keep_path* (or current song)."""
        anchor = keep_path or self.current()
        self.paths = paths
        if anchor is not None and anchor in paths:
            self.index = paths.index(anchor)
        elif paths:
            self.index = min(self.index, len(paths) - 1)
        else:
            self.index = 0
