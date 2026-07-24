"""Persist application settings."""

import json
import logging
from pathlib import Path

from karaoke_blast.storage.paths import config_dir

logger = logging.getLogger(__name__)


def _settings_file() -> Path:
    return config_dir() / "settings.json"


class Settings:
    """Read and write user preferences."""

    def __init__(self) -> None:
        self.controls_auto_hide: bool = True
        self.volume: int = 80
        self.muted: bool = False
        self.launch_window_width: int | None = None
        self.launch_window_height: int | None = None
        self.load()

    def load(self) -> None:
        path = _settings_file()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data.get("controls_auto_hide"), bool):
                self.controls_auto_hide = data["controls_auto_hide"]
            volume = data.get("volume")
            if isinstance(volume, int) and 0 <= volume <= 100:
                self.volume = volume
            if isinstance(data.get("muted"), bool):
                self.muted = data["muted"]
            width = data.get("launch_window_width")
            height = data.get("launch_window_height")
            if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
                self.launch_window_width = width
                self.launch_window_height = height
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load settings: %s", exc)

    def save(self) -> None:
        data = {
            "controls_auto_hide": self.controls_auto_hide,
            "volume": self.volume,
            "muted": self.muted,
            "launch_window_width": self.launch_window_width,
            "launch_window_height": self.launch_window_height,
        }
        try:
            _settings_file().write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            logger.warning("Could not save settings: %s", exc)
