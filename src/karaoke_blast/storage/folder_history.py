"""Persist recently opened folders."""

import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_HISTORY = 20


def _config_dir() -> Path:
    if sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "Karaoke Blast"
    elif sys.platform == "win32":
        path = Path(os.environ.get("APPDATA", Path.home())) / "Karaoke Blast"
    else:
        path = Path.home() / ".config" / "karaoke-blast"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _history_file() -> Path:
    return _config_dir() / "folder_history.json"


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
        self._prune_missing()

    def save(self) -> None:
        data = {"folders": [str(p) for p in self._paths]}
        try:
            _history_file().write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not save folder history: %s", exc)

    def add(self, folder: Path) -> None:
        folder = folder.resolve()
        self._paths = [p for p in self._paths if p != folder]
        self._paths.insert(0, folder)
        self._paths = self._paths[:MAX_HISTORY]
        self.save()

    def folders(self) -> list[Path]:
        self._prune_missing()
        return list(self._paths)

    def _prune_missing(self) -> None:
        existing = [p for p in self._paths if p.is_dir()]
        if len(existing) != len(self._paths):
            self._paths = existing
            self.save()
