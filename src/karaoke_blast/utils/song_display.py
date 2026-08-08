"""Song list display labels from filename or embedded metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from karaoke_blast.utils.display import display_name
from karaoke_blast.utils.media_metadata import MediaTags, MetadataError, read_tags

DISPLAY_MODE_FILENAME = "filename"
DISPLAY_MODE_METADATA = "metadata"

SLOT_KIND_TITLE = "title"
SLOT_KIND_ARTIST = "artist"
SLOT_KIND_COMMENT = "comment"

SLOT_KINDS = (SLOT_KIND_TITLE, SLOT_KIND_ARTIST, SLOT_KIND_COMMENT)
SLOT_COUNT = 3
SEPARATOR_COUNT = 2
DEFAULT_SEPARATORS = (" - ", " - ")

_KIND_LABELS = {
    SLOT_KIND_TITLE: "Song title",
    SLOT_KIND_ARTIST: "Artist",
    SLOT_KIND_COMMENT: "Comments",
}


@dataclass
class DisplaySlot:
    """One position in the metadata display format."""

    kind: str
    enabled: bool = True

    def to_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "enabled": self.enabled}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> DisplaySlot:
        kind = str(data.get("kind", SLOT_KIND_TITLE))
        if kind not in SLOT_KINDS:
            kind = SLOT_KIND_TITLE
        return cls(kind=kind, enabled=bool(data.get("enabled", True)))


@dataclass
class DisplayFormat:
    """Reorderable title / artist / comment slots with separators."""

    slots: list[DisplaySlot] = field(default_factory=list)
    separators: list[str] = field(default_factory=lambda: list(DEFAULT_SEPARATORS))

    def __post_init__(self) -> None:
        self._normalize_shape()

    def _normalize_shape(self) -> None:
        by_kind = {slot.kind: slot for slot in self.slots if slot.kind in SLOT_KINDS}
        ordered: list[DisplaySlot] = []
        seen: set[str] = set()
        for slot in self.slots:
            if slot.kind in SLOT_KINDS and slot.kind not in seen:
                ordered.append(DisplaySlot(slot.kind, enabled=slot.enabled))
                seen.add(slot.kind)
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
        DisplaySlot(SLOT_KIND_COMMENT, enabled=True),
    ],
    separators=list(DEFAULT_SEPARATORS),
)


def slot_kind_label(kind: str) -> str:
    return _KIND_LABELS.get(kind, kind)


def _slot_value(tags: MediaTags, kind: str) -> str:
    if kind == SLOT_KIND_TITLE:
        return tags.title.strip()
    if kind == SLOT_KIND_ARTIST:
        return tags.artist.strip()
    if kind == SLOT_KIND_COMMENT:
        return tags.comment.strip()
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


def format_display_preview(fmt: DisplayFormat) -> str:
    """Human-readable pattern preview for the format dialog."""
    fmt._normalize_shape()
    enabled = [index for index, slot in enumerate(fmt.slots) if slot.enabled]
    if not enabled:
        return ""
    parts: list[str] = []
    for position, index in enumerate(enabled):
        if position > 0:
            parts.append(fmt.separators[index - 1] if index > 0 else " - ")
        parts.append(f"{{{slot_kind_label(fmt.slots[index].kind)}}}")
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
        # Filename stem when label is metadata-only and query hits the stem.
        if needle in display_name(path).lower():
            return True
    return False
