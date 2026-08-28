"""Video type profiles for rename and metadata workflows."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum

from karaoke_blast.utils.filename_rename import (
    DEFAULT_KARAOKE_FORMAT,
    DEFAULT_SEPARATORS,
    FilenameFormat,
    FormatSlot,
    SLOT_KIND_ADDITIONAL,
    SLOT_KIND_ARTIST,
    SLOT_KIND_SONG,
)
from karaoke_blast.utils.metadata_field_mapping import (
    MetadataFieldMapping,
    builtin_metadata_mapping,
    default_metadata_mapping,
)
from karaoke_blast.utils.song_display import (
    DisplayFormat,
    SLOT_KIND_DESCRIPTION,
    SLOT_KIND_GENRE,
    default_display_format_for_mapping,
    display_format_has_enabled_kind_before,
)

YOUTUBE_APPEND_KARAOKE = "karaoke"
YOUTUBE_APPEND_VIDEOKE = "videoke"

YOUTUBE_APPEND_COMBO_ITEMS: tuple[tuple[str, str | None], ...] = (
    ("Karaoke", YOUTUBE_APPEND_KARAOKE),
    ("Videoke", YOUTUBE_APPEND_VIDEOKE),
    ("None", None),
)


class MediaCategory(str, Enum):
    KARAOKE_VIDEOKE = "karaoke_videoke"
    VIDEO = "video"
    AUDIO = "audio"
    NONE = "none"


_MEDIA_CATEGORY_LABELS = {
    MediaCategory.KARAOKE_VIDEOKE: "Karaoke/Videoke",
    MediaCategory.VIDEO: "Video",
    MediaCategory.AUDIO: "Audio",
    MediaCategory.NONE: "None",
}

BUILTIN_ANY_ID = "any"
BUILTIN_SONGS_ID = "songs"
BUILTIN_KARAOKE_ID = BUILTIN_SONGS_ID
BUILTIN_MUSIC_VIDEOS_ID = "music_videos"
BUILTIN_MUSIC_AUDIO_ID = "music_audio"
BUILTIN_TV_SHOWS_ID = "tv_shows"
BUILTIN_MOVIES_ID = "movies"
BUILTIN_PERSONAL_VIDEOS_ID = "personal_videos"

_BUILTIN_MEDIA_CATEGORIES: dict[str, MediaCategory] = {
    BUILTIN_ANY_ID: MediaCategory.VIDEO,
    BUILTIN_SONGS_ID: MediaCategory.KARAOKE_VIDEOKE,
    BUILTIN_MUSIC_VIDEOS_ID: MediaCategory.VIDEO,
    BUILTIN_MUSIC_AUDIO_ID: MediaCategory.AUDIO,
    BUILTIN_TV_SHOWS_ID: MediaCategory.VIDEO,
    BUILTIN_MOVIES_ID: MediaCategory.VIDEO,
    BUILTIN_PERSONAL_VIDEOS_ID: MediaCategory.VIDEO,
}

BUILTIN_IDS = frozenset({
    BUILTIN_ANY_ID,
    BUILTIN_SONGS_ID,
    BUILTIN_MUSIC_VIDEOS_ID,
    BUILTIN_MUSIC_AUDIO_ID,
    BUILTIN_TV_SHOWS_ID,
    BUILTIN_MOVIES_ID,
    BUILTIN_PERSONAL_VIDEOS_ID,
})

BUILTIN_ORDER = (
    BUILTIN_ANY_ID,
    BUILTIN_SONGS_ID,
    BUILTIN_MUSIC_VIDEOS_ID,
    BUILTIN_MUSIC_AUDIO_ID,
    BUILTIN_TV_SHOWS_ID,
    BUILTIN_MOVIES_ID,
    BUILTIN_PERSONAL_VIDEOS_ID,
)

_BUILTIN_NAMES = {
    BUILTIN_ANY_ID: "Any",
    BUILTIN_SONGS_ID: "Karaoke",
    BUILTIN_MUSIC_VIDEOS_ID: "Music (Videos)",
    BUILTIN_MUSIC_AUDIO_ID: "Music (Audio)",
    BUILTIN_TV_SHOWS_ID: "TV Shows",
    BUILTIN_MOVIES_ID: "Movies",
    BUILTIN_PERSONAL_VIDEOS_ID: "Personal Videos",
}


def _default_any_format() -> FilenameFormat:
    return FilenameFormat(
        slots=[
            FormatSlot(SLOT_KIND_SONG, "Media name", enabled=True),
            FormatSlot(SLOT_KIND_ARTIST, "Description", enabled=True),
            FormatSlot(SLOT_KIND_ADDITIONAL, "Additional", enabled=True, hint=""),
            FormatSlot(SLOT_KIND_ADDITIONAL, "Additional", enabled=False, hint=""),
        ],
        separators=list(DEFAULT_SEPARATORS),
    )


def _default_songs_format() -> FilenameFormat:
    return DEFAULT_KARAOKE_FORMAT.copy()


def _default_tv_shows_format() -> FilenameFormat:
    return FilenameFormat(
        slots=[
            FormatSlot(SLOT_KIND_SONG, "Series Name", enabled=True),
            FormatSlot(SLOT_KIND_ARTIST, "Episode Title", enabled=True),
            FormatSlot(SLOT_KIND_ADDITIONAL, "Episode Number", enabled=True, hint=""),
            FormatSlot(SLOT_KIND_ADDITIONAL, "Notes", enabled=False, hint=""),
        ],
        separators=list(DEFAULT_SEPARATORS),
    )


def _default_movies_format() -> FilenameFormat:
    return FilenameFormat(
        slots=[
            FormatSlot(SLOT_KIND_SONG, "Movie Name", enabled=True),
            FormatSlot(SLOT_KIND_ARTIST, "Main Actor", enabled=True),
            FormatSlot(SLOT_KIND_ADDITIONAL, "Genre", enabled=True, hint=""),
            FormatSlot(SLOT_KIND_ADDITIONAL, "Year", enabled=True, hint=""),
        ],
        separators=list(DEFAULT_SEPARATORS),
    )


def _default_personal_videos_format() -> FilenameFormat:
    return FilenameFormat(
        slots=[
            FormatSlot(SLOT_KIND_SONG, "Title", enabled=True),
            FormatSlot(SLOT_KIND_ARTIST, "Topic", enabled=True),
            FormatSlot(SLOT_KIND_ADDITIONAL, "Creator", enabled=True, hint=""),
            FormatSlot(SLOT_KIND_ADDITIONAL, "Date", enabled=True, hint=""),
        ],
        separators=list(DEFAULT_SEPARATORS),
    )


def _default_music_format() -> FilenameFormat:
    return FilenameFormat(
        slots=[
            FormatSlot(SLOT_KIND_SONG, "Song Name", enabled=True),
            FormatSlot(SLOT_KIND_ARTIST, "Artist Name", enabled=True),
            FormatSlot(SLOT_KIND_ADDITIONAL, "Album", enabled=True, hint=""),
            FormatSlot(SLOT_KIND_ADDITIONAL, "Additional", enabled=False, hint=""),
        ],
        separators=list(DEFAULT_SEPARATORS),
    )


def _default_custom_format() -> FilenameFormat:
    return FilenameFormat(
        slots=[
            FormatSlot(SLOT_KIND_SONG, "Song Name", enabled=True),
            FormatSlot(SLOT_KIND_ARTIST, "Artist Name", enabled=True),
            FormatSlot(SLOT_KIND_ADDITIONAL, "Additional", enabled=False, hint=""),
            FormatSlot(SLOT_KIND_ADDITIONAL, "Additional", enabled=False, hint=""),
        ],
        separators=list(DEFAULT_SEPARATORS),
    )


_BUILTIN_DEFAULTS: dict[str, FilenameFormat] = {
    BUILTIN_ANY_ID: _default_any_format(),
    BUILTIN_SONGS_ID: _default_songs_format(),
    BUILTIN_MUSIC_VIDEOS_ID: _default_music_format(),
    BUILTIN_MUSIC_AUDIO_ID: _default_music_format(),
    BUILTIN_TV_SHOWS_ID: _default_tv_shows_format(),
    BUILTIN_MOVIES_ID: _default_movies_format(),
    BUILTIN_PERSONAL_VIDEOS_ID: _default_personal_videos_format(),
}


def default_media_category(profile_id: str, *, builtin: bool) -> MediaCategory:
    if builtin and profile_id in _BUILTIN_MEDIA_CATEGORIES:
        return _BUILTIN_MEDIA_CATEGORIES[profile_id]
    return MediaCategory.NONE


def default_youtube_search_append(category: MediaCategory) -> str | None:
    if category == MediaCategory.KARAOKE_VIDEOKE:
        return YOUTUBE_APPEND_KARAOKE
    return None


def shows_youtube_append_dropdown(category: MediaCategory) -> bool:
    return category == MediaCategory.KARAOKE_VIDEOKE


def resolve_youtube_append_term(profile: VideoTypeProfile) -> str | None:
    if not shows_youtube_append_dropdown(profile.media_category):
        return None
    return profile.youtube_search_append


def media_category_label(category: MediaCategory) -> str:
    return _MEDIA_CATEGORY_LABELS[category]


def parse_media_category(value: object) -> MediaCategory | None:
    if isinstance(value, str):
        try:
            return MediaCategory(value)
        except ValueError:
            pass
    return None


def parse_youtube_search_append(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        lowered = value.casefold()
        if lowered == YOUTUBE_APPEND_KARAOKE:
            return YOUTUBE_APPEND_KARAOKE
        if lowered == YOUTUBE_APPEND_VIDEOKE:
            return YOUTUBE_APPEND_VIDEOKE
    return None


def youtube_append_combo_index(append: str | None) -> int:
    for index, (_, value) in enumerate(YOUTUBE_APPEND_COMBO_ITEMS):
        if value == append:
            return index
    return len(YOUTUBE_APPEND_COMBO_ITEMS) - 1


def youtube_append_from_combo_index(index: int) -> str | None:
    if 0 <= index < len(YOUTUBE_APPEND_COMBO_ITEMS):
        return YOUTUBE_APPEND_COMBO_ITEMS[index][1]
    return None


def default_youtube_append_karaoke(profile_id: str) -> bool:
    """Backward-compatible default derived from built-in media category."""
    if profile_id not in BUILTIN_IDS:
        return False
    return shows_youtube_append_dropdown(default_media_category(profile_id, builtin=True))


def _migrate_youtube_search_append(
    data: dict[str, object],
    media_category: MediaCategory,
) -> str | None:
    if "youtube_search_append" in data:
        return parse_youtube_search_append(data.get("youtube_search_append"))
    legacy = data.get("youtube_append_karaoke")
    if isinstance(legacy, bool):
        if legacy and shows_youtube_append_dropdown(media_category):
            return YOUTUBE_APPEND_KARAOKE
        return None
    return default_youtube_search_append(media_category)


@dataclass
class VideoTypeProfile:
    """A named video type with rename format and metadata options."""

    id: str
    name: str
    builtin: bool
    rename_format: FilenameFormat
    metadata_comment_slot_indices: list[int] | None = None
    metadata_field_mapping: MetadataFieldMapping | None = None
    display_format: DisplayFormat | None = None
    media_category: MediaCategory = MediaCategory.NONE
    youtube_search_append: str | None = None
    youtube_append_karaoke: bool = False
    last_library_folder: str | None = None
    youtube_downloads_dir: str | None = None

    def resolved_metadata_mapping(self) -> MetadataFieldMapping:
        if self.metadata_field_mapping is not None:
            return self.metadata_field_mapping.copy().normalize_for_format(
                self.rename_format
            )
        if self.builtin:
            return builtin_metadata_mapping(
                self.id, self.rename_format
            ).normalize_for_format(self.rename_format)
        return default_metadata_mapping(
            self.rename_format,
            legacy_comment_slot_indices=self.metadata_comment_slot_indices,
        ).normalize_for_format(self.rename_format)

    def resolved_display_format(self) -> DisplayFormat:
        if self.display_format is not None:
            return self.display_format.copy()
        return default_display_format_for_mapping(
            self.resolved_metadata_mapping()
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "builtin": self.builtin,
            "rename_format": self.rename_format.to_dict(),
            "metadata_comment_slot_indices": (
                None
                if self.metadata_comment_slot_indices is None
                else list(self.metadata_comment_slot_indices)
            ),
            "metadata_field_mapping": (
                None
                if self.metadata_field_mapping is None
                else self.metadata_field_mapping.to_dict()
            ),
            "display_format": (
                None
                if self.display_format is None
                else self.display_format.to_dict()
            ),
            "media_category": self.media_category.value,
            "youtube_search_append": self.youtube_search_append,
            "youtube_append_karaoke": bool(self.youtube_search_append),
            "last_library_folder": self.last_library_folder,
            "youtube_downloads_dir": self.youtube_downloads_dir,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> VideoTypeProfile:
        profile_id = str(data.get("id", ""))
        name = str(data.get("name", "Custom"))
        builtin = bool(data.get("builtin", False))
        rename_data = data.get("rename_format")
        rename_format = (
            FilenameFormat.from_dict(rename_data)
            if isinstance(rename_data, dict)
            else _default_custom_format()
        )
        comment_indices = data.get("metadata_comment_slot_indices")
        metadata_comment_slot_indices: list[int] | None = None
        if comment_indices is None:
            metadata_comment_slot_indices = None
        elif isinstance(comment_indices, list):
            parsed: list[int] = []
            for item in comment_indices:
                if isinstance(item, int) and 0 <= item < 4 and item not in parsed:
                    parsed.append(item)
            metadata_comment_slot_indices = parsed
        mapping_data = data.get("metadata_field_mapping")
        metadata_field_mapping = (
            MetadataFieldMapping.from_dict(mapping_data)
            if isinstance(mapping_data, dict)
            else None
        )
        display_data = data.get("display_format")
        display_format = (
            DisplayFormat.from_dict(display_data)
            if isinstance(display_data, dict)
            else None
        )
        media_category = parse_media_category(data.get("media_category"))
        if media_category is None:
            media_category = default_media_category(profile_id, builtin=builtin)
        youtube_search_append = _migrate_youtube_search_append(data, media_category)
        youtube_append_karaoke = bool(youtube_search_append)
        last_library_folder = data.get("last_library_folder")
        if isinstance(last_library_folder, str) and last_library_folder.strip():
            stored_library_folder: str | None = last_library_folder.strip()
        else:
            stored_library_folder = None
        downloads_dir = data.get("youtube_downloads_dir")
        if isinstance(downloads_dir, str) and downloads_dir.strip():
            stored_downloads_dir: str | None = downloads_dir.strip()
        else:
            stored_downloads_dir = None
        profile = cls(
            id=profile_id,
            name=name,
            builtin=builtin,
            rename_format=rename_format,
            metadata_comment_slot_indices=metadata_comment_slot_indices,
            metadata_field_mapping=metadata_field_mapping,
            display_format=display_format,
            media_category=media_category,
            youtube_search_append=youtube_search_append,
            youtube_append_karaoke=youtube_append_karaoke,
            last_library_folder=stored_library_folder,
            youtube_downloads_dir=stored_downloads_dir,
        )
        if metadata_field_mapping is None and metadata_comment_slot_indices is not None:
            profile.metadata_field_mapping = default_metadata_mapping(
                rename_format,
                legacy_comment_slot_indices=metadata_comment_slot_indices,
            )
        return profile

    def copy(self) -> VideoTypeProfile:
        return VideoTypeProfile.from_dict(self.to_dict())


def builtin_video_type(profile_id: str) -> VideoTypeProfile:
    """Return a factory-default built-in profile."""
    if profile_id not in BUILTIN_IDS:
        raise ValueError(f"Unknown built-in video type: {profile_id}")
    rename_format = _BUILTIN_DEFAULTS[profile_id].copy()
    mapping = builtin_metadata_mapping(profile_id, rename_format)
    category = default_media_category(profile_id, builtin=True)
    return VideoTypeProfile(
        id=profile_id,
        name=_BUILTIN_NAMES[profile_id],
        builtin=True,
        rename_format=rename_format,
        metadata_comment_slot_indices=None,
        metadata_field_mapping=mapping,
        display_format=default_display_format_for_mapping(mapping),
        media_category=category,
        youtube_search_append=default_youtube_search_append(category),
        youtube_append_karaoke=category == MediaCategory.KARAOKE_VIDEOKE,
    )


def default_video_types() -> list[VideoTypeProfile]:
    """Return all built-in video types with factory defaults."""
    return [builtin_video_type(profile_id) for profile_id in BUILTIN_ORDER]


_LEGACY_PIPE_SEPARATORS = (" | ", " | ", " | ")


def _migrate_legacy_separators(profile: VideoTypeProfile) -> VideoTypeProfile:
    """Replace legacy pipe separators with the standard dash default."""
    separators = profile.rename_format.separators
    if list(separators) == list(_LEGACY_PIPE_SEPARATORS):
        updated = profile.copy()
        updated.rename_format.separators = list(DEFAULT_SEPARATORS)
        return updated
    if profile.builtin and any("|" in sep for sep in separators):
        updated = profile.copy()
        updated.rename_format.separators = [
            " - " if "|" in sep else sep for sep in separators
        ]
        return updated
    return profile


def _is_legacy_tv_shows_format(fmt: FilenameFormat) -> bool:
    slots = fmt.slots
    if len(slots) < 3:
        return False
    return (
        slots[0].label == "Episode Title"
        and slots[1].label == "Series Name"
        and slots[2].label == "Episode Number"
    )


def _is_legacy_movies_format(fmt: FilenameFormat) -> bool:
    slots = fmt.slots
    if len(slots) < 3:
        return False
    return (
        slots[0].label == "Movie Name"
        and slots[1].label == "Main Actor"
        and slots[2].label == "Year"
    )


def _migrate_legacy_movies_format(profile: VideoTypeProfile) -> VideoTypeProfile:
    if profile.id != BUILTIN_MOVIES_ID or not profile.builtin:
        return profile
    if not _is_legacy_movies_format(profile.rename_format):
        return profile
    updated = profile.copy()
    updated.rename_format = _default_movies_format()
    updated.metadata_field_mapping = builtin_metadata_mapping(
        BUILTIN_MOVIES_ID,
        updated.rename_format,
    )
    updated.display_format = default_display_format_for_mapping(
        updated.metadata_field_mapping
    )
    return updated


def _migrate_movies_display_format(profile: VideoTypeProfile) -> VideoTypeProfile:
    if profile.id != BUILTIN_MOVIES_ID or not profile.builtin:
        return profile
    mapping = profile.resolved_metadata_mapping()
    if mapping.genre_slot is None or not mapping.description_slots:
        return profile
    display = profile.display_format
    if display is None:
        return profile
    if not display_format_has_enabled_kind_before(
        display,
        before=SLOT_KIND_DESCRIPTION,
        after=SLOT_KIND_GENRE,
    ):
        return profile
    updated = profile.copy()
    updated.display_format = default_display_format_for_mapping(mapping)
    return updated


def _migrate_legacy_tv_shows_format(profile: VideoTypeProfile) -> VideoTypeProfile:
    if profile.id != BUILTIN_TV_SHOWS_ID or not profile.builtin:
        return profile
    if not _is_legacy_tv_shows_format(profile.rename_format):
        return profile
    updated = profile.copy()
    updated.rename_format = _default_tv_shows_format()
    return updated


def normalize_video_types(profiles: list[VideoTypeProfile]) -> list[VideoTypeProfile]:
    """Deduplicate profiles and ensure all built-in types are present once."""
    builtin_names = {name.casefold() for name in _BUILTIN_NAMES.values()}
    by_id: dict[str, VideoTypeProfile] = {}
    customs: list[VideoTypeProfile] = []

    for profile in profiles:
        copied = _migrate_movies_display_format(
            _migrate_legacy_movies_format(
                _migrate_legacy_tv_shows_format(
                    _migrate_legacy_separators(profile.copy())
                )
            )
        )
        if copied.id in by_id:
            continue
        if copied.id in BUILTIN_IDS:
            copied.name = _BUILTIN_NAMES[copied.id]
            factory = builtin_video_type(copied.id)
            copied.media_category = factory.media_category
            by_id[copied.id] = copied
            continue
        if copied.name.strip().casefold() in builtin_names:
            continue
        customs.append(copied)

    result: list[VideoTypeProfile] = []
    for builtin_id in BUILTIN_ORDER:
        existing = by_id.get(builtin_id)
        if existing is not None:
            result.append(existing)
        else:
            result.append(builtin_video_type(builtin_id))
    result.extend(customs)
    return result


def ensure_builtin_video_types(
    profiles: list[VideoTypeProfile],
) -> list[VideoTypeProfile]:
    """Backward-compatible alias for normalize_video_types."""
    return normalize_video_types(profiles)


def reset_builtin_video_type(profile: VideoTypeProfile) -> VideoTypeProfile:
    """Restore a built-in profile to its factory default."""
    if not profile.builtin or profile.id not in BUILTIN_IDS:
        return profile.copy()
    return builtin_video_type(profile.id)


def default_custom_format() -> FilenameFormat:
    """Return the blank template used for new custom video types."""
    return _default_custom_format()


def create_custom_video_type(
    name: str,
    *,
    rename_format: FilenameFormat | None = None,
    media_category: MediaCategory = MediaCategory.NONE,
) -> VideoTypeProfile:
    """Create a new user-defined video type."""
    cleaned = name.strip() or "Custom"
    fmt = (
        rename_format.copy()
        if rename_format is not None
        else _default_custom_format()
    )
    return VideoTypeProfile(
        id=uuid.uuid4().hex,
        name=cleaned,
        builtin=False,
        rename_format=fmt,
        metadata_comment_slot_indices=None,
        metadata_field_mapping=default_metadata_mapping(fmt),
        display_format=default_display_format_for_mapping(
            default_metadata_mapping(fmt)
        ),
        media_category=media_category,
        youtube_search_append=default_youtube_search_append(media_category),
        youtube_append_karaoke=shows_youtube_append_dropdown(media_category),
    )


def migrate_video_types(
    *,
    existing_rename_format: FilenameFormat,
    existing_comment_indices: list[int] | None,
) -> list[VideoTypeProfile]:
    """Build initial video types from legacy single-format settings."""
    songs = builtin_video_type(BUILTIN_SONGS_ID)
    songs.rename_format = existing_rename_format.copy()
    songs.metadata_comment_slot_indices = (
        list(existing_comment_indices)
        if existing_comment_indices is not None
        else None
    )
    return [
        songs,
        builtin_video_type(BUILTIN_MUSIC_VIDEOS_ID),
        builtin_video_type(BUILTIN_MUSIC_AUDIO_ID),
        builtin_video_type(BUILTIN_TV_SHOWS_ID),
        builtin_video_type(BUILTIN_MOVIES_ID),
        builtin_video_type(BUILTIN_PERSONAL_VIDEOS_ID),
    ]


def find_video_type(
    profiles: list[VideoTypeProfile], profile_id: str
) -> VideoTypeProfile | None:
    for profile in profiles:
        if profile.id == profile_id:
            return profile
    return None


def active_video_type(
    profiles: list[VideoTypeProfile], active_id: str
) -> VideoTypeProfile:
    profile = find_video_type(profiles, active_id)
    if profile is not None:
        return profile
    fallback = find_video_type(profiles, BUILTIN_SONGS_ID)
    if fallback is not None:
        return fallback
    types = default_video_types()
    return types[0]
