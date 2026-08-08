"""Persist recently opened folders."""

import json
import logging
from pathlib import Path

from karaoke_blast.storage.path_filters import is_transient_path
from karaoke_blast.storage.paths import config_dir

logger = logging.getLogger(__name__)

MAX_HISTORY = 20


def _history_file() -> Path:
    return config_dir() / "folder_history.json"


class FolderHistory:
    """Read and write the list of recently opened folders."""

    def __init__(self) -> None:
        self._paths: list[Path] = []
        self.load()

    def load(self) -> None:
        path = _history_file()
        if not path.exists():
            self._paths = []
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw = data.get("folders", [])
            self._paths = [Path(p) for p in raw if isinstance(p, str)]
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load folder history: %s", exc)
            self._paths = []
        self._prune_invalid()

    def save(self) -> None:
        data = {"folders": [str(p) for p in self._paths]}
        try:
            _history_file().write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not save folder history: %s", exc)

    def add(self, folder: Path) -> None:
        folder = folder.resolve()
        if is_transient_path(folder):
            return
        self._paths = [p for p in self._paths if p != folder]
        self._paths.insert(0, folder)
        self._paths = self._paths[:MAX_HISTORY]
        self.save()

    def remove(self, folder: Path) -> None:
        folder = folder.resolve()
        self._paths = [p for p in self._paths if p != folder]
        self.save()

    def folders(self) -> list[Path]:
        self._prune_invalid()
        return list(self._paths)

    def _prune_invalid(self) -> None:
        keep = [
            path
            for path in self._paths
            if path.is_dir() and not is_transient_path(path)
        ]
        if keep != self._paths:
            self._paths = keep
            self.save()
