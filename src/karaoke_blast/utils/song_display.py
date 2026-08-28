"""Library list display labels from filename or embedded metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from karaoke_blast.utils.display import display_name
from karaoke_blast.utils.media_metadata import MediaTags, MetadataError, read_tags
from karaoke_blast.utils.metadata_field_mapping import (
    MetadataFieldMapping,
    VLC_FIELD_ALBUM,
    VLC_FIELD_ARTIST,
    VLC_FIELD_DESCRIPTION,
    VLC_FIELD_GENRE,
    VLC_FIELD_TITLE,
    metadata_field_display_labels,
)

DISPLAY_MODE_FILENAME = "filename"
DISPLAY_MODE_METADATA = "metadata"

SLOT_KIND_TITLE = "title"
SLOT_KIND_ARTIST = "artist"
SLOT_KIND_DESCRIPTION = "description"
SLOT_KIND_GENRE = "genre"
SLOT_KIND_ALBUM = "album"
# Legacy persisted value for the description slot.
SLOT_KIND_COMMENT = "comment"

SLOT_KINDS = (
    SLOT_KIND_TITLE,
    SLOT_KIND_ARTIST,
    SLOT_KIND_GENRE,
    SLOT_KIND_DESCRIPTION,
    SLOT_KIND_ALBUM,
)
SLOT_COUNT = 5
SEPARATOR_COUNT = 4
DEFAULT_SEPARATORS = (" - ", " - ", " - ")

_DEFAULT_FIELD_LABELS = {
    SLOT_KIND_TITLE: "Title",
    SLOT_KIND_ARTIST: "Artist",
    SLOT_KIND_DESCRIPTION: "Description",
    SLOT_KIND_GENRE: "Genre",
    SLOT_KIND_ALBUM: "Album",
}


def _normalize_slot_kind(kind: str) -> str:
    if kind == SLOT_KIND_COMMENT:
        return SLOT_KIND_DESCRIPTION
    if kind in SLOT_KINDS:
        return kind
    return SLOT_KIND_TITLE


@dataclass
class DisplaySlot:
    """One position in the metadata display format."""

    kind: str
    enabled: bool = True

    def to_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "enabled": self.enabled}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> DisplaySlot:
        kind = _normalize_slot_kind(str(data.get("kind", SLOT_KIND_TITLE)))
        return cls(kind=kind, enabled=bool(data.get("enabled", True)))


@dataclass
class DisplayFormat:
    """Reorderable VLC metadata slots with separators."""

    slots: list[DisplaySlot] = field(default_factory=list)
    separators: list[str] = field(default_factory=lambda: list(DEFAULT_SEPARATORS))

    def __post_init__(self) -> None:
        self._normalize_shape()

    def _normalize_shape(self) -> None:
        by_kind = {
            _normalize_slot_kind(slot.kind): slot
            for slot in self.slots
            if _normalize_slot_kind(slot.kind) in SLOT_KINDS
        }
        ordered: list[DisplaySlot] = []
        seen: set[str] = set()
        for slot in self.slots:
            kind = _normalize_slot_kind(slot.kind)
            if kind in SLOT_KINDS and kind not in seen:
                ordered.append(DisplaySlot(kind, enabled=slot.enabled))
                seen.add(kind)
        for kind in SLOT_KINDS:
            if kind not in seen:
                existing = by_kind.get(kind)
                ordered.append(
                    DisplaySlot(kind, enabled=True if existing is None else existing.enabled)
                )
                seen.add(kind)
        self.slots = ordered[:SLOT_COUNT]
        while len(self.separators) < SEPARATOR_COUNT:
            self.separators.append(" - ")
        self.separators = [str(sep) for sep in self.separators[:SEPARATOR_COUNT]]

    def copy(self) -> DisplayFormat:
        return DisplayFormat.from_dict(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        self._normalize_shape()
        return {
            "slots": [slot.to_dict() for slot in self.slots],
            "separators": list(self.separators),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> DisplayFormat:
        if not data:
            return DEFAULT_DISPLAY_FORMAT.copy()
        raw_slots = data.get("slots", [])
        separators = data.get("separators", DEFAULT_SEPARATORS)
        slots: list[DisplaySlot] = []
        if isinstance(raw_slots, list):
            for entry in raw_slots:
                if isinstance(entry, dict):
                    slots.append(DisplaySlot.from_dict(entry))
        fmt = cls(
            slots=slots,
            separators=[str(sep) for sep in separators]
            if isinstance(separators, list)
            else list(DEFAULT_SEPARATORS),
        )
        fmt._normalize_shape()
        return fmt


DEFAULT_DISPLAY_FORMAT = DisplayFormat(
    slots=[
        DisplaySlot(SLOT_KIND_TITLE, enabled=True),
        DisplaySlot(SLOT_KIND_ARTIST, enabled=True),
        DisplaySlot(SLOT_KIND_GENRE, enabled=False),
        DisplaySlot(SLOT_KIND_DESCRIPTION, enabled=True),
        DisplaySlot(SLOT_KIND_ALBUM, enabled=False),
    ],
    separators=list(DEFAULT_SEPARATORS),
)


def default_display_format_for_mapping(mapping: MetadataFieldMapping) -> DisplayFormat:
    """Factory default display layout from a metadata field mapping."""
    return DisplayFormat(
        slots=[
            DisplaySlot(SLOT_KIND_TITLE, enabled=mapping.title_slot is not None),
            DisplaySlot(SLOT_KIND_ARTIST, enabled=mapping.artist_slot is not None),
            DisplaySlot(SLOT_KIND_GENRE, enabled=mapping.genre_slot is not None),
            DisplaySlot(
                SLOT_KIND_DESCRIPTION,
                enabled=bool(mapping.description_slots),
            ),
            DisplaySlot(SLOT_KIND_ALBUM, enabled=mapping.album_slot is not None),
        ],
        separators=list(DEFAULT_SEPARATORS),
    )


def display_format_has_enabled_kind_before(
    fmt: DisplayFormat,
    *,
    before: str,
    after: str,
) -> bool:
    """Return True when *before* appears before *after* among enabled slots."""
    kinds = [slot.kind for slot in fmt.slots if slot.enabled]
    if before not in kinds or after not in kinds:
        return False
    return kinds.index(before) < kinds.index(after)


def display_field_labels_from_mapping(
    mapping: MetadataFieldMapping,
    *,
    rename_format=None,
) -> dict[str, str]:
    """Map display slot kinds to labels using VLC metadata mapping."""
    if rename_format is None:
        from karaoke_blast.utils.filename_rename import DEFAULT_KARAOKE_FORMAT

        rename_format = DEFAULT_KARAOKE_FORMAT
    vlc_labels = metadata_field_display_labels(rename_format, mapping)
    return {
        SLOT_KIND_TITLE: vlc_labels[VLC_FIELD_TITLE],
        SLOT_KIND_ARTIST: vlc_labels[VLC_FIELD_ARTIST],
        SLOT_KIND_DESCRIPTION: vlc_labels[VLC_FIELD_DESCRIPTION],
        SLOT_KIND_GENRE: vlc_labels[VLC_FIELD_GENRE],
        SLOT_KIND_ALBUM: vlc_labels[VLC_FIELD_ALBUM],
    }


def slot_kind_label(kind: str, field_labels: dict[str, str] | None = None) -> str:
    normalized = _normalize_slot_kind(kind)
    if field_labels and normalized in field_labels:
        return field_labels[normalized]
    return _DEFAULT_FIELD_LABELS.get(normalized, normalized)


def _slot_value(tags: MediaTags, kind: str) -> str:
    normalized = _normalize_slot_kind(kind)
    if normalized == SLOT_KIND_TITLE:
        return tags.title.strip()
    if normalized == SLOT_KIND_ARTIST:
        return tags.artist.strip()
    if normalized == SLOT_KIND_DESCRIPTION:
        return tags.comment.strip()
    if normalized == SLOT_KIND_GENRE:
        return tags.genre.strip()
    if normalized == SLOT_KIND_ALBUM:
        return tags.album.strip()
    return ""


def format_metadata_label(tags: MediaTags, fmt: DisplayFormat) -> str:
    """Join enabled non-empty metadata slots using configured separators."""
    fmt._normalize_shape()
    included: list[tuple[int, str]] = []
    for index, slot in enumerate(fmt.slots):
        if not slot.enabled:
            continue
        value = _slot_value(tags, slot.kind)
        if value:
            included.append((index, value))
    if not included:
        return ""
    result = included[0][1]
    for position in range(1, len(included)):
        index = included[position][0]
        separator = fmt.separators[index - 1] if index > 0 else " - "
        result += separator + included[position][1]
    return result


def format_display_preview(
    fmt: DisplayFormat,
    *,
    field_labels: dict[str, str] | None = None,
) -> str:
    """Human-readable pattern preview for the format dialog."""
    fmt._normalize_shape()
    enabled = [index for index, slot in enumerate(fmt.slots) if slot.enabled]
    if not enabled:
        return ""
    parts: list[str] = []
    for position, index in enumerate(enabled):
        if position > 0:
            parts.append(fmt.separators[index - 1] if index > 0 else " - ")
        parts.append(
            f"{{{slot_kind_label(fmt.slots[index].kind, field_labels)}}}"
        )
    return "".join(parts)


class TagCache:
    """Cache MediaTags by resolved path and mtime."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[float, MediaTags]] = {}

    def clear(self) -> None:
        self._entries.clear()

    def get(self, path: Path) -> MediaTags:
        try:
            resolved = str(path.resolve())
        except OSError:
            resolved = str(path)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = -1.0
        cached = self._entries.get(resolved)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        tags = self._read(path)
        self._entries[resolved] = (mtime, tags)
        return tags

    @staticmethod
    def _read(path: Path) -> MediaTags:
        try:
            return read_tags(path)
        except (MetadataError, OSError, ValueError):
            return MediaTags()


def song_display_label(
    path: Path,
    *,
    mode: str,
    fmt: DisplayFormat,
    cache: TagCache | None = None,
) -> str:
    """Return the list label for *path* under the given display mode."""
    if mode != DISPLAY_MODE_METADATA:
        return display_name(path)
    tags = cache.get(path) if cache is not None else TagCache._read(path)
    if not tags.title.strip():
        return display_name(path)
    formatted = format_metadata_label(tags, fmt)
    return formatted if formatted else display_name(path)


def song_matches_query(
    path: Path,
    query: str,
    *,
    mode: str,
    fmt: DisplayFormat,
    cache: TagCache | None = None,
    label: str | None = None,
) -> bool:
    """Return True when *query* matches metadata label and/or filename."""
    needle = query.strip().lower()
    if not needle:
        return True
    display = label if label is not None else song_display_label(
        path, mode=mode, fmt=fmt, cache=cache
    )
    if needle in display.lower():
        return True
    if needle in path.name.lower():
        return True
    if mode == DISPLAY_MODE_METADATA:
        if needle in display_name(path).lower():
            return True
    return False
