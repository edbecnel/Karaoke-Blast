"""Persist per-folder playback state (queue and current song)."""

import json
import logging
from pathlib import Path

from karaoke_blast.storage.paths import config_dir

logger = logging.getLogger(__name__)


def _state_file() -> Path:
    return config_dir() / "folder_queues.json"


class FolderQueues:
    """Read and write queue and current-song state keyed by folder."""

    def __init__(self) -> None:
        self._state: dict[str, dict[str, object]] = {}
        self.load()

    def load(self) -> None:
        path = _state_file()
        if not path.exists():
            self._state = {}
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw = data.get("queues", {})
            if not isinstance(raw, dict):
                self._state = {}
                return
            self._state = {}
            for folder, entry in raw.items():
                if not isinstance(folder, str):
                    continue
                if isinstance(entry, list):
                    self._state[folder] = {
                        "queue": [p for p in entry if isinstance(p, str)],
                        "current": None,
                    }
                elif isinstance(entry, dict):
                    queue = entry.get("queue", [])
                    current = entry.get("current")
                    self._state[folder] = {
                        "queue": [p for p in queue if isinstance(p, str)]
                        if isinstance(queue, list)
                        else [],
                        "current": current if isinstance(current, str) else None,
                    }
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load folder playback state: %s", exc)
            self._state = {}

    def save(self) -> None:
        data = {"queues": self._state}
        try:
            _state_file().write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            logger.warning("Could not save folder playback state: %s", exc)

    def _key(self, folder: Path) -> str:
        return str(folder.resolve())

    def get_queue(self, folder: Path) -> list[Path]:
        entry = self._state.get(self._key(folder), {})
        raw = entry.get("queue", []) if isinstance(entry, dict) else []
        return [Path(p) for p in raw if isinstance(p, str)]

    def get_current(self, folder: Path) -> Path | None:
        entry = self._state.get(self._key(folder), {})
        if not isinstance(entry, dict):
            return None
        current = entry.get("current")
        return Path(current) if isinstance(current, str) else None

    def set(
        self,
        folder: Path,
        *,
        queue: list[Path],
        current: Path | None,
    ) -> None:
        key = self._key(folder)
        queue_paths = [str(path.resolve()) for path in queue]
        current_path = str(current.resolve()) if current is not None else None
        if not queue_paths and current_path is None:
            self._state.pop(key, None)
        else:
            self._state[key] = {"queue": queue_paths, "current": current_path}
        self.save()

    def get(self, folder: Path) -> list[Path]:
        """Return the saved queue paths for *folder*."""
        return self.get_queue(folder)
