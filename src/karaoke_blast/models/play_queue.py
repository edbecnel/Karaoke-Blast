"""FIFO queue of playlist indices to play after the current song."""


class PlayQueue:
    """Queue of playlist indices played before resuming normal order."""

    def __init__(self) -> None:
        self._indices: list[int] = []

    def enqueue(self, index: int) -> bool:
        """Add *index* to the queue. Returns False if already queued."""
        if index in self._indices:
            return False
        self._indices.append(index)
        return True

    def dequeue(self) -> int | None:
        if not self._indices:
            return None
        return self._indices.pop(0)

    def remove(self, index: int) -> None:
        self._indices = [i for i in self._indices if i != index]

    def clear(self) -> None:
        self._indices.clear()

    def set_order(self, indices: list[int]) -> None:
        """Replace queue order from a reordered list of playlist indices."""
        if set(indices) == set(self._indices) and len(indices) == len(self._indices):
            self._indices = list(indices)
            return
        # Drag-reorder UI omits the now-playing row even if that index is still stored.
        if set(indices).issubset(set(self._indices)):
            self._indices = list(indices)
            return

    def __len__(self) -> int:
        return len(self._indices)

    def indices(self) -> list[int]:
        return list(self._indices)

    def contains(self, index: int) -> bool:
        return index in self._indices
