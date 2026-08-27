"""Map filename slots to VLC-compatible embedded metadata fields."""

from __future__ import annotations

from dataclasses import dataclass, field

from karaoke_blast.utils.filename_rename import (
    FilenameFormat,
    SLOT_KIND_ADDITIONAL,
    SLOT_KIND_ARTIST,
    SLOT_KIND_SONG,
    apply_slot_casing,
)

VLC_FIELD_TITLE = "title"
VLC_FIELD_ARTIST = "artist"
VLC_FIELD_DESCRIPTION = "description"
VLC_FIELD_ALBUM = "album"

VLC_METADATA_FIELDS = (
    VLC_FIELD_TITLE,
    VLC_FIELD_ARTIST,
    VLC_FIELD_DESCRIPTION,
    VLC_FIELD_ALBUM,
)

VLC_METADATA_FIELD_LABELS = {
    VLC_FIELD_TITLE: "Title",
    VLC_FIELD_ARTIST: "Artist",
    VLC_FIELD_DESCRIPTION: "Description",
    VLC_FIELD_ALBUM: "Album",
}

_DESCRIPTION_JOIN = "; "


@dataclass
class MetadataFieldMapping:
    """Per media type: which rename slots populate each VLC metadata field."""

    title_slot: int | None = None
    artist_slot: int | None = None
    description_slots: list[int] = field(default_factory=list)
    album_slot: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "title_slot": self.title_slot,
            "artist_slot": self.artist_slot,
            "description_slots": list(self.description_slots),
            "album_slot": self.album_slot,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> MetadataFieldMapping:
        if not data:
            return cls()
        title_slot = data.get("title_slot")
        artist_slot = data.get("artist_slot")
        album_slot = data.get("album_slot")
        raw_description = data.get("description_slots")
        description_slots: list[int] = []
        if isinstance(raw_description, list):
            for item in raw_description:
                if isinstance(item, int) and 0 <= item < 4 and item not in description_slots:
                    description_slots.append(item)
        return cls(
            title_slot=title_slot if isinstance(title_slot, int) and 0 <= title_slot < 4 else None,
            artist_slot=artist_slot if isinstance(artist_slot, int) and 0 <= artist_slot < 4 else None,
            description_slots=description_slots,
            album_slot=album_slot if isinstance(album_slot, int) and 0 <= album_slot < 4 else None,
        )

    def copy(self) -> MetadataFieldMapping:
        return MetadataFieldMapping.from_dict(self.to_dict())

    def normalize_for_format(self, fmt: FilenameFormat) -> MetadataFieldMapping:
        """Drop mappings that reference disabled or invalid slots."""
        enabled = set(fmt.enabled_slot_indices())
        return MetadataFieldMapping(
            title_slot=self.title_slot if self.title_slot in enabled else None,
            artist_slot=self.artist_slot if self.artist_slot in enabled else None,
            description_slots=[
                index for index in self.description_slots if index in enabled
            ][:1],
            album_slot=self.album_slot if self.album_slot in enabled else None,
        )


def _slot_text(
    fmt: FilenameFormat,
    slot_values: dict[int, str],
    slot_index: int | None,
) -> str:
    if slot_index is None or not (0 <= slot_index < len(fmt.slots)):
        return ""
    slot = fmt.slots[slot_index]
    if not slot.enabled:
        return ""
    raw = slot_values.get(slot_index, "").strip()
    return apply_slot_casing(raw, slot.kind, fmt)


def resolve_vlc_metadata(
    fmt: FilenameFormat,
    mapping: MetadataFieldMapping,
    slot_values: dict[int, str],
) -> dict[str, str]:
    """Build VLC field values from slot text using *mapping*."""
    normalized = mapping.normalize_for_format(fmt)
    description_parts: list[str] = []
    for index in normalized.description_slots:
        text = _slot_text(fmt, slot_values, index)
        if text and text not in description_parts:
            description_parts.append(text)
    return {
        VLC_FIELD_TITLE: _slot_text(fmt, slot_values, normalized.title_slot),
        VLC_FIELD_ARTIST: _slot_text(fmt, slot_values, normalized.artist_slot),
        VLC_FIELD_DESCRIPTION: _DESCRIPTION_JOIN.join(description_parts),
        VLC_FIELD_ALBUM: _slot_text(fmt, slot_values, normalized.album_slot),
    }


def default_metadata_mapping(
    fmt: FilenameFormat,
    *,
    legacy_comment_slot_indices: list[int] | None = None,
) -> MetadataFieldMapping:
    """Infer a sensible mapping from slot kinds and legacy comment settings."""
    title_slot = fmt.song_slot_index()
    artist_slot = None
    for index, slot in enumerate(fmt.slots):
        if slot.kind == SLOT_KIND_ARTIST and slot.enabled:
            artist_slot = index
            break

    description_slots: list[int] = []
    if legacy_comment_slot_indices is not None:
        description_slots = [
            index
            for index in legacy_comment_slot_indices
            if 0 <= index < len(fmt.slots) and fmt.slots[index].enabled
        ]
    if not description_slots:
        for index in fmt.enabled_slot_indices():
            slot = fmt.slots[index]
            if slot.kind == SLOT_KIND_ADDITIONAL:
                description_slots.append(index)
                break

    used = {slot for slot in (title_slot, artist_slot) if slot is not None}
    description_slots = [
        index for index in description_slots if index not in used
    ]

    return MetadataFieldMapping(
        title_slot=title_slot,
        artist_slot=artist_slot,
        description_slots=description_slots,
        album_slot=None,
    )


def metadata_field_display_labels(
    fmt: FilenameFormat,
    mapping: MetadataFieldMapping,
) -> dict[str, str]:
    """Return UI labels for VLC fields based on mapped slot names."""
    normalized = mapping.normalize_for_format(fmt)
    labels = dict(VLC_METADATA_FIELD_LABELS)

    if normalized.title_slot is not None:
        labels[VLC_FIELD_TITLE] = fmt.slots[normalized.title_slot].label
    if normalized.artist_slot is not None:
        labels[VLC_FIELD_ARTIST] = fmt.slots[normalized.artist_slot].label
    if normalized.album_slot is not None:
        labels[VLC_FIELD_ALBUM] = fmt.slots[normalized.album_slot].label

    description_labels = [
        fmt.slots[index].label
        for index in normalized.description_slots
        if 0 <= index < len(fmt.slots)
    ]
    if len(description_labels) == 1:
        labels[VLC_FIELD_DESCRIPTION] = description_labels[0]
    elif description_labels:
        labels[VLC_FIELD_DESCRIPTION] = " / ".join(description_labels)

    return labels


def builtin_metadata_mapping(profile_id: str, fmt: FilenameFormat) -> MetadataFieldMapping:
    """Factory defaults for built-in media types."""
    if profile_id == "songs":
        return MetadataFieldMapping(
            title_slot=0,
            artist_slot=1,
            description_slots=[2] if len(fmt.slots) > 2 and fmt.slots[2].enabled else [],
            album_slot=None,
        )
    if profile_id in {"music_videos", "music_audio"}:
        return MetadataFieldMapping(
            title_slot=0,
            artist_slot=1,
            description_slots=[],
            album_slot=2 if len(fmt.slots) > 2 and fmt.slots[2].enabled else None,
        )
    if profile_id == "tv_shows":
        return MetadataFieldMapping(
            title_slot=0,
            artist_slot=1,
            description_slots=[2] if len(fmt.slots) > 2 and fmt.slots[2].enabled else [],
            album_slot=None,
        )
    if profile_id == "movies":
        return MetadataFieldMapping(
            title_slot=0,
            artist_slot=1,
            description_slots=[2] if len(fmt.slots) > 2 and fmt.slots[2].enabled else [],
            album_slot=None,
        )
    if profile_id == "personal_videos":
        mapping = MetadataFieldMapping(
            title_slot=0,
            artist_slot=1,
            description_slots=[2] if len(fmt.slots) > 2 and fmt.slots[2].enabled else [],
            album_slot=3 if len(fmt.slots) > 3 and fmt.slots[3].enabled else None,
        )
        return mapping.normalize_for_format(fmt)
    return default_metadata_mapping(fmt)
