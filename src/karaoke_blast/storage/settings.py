"""Persist application settings."""

import json
import logging
from pathlib import Path

from karaoke_blast.storage.paths import config_dir, default_downloads_dir
from karaoke_blast.utils.filename_rename import FilenameFormat
from karaoke_blast.utils.song_display import (
    DEFAULT_DISPLAY_FORMAT,
    DISPLAY_MODE_FILENAME,
    DISPLAY_MODE_METADATA,
    DisplayFormat,
)
from karaoke_blast.utils.video_types import (
    BUILTIN_ANY_ID,
    BUILTIN_SONGS_ID,
    YOUTUBE_APPEND_KARAOKE,
    VideoTypeProfile,
    active_video_type,
    default_video_types,
    normalize_video_types,
    find_video_type,
    migrate_video_types,
    reset_builtin_video_type,
)

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
        self.metadata_comment_slot_indices: list[int] | None = None
        self.metadata_auto_fill_slots: bool = False
        self.metadata_skip_tagged: bool = True
        self.song_display_mode: str = DISPLAY_MODE_FILENAME
        self.song_display_format: DisplayFormat = DEFAULT_DISPLAY_FORMAT.copy()
        self.video_types: list[VideoTypeProfile] = default_video_types()
        self.active_video_type_id: str = BUILTIN_ANY_ID
        self.library_flat_browse: bool = False
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
            comment_indices = data.get("metadata_comment_slot_indices")
            if comment_indices is None:
                self.metadata_comment_slot_indices = None
            elif isinstance(comment_indices, list):
                parsed: list[int] = []
                for item in comment_indices:
                    if isinstance(item, int) and 0 <= item < 4 and item not in parsed:
                        parsed.append(item)
                self.metadata_comment_slot_indices = parsed
            if isinstance(data.get("metadata_auto_fill_slots"), bool):
                self.metadata_auto_fill_slots = data["metadata_auto_fill_slots"]
            if isinstance(data.get("metadata_skip_tagged"), bool):
                self.metadata_skip_tagged = data["metadata_skip_tagged"]
            display_mode = data.get("song_display_mode")
            if display_mode in {DISPLAY_MODE_FILENAME, DISPLAY_MODE_METADATA}:
                self.song_display_mode = display_mode
            display_format = data.get("song_display_format")
            if isinstance(display_format, dict):
                self.song_display_format = DisplayFormat.from_dict(display_format)
            raw_video_types = data.get("video_types")
            if isinstance(raw_video_types, list) and raw_video_types:
                profiles: list[VideoTypeProfile] = []
                for entry in raw_video_types:
                    if isinstance(entry, dict):
                        profiles.append(VideoTypeProfile.from_dict(entry))
                if profiles:
                    self.video_types = normalize_video_types(profiles)
            else:
                self.video_types = migrate_video_types(
                    existing_rename_format=self.filename_rename_format,
                    existing_comment_indices=self.metadata_comment_slot_indices,
                )
            active_id = data.get("active_video_type_id")
            if isinstance(active_id, str) and active_id.strip():
                self.active_video_type_id = active_id.strip()
            if find_video_type(self.video_types, self.active_video_type_id) is None:
                self.active_video_type_id = BUILTIN_SONGS_ID
            if isinstance(data.get("library_flat_browse"), bool):
                self.library_flat_browse = data["library_flat_browse"]
            self._migrate_legacy_youtube_append_karaoke(data)
            self._migrate_legacy_youtube_downloads_dir(data)
            self._migrate_legacy_display_formats()
            self._sync_legacy_fields_from_active_type()
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load settings: %s", exc)

    def save(self) -> None:
        self.video_types = normalize_video_types(self.video_types)
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
            "metadata_comment_slot_indices": (
                None
                if self.metadata_comment_slot_indices is None
                else list(self.metadata_comment_slot_indices)
            ),
            "metadata_auto_fill_slots": self.metadata_auto_fill_slots,
            "metadata_skip_tagged": self.metadata_skip_tagged,
            "song_display_mode": self.song_display_mode,
            "song_display_format": self.song_display_format.to_dict(),
            "video_types": [profile.to_dict() for profile in self.video_types],
            "active_video_type_id": self.active_video_type_id,
            "library_flat_browse": self.library_flat_browse,
        }
        try:
            _settings_file().write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            logger.warning("Could not save settings: %s", exc)

    def resolved_youtube_downloads_dir(self) -> Path:
        """Return the YouTube downloads folder for the active media type."""
        return self._resolve_profile_downloads_dir(self.get_active_video_type())

    def _resolve_profile_downloads_dir(self, profile: VideoTypeProfile) -> Path:
        if profile.youtube_downloads_dir:
            path = Path(profile.youtube_downloads_dir)
            if path.is_dir():
                return path.resolve()
            logger.warning(
                "Configured YouTube downloads folder is unavailable for %s: %s",
                profile.name,
                profile.youtube_downloads_dir,
            )
        if profile.last_library_folder:
            path = Path(profile.last_library_folder)
            if path.is_dir():
                return path.resolve()
        return default_downloads_dir()

    def set_youtube_downloads_dir(self, path: Path) -> None:
        """Persist a custom YouTube downloads folder for the active media type."""
        resolved = path.resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        profile = self.get_active_video_type()
        updated = profile.copy()
        updated.youtube_downloads_dir = str(resolved)
        self.update_video_type(updated)
        self.youtube_downloads_dir = updated.youtube_downloads_dir
        self.save()

    def get_active_video_type(self) -> VideoTypeProfile:
        """Return the currently selected video type profile."""
        return active_video_type(self.video_types, self.active_video_type_id)

    def set_active_video_type_id(self, profile_id: str) -> None:
        """Switch the active video type and sync legacy rename fields."""
        if find_video_type(self.video_types, profile_id) is None:
            return
        self.active_video_type_id = profile_id
        self._sync_legacy_fields_from_active_type()

    def get_video_type_library_folder(self, profile_id: str) -> Path | None:
        """Return the last opened library folder for a media type, if it still exists."""
        profile = find_video_type(self.video_types, profile_id)
        if profile is None or not profile.last_library_folder:
            return None
        path = Path(profile.last_library_folder)
        if not path.is_dir():
            return None
        return path.resolve()

    def resolved_video_type_default_folder(self, profile_id: str | None = None) -> Path | None:
        """Return the default folder for a media type (library, else downloads)."""
        resolved_id = profile_id or self.active_video_type_id
        library = self.get_video_type_library_folder(resolved_id)
        if library is not None:
            return library
        profile = find_video_type(self.video_types, resolved_id)
        if profile is None:
            return None
        if profile.id == BUILTIN_ANY_ID:
            return Path.home().resolve()
        return self._resolve_profile_downloads_dir(profile)

    def set_video_type_library_folder(self, profile_id: str, folder: Path) -> None:
        """Remember the latest library folder opened for a media type."""
        profile = find_video_type(self.video_types, profile_id)
        if profile is None:
            return
        resolved = str(folder.resolve())
        if profile.last_library_folder == resolved:
            return
        updated = profile.copy()
        updated.last_library_folder = resolved
        self.update_video_type(updated)
        self.save()

    def update_video_type(self, profile: VideoTypeProfile) -> None:
        """Replace a video type profile in the stored list."""
        for index, existing in enumerate(self.video_types):
            if existing.id == profile.id:
                self.video_types[index] = profile.copy()
                if profile.id == self.active_video_type_id:
                    self._sync_legacy_fields_from_active_type()
                return
        self.video_types.append(profile.copy())
        if profile.id == self.active_video_type_id:
            self._sync_legacy_fields_from_active_type()

    def reset_builtin_video_type(self, profile_id: str) -> None:
        """Restore a built-in video type to its factory default."""
        profile = find_video_type(self.video_types, profile_id)
        if profile is None or not profile.builtin:
            return
        self.update_video_type(reset_builtin_video_type(profile))

    def remove_video_type(self, profile_id: str) -> None:
        """Remove a custom video type. Built-in types cannot be removed."""
        profile = find_video_type(self.video_types, profile_id)
        if profile is None or profile.builtin:
            return
        self.video_types = [item for item in self.video_types if item.id != profile_id]
        if self.active_video_type_id == profile_id:
            self.active_video_type_id = BUILTIN_SONGS_ID
            self._sync_legacy_fields_from_active_type()

    def _migrate_legacy_youtube_append_karaoke(self, data: dict[str, object]) -> None:
        """Move the legacy global append-karaoke preference onto the Songs profile."""
        legacy = data.get("youtube_append_karaoke")
        if not isinstance(legacy, bool):
            return
        raw_video_types = data.get("video_types")
        if not isinstance(raw_video_types, list):
            return
        songs_entry = next(
            (
                entry
                for entry in raw_video_types
                if isinstance(entry, dict) and entry.get("id") == BUILTIN_SONGS_ID
            ),
            None,
        )
        if songs_entry is not None and "youtube_append_karaoke" in songs_entry:
            return
        songs = find_video_type(self.video_types, BUILTIN_SONGS_ID)
        if songs is None:
            return
        updated = songs.copy()
        updated.youtube_search_append = YOUTUBE_APPEND_KARAOKE if legacy else None
        updated.youtube_append_karaoke = legacy
        self.update_video_type(updated)

    def _migrate_legacy_display_formats(self) -> None:
        """Move the legacy global display format onto the Songs profile once."""
        songs = find_video_type(self.video_types, BUILTIN_SONGS_ID)
        if songs is None or songs.display_format is not None:
            return
        updated = songs.copy()
        updated.display_format = self.song_display_format.copy()
        self.update_video_type(updated)

    def _sync_legacy_fields_from_active_type(self) -> None:
        """Keep legacy single-format fields aligned with the active video type."""
        profile = self.get_active_video_type()
        self.filename_rename_format = profile.rename_format.copy()
        mapping = profile.resolved_metadata_mapping()
        description_slots = list(mapping.description_slots)
        self.metadata_comment_slot_indices = description_slots or None
        self.song_display_format = profile.resolved_display_format().copy()
        self.youtube_append_karaoke = bool(profile.youtube_search_append)
        self.youtube_downloads_dir = profile.youtube_downloads_dir

    def _migrate_legacy_youtube_downloads_dir(self, data: dict[str, object]) -> None:
        """Move the legacy global downloads folder onto the Songs profile."""
        legacy = data.get("youtube_downloads_dir")
        if not isinstance(legacy, str) or not legacy.strip():
            return
        raw_video_types = data.get("video_types")
        if not isinstance(raw_video_types, list):
            return
        songs_entry = next(
            (
                entry
                for entry in raw_video_types
                if isinstance(entry, dict) and entry.get("id") == BUILTIN_SONGS_ID
            ),
            None,
        )
        if songs_entry is not None and "youtube_downloads_dir" in songs_entry:
            return
        songs = find_video_type(self.video_types, BUILTIN_SONGS_ID)
        if songs is None:
            return
        updated = songs.copy()
        updated.youtube_downloads_dir = legacy.strip()
        self.update_video_type(updated)
