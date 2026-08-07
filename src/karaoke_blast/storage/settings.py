"""Persist application settings."""

import json
import logging
from pathlib import Path

from karaoke_blast.storage.paths import config_dir, default_downloads_dir
from karaoke_blast.utils.filename_rename import FilenameFormat

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
        self.queue_section_ratio: float | None = None
        self.youtube_search_backend: str = "yt-dlp"
        self.youtube_api_key: str | None = None
        self.youtube_append_karaoke: bool = True
        self.youtube_downloads_dir: str | None = None
        self.filename_rename_format: FilenameFormat = FilenameFormat()
        self.filename_rename_skip_canonical: bool = True
        self.filename_rename_auto_fill_slots: bool = False
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
            ratio = data.get("queue_section_ratio")
            if isinstance(ratio, (int, float)) and 0.1 <= float(ratio) <= 0.85:
                self.queue_section_ratio = float(ratio)
            backend = data.get("youtube_search_backend")
            if backend in {"yt-dlp", "api"}:
                self.youtube_search_backend = backend
            api_key = data.get("youtube_api_key")
            if isinstance(api_key, str) and api_key.strip():
                self.youtube_api_key = api_key.strip()
            elif api_key is None:
                self.youtube_api_key = None
            if isinstance(data.get("youtube_append_karaoke"), bool):
                self.youtube_append_karaoke = data["youtube_append_karaoke"]
            downloads_dir = data.get("youtube_downloads_dir")
            if isinstance(downloads_dir, str) and downloads_dir.strip():
                self.youtube_downloads_dir = downloads_dir.strip()
            elif downloads_dir is None:
                self.youtube_downloads_dir = None
            rename_data = data.get("filename_rename")
            if isinstance(rename_data, dict):
                self.filename_rename_format = FilenameFormat.from_dict(rename_data)
            if isinstance(data.get("filename_rename_skip_canonical"), bool):
                self.filename_rename_skip_canonical = data["filename_rename_skip_canonical"]
            if isinstance(data.get("filename_rename_auto_fill_slots"), bool):
                self.filename_rename_auto_fill_slots = data["filename_rename_auto_fill_slots"]
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load settings: %s", exc)

    def save(self) -> None:
        data = {
            "controls_auto_hide": self.controls_auto_hide,
            "volume": self.volume,
            "muted": self.muted,
            "launch_window_width": self.launch_window_width,
            "launch_window_height": self.launch_window_height,
            "queue_section_ratio": self.queue_section_ratio,
            "youtube_search_backend": self.youtube_search_backend,
            "youtube_api_key": self.youtube_api_key,
            "youtube_append_karaoke": self.youtube_append_karaoke,
            "youtube_downloads_dir": self.youtube_downloads_dir,
            "filename_rename": self.filename_rename_format.to_dict(),
            "filename_rename_skip_canonical": self.filename_rename_skip_canonical,
            "filename_rename_auto_fill_slots": self.filename_rename_auto_fill_slots,
        }
        try:
            _settings_file().write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            logger.warning("Could not save settings: %s", exc)

    def resolved_youtube_downloads_dir(self) -> Path:
        """Return the configured YouTube downloads folder, or the default."""
        if self.youtube_downloads_dir:
            path = Path(self.youtube_downloads_dir)
            if path.is_dir():
                return path
            logger.warning(
                "Configured YouTube downloads folder is unavailable, using default: %s",
                self.youtube_downloads_dir,
            )
        return default_downloads_dir()

    def set_youtube_downloads_dir(self, path: Path) -> None:
        """Persist a custom YouTube downloads folder."""
        resolved = path.resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        self.youtube_downloads_dir = str(resolved)
        self.save()
