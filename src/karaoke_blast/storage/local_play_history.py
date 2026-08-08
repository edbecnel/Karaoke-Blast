"""Persist recently played local video paths."""

import json
import logging
from pathlib import Path

from karaoke_blast.storage.paths import config_dir

logger = logging.getLogger(__name__)

MAX_HISTORY = 200


def _history_file() -> Path:
    return config_dir() / "local_play_history.json"


class LocalPlayHistory:
    """Read and write the list of recently played local videos."""

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
            raw = data.get("paths", [])
            self._paths = [Path(p) for p in raw if isinstance(p, str)]
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load local play history: %s", exc)
            self._paths = []

    def save(self) -> None:
        data = {"paths": [str(p) for p in self._paths]}
        try:
            _history_file().write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not save local play history: %s", exc)

    def add(self, path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        kept: list[Path] = []
        for existing in self._paths:
            try:
                if existing.resolve() == resolved:
                    continue
            except OSError:
                if existing == resolved:
                    continue
            kept.append(existing)
        self._paths = kept
        self._paths.insert(0, resolved)
        self._paths = self._paths[:MAX_HISTORY]
        self.save()

    def remove(self, path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        kept: list[Path] = []
        for existing in self._paths:
            try:
                if existing.resolve() == resolved:
                    continue
            except OSError:
                if existing == resolved:
                    continue
            kept.append(existing)
        self._paths = kept
        self.save()

    def clear(self) -> None:
        self._paths.clear()
        self.save()

    def paths(self) -> list[Path]:
        return list(self._paths)
