"""FIFO queue of local video paths played outside the current playlist."""

from pathlib import Path


class PathQueue:
    """Queue of file paths for play-next outside the folder playlist."""

    def __init__(self) -> None:
        self._paths: list[Path] = []

    def enqueue(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if any(p.resolve() == resolved for p in self._paths):
            return False
        self._paths.append(resolved)
        return True

    def dequeue(self) -> Path | None:
        if not self._paths:
            return None
        return self._paths.pop(0)

    def remove(self, path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        self._paths = [p for p in self._paths if p.resolve() != resolved]

    def clear(self) -> None:
        self._paths.clear()

    def __len__(self) -> int:
        return len(self._paths)
