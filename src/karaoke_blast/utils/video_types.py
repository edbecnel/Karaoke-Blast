"""Video type profiles for rename and metadata workflows."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

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
    default_display_format_for_mapping,
)

BUILTIN_SONGS_ID = "songs"
BUILTIN_TV_SHOWS_ID = "tv_shows"
BUILTIN_MOVIES_ID = "movies"
BUILTIN_PERSONAL_VIDEOS_ID = "personal_videos"

BUILTIN_IDS = frozenset({
    BUILTIN_SONGS_ID,
    BUILTIN_TV_SHOWS_ID,
    BUILTIN_MOVIES_ID,
    BUILTIN_PERSONAL_VIDEOS_ID,
})

BUILTIN_ORDER = (
    BUILTIN_SONGS_ID,
    BUILTIN_TV_SHOWS_ID,
    BUILTIN_MOVIES_ID,
    BUILTIN_PERSONAL_VIDEOS_ID,
)

_BUILTIN_NAMES = {
    BUILTIN_SONGS_ID: "Songs",
    BUILTIN_TV_SHOWS_ID: "TV Shows",
    BUILTIN_MOVIES_ID: "Movies",
    BUILTIN_PERSONAL_VIDEOS_ID: "Personal Videos",
}


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
            FormatSlot(SLOT_KIND_ADDITIONAL, "Year", enabled=True, hint=""),
            FormatSlot(SLOT_KIND_ADDITIONAL, "Additional", enabled=False, hint=""),
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
    BUILTIN_SONGS_ID: _default_songs_format(),
    BUILTIN_TV_SHOWS_ID: _default_tv_shows_format(),
    BUILTIN_MOVIES_ID: _default_movies_format(),
    BUILTIN_PERSONAL_VIDEOS_ID: _default_personal_videos_format(),
}


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
        profile = cls(
            id=profile_id,
            name=name,
            builtin=builtin,
            rename_format=rename_format,
            metadata_comment_slot_indices=metadata_comment_slot_indices,
            metadata_field_mapping=metadata_field_mapping,
            display_format=display_format,
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
    return VideoTypeProfile(
        id=profile_id,
        name=_BUILTIN_NAMES[profile_id],
        builtin=True,
        rename_format=rename_format,
        metadata_comment_slot_indices=None,
        metadata_field_mapping=mapping,
        display_format=default_display_format_for_mapping(mapping),
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
        copied = _migrate_legacy_tv_shows_format(
            _migrate_legacy_separators(profile.copy())
        )
        if copied.id in by_id:
            continue
        if copied.id in BUILTIN_IDS:
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
) -> VideoTypeProfile:
    """Create a new user-defined video type."""
    cleaned = name.strip() or "Custom"
    return VideoTypeProfile(
        id=uuid.uuid4().hex,
        name=cleaned,
        builtin=False,
        rename_format=(
            rename_format.copy()
            if rename_format is not None
            else _default_custom_format()
        ),
        metadata_comment_slot_indices=None,
        metadata_field_mapping=default_metadata_mapping(
            rename_format if rename_format is not None else _default_custom_format()
        ),
        display_format=default_display_format_for_mapping(
            default_metadata_mapping(
                rename_format if rename_format is not None else _default_custom_format()
            )
        ),
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
