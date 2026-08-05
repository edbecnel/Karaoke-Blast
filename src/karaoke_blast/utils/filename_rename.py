"""Filename parsing, composition, and safe rename for karaoke videos."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_YOUTUBE_ID_SUFFIX = re.compile(r"\s*\[[\w-]{6,}\]\s*$")
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')
_SPLIT_DELIMITERS = re.compile(r"\s*[-–—|｜]\s*|\s*\|\s*|_+|\s*\(\s*|\s*\)\s*")

SLOT_KIND_SONG = "song"
SLOT_KIND_ARTIST = "artist"
SLOT_KIND_ADDITIONAL = "additional"

DEFAULT_SEPARATORS = (" - ", " - ", " - ")
SLOT_COUNT = 4
SEPARATOR_COUNT = 3

# Legacy keys for migration
_LEGACY_DEFAULT_SLOT_NAMES = ("Song Name", "Artist Name")
_LEGACY_DEFAULT_SUFFIX = "Karaoke"


@dataclass
class FormatSlot:
    """One position in the filename format."""

    kind: str
    label: str
    enabled: bool = True
    hint: str = ""
    hint_fixed: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "label": self.label,
            "enabled": self.enabled,
            "hint": self.hint,
            "hint_fixed": self.hint_fixed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> FormatSlot:
        kind = str(data.get("kind", SLOT_KIND_ADDITIONAL))
        label = str(data.get("label", "Additional"))
        enabled = bool(data.get("enabled", True))
        hint = str(data.get("hint", "")) if data.get("hint") is not None else ""
        if "hint_fixed" in data:
            hint_fixed = bool(data.get("hint_fixed", False))
        elif hint and kind == SLOT_KIND_ADDITIONAL and hint == label:
            hint_fixed = True
        else:
            hint_fixed = False
        return cls(kind=kind, label=label, enabled=enabled, hint=hint, hint_fixed=hint_fixed)


@dataclass
class FilenameFormat:
    """Configurable filename layout: four reorderable slots and three separators."""

    slots: list[FormatSlot] = field(default_factory=list)
    separators: list[str] = field(default_factory=lambda: list(DEFAULT_SEPARATORS))

    def __post_init__(self) -> None:
        self._normalize_shape()

    def _normalize_shape(self) -> None:
        while len(self.slots) < SLOT_COUNT:
            self.slots.append(
                FormatSlot(SLOT_KIND_ADDITIONAL, "Additional", enabled=False, hint="")
            )
        self.slots = self.slots[:SLOT_COUNT]
        while len(self.separators) < SEPARATOR_COUNT:
            self.separators.append(" - ")
        self.separators = self.separators[:SEPARATOR_COUNT]

    def enabled_slot_indices(self) -> list[int]:
        return [index for index, slot in enumerate(self.slots) if slot.enabled]

    def song_slot_index(self) -> int | None:
        for index, slot in enumerate(self.slots):
            if slot.kind == SLOT_KIND_SONG:
                return index
        return None

    def slot_label(self, index: int) -> str:
        return self.slots[index].label

    def to_dict(self) -> dict[str, object]:
        self._normalize_shape()
        return {
            "slots": [slot.to_dict() for slot in self.slots],
            "separators": list(self.separators),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> FilenameFormat:
        if not data:
            return DEFAULT_KARAOKE_FORMAT.copy()
        if "slots" in data:
            return cls._from_new_dict(data)
        return cls._migrate_legacy_dict(data)

    @classmethod
    def _from_new_dict(cls, data: dict[str, object]) -> FilenameFormat:
        raw_slots = data.get("slots", [])
        separators = data.get("separators", DEFAULT_SEPARATORS)
        slots: list[FormatSlot] = []
        if isinstance(raw_slots, list):
            for entry in raw_slots:
                if isinstance(entry, dict):
                    slots.append(FormatSlot.from_dict(entry))
        fmt = cls(
            slots=slots,
            separators=[str(sep) for sep in separators]
            if isinstance(separators, list)
            else list(DEFAULT_SEPARATORS),
        )
        fmt._normalize_shape()
        return fmt

    @classmethod
    def _migrate_legacy_dict(cls, data: dict[str, object]) -> FilenameFormat:
        slot_names = data.get("slot_names", _LEGACY_DEFAULT_SLOT_NAMES)
        separators = data.get("separators", (" - ", " - "))
        suffix_enabled = bool(data.get("suffix_enabled", True))
        suffix_text = str(data.get("suffix_text", _LEGACY_DEFAULT_SUFFIX))

        names = (
            [str(name) for name in slot_names]
            if isinstance(slot_names, list)
            else list(_LEGACY_DEFAULT_SLOT_NAMES)
        )
        song_label = names[0] if names else "Song Name"
        artist_label = names[1] if len(names) > 1 else "Artist Name"

        legacy_seps = (
            [str(sep) for sep in separators]
            if isinstance(separators, list)
            else [" - ", " - "]
        )
        migrated_seps = [" - ", " - ", " - "]
        migrated_seps[0] = legacy_seps[0] if legacy_seps else " - "
        if suffix_enabled and suffix_text:
            migrated_seps[1] = legacy_seps[1] if len(legacy_seps) > 1 else " - "
            migrated_seps[2] = legacy_seps[1] if len(legacy_seps) > 1 else " - "
        elif len(legacy_seps) > 0:
            migrated_seps[1] = legacy_seps[0]

        return cls(
            slots=[
                FormatSlot(SLOT_KIND_SONG, song_label, enabled=True),
                FormatSlot(SLOT_KIND_ARTIST, artist_label, enabled=True),
                FormatSlot(
                    SLOT_KIND_ADDITIONAL,
                    suffix_text if suffix_text else "Karaoke",
                    enabled=suffix_enabled and bool(suffix_text),
                    hint=suffix_text if suffix_text else "Karaoke",
                    hint_fixed=bool(suffix_text),
                ),
                FormatSlot(SLOT_KIND_ADDITIONAL, "Additional", enabled=False, hint=""),
            ],
            separators=migrated_seps,
        )

    def copy(self) -> FilenameFormat:
        return FilenameFormat.from_dict(self.to_dict())


DEFAULT_KARAOKE_FORMAT = FilenameFormat(
    slots=[
        FormatSlot(SLOT_KIND_SONG, "Song Name", enabled=True),
        FormatSlot(SLOT_KIND_ARTIST, "Artist Name", enabled=True),
        FormatSlot(SLOT_KIND_ADDITIONAL, "Karaoke", enabled=True, hint="Karaoke", hint_fixed=True),
        FormatSlot(SLOT_KIND_ADDITIONAL, "Additional", enabled=False, hint=""),
    ],
    separators=list(DEFAULT_SEPARATORS),
)

SONG_ARTIST_FORMAT = FilenameFormat(
    slots=[
        FormatSlot(SLOT_KIND_SONG, "Song Name", enabled=True),
        FormatSlot(SLOT_KIND_ARTIST, "Artist Name", enabled=True),
        FormatSlot(SLOT_KIND_ADDITIONAL, "Karaoke", enabled=False, hint="Karaoke"),
        FormatSlot(SLOT_KIND_ADDITIONAL, "Additional", enabled=False, hint=""),
    ],
    separators=list(DEFAULT_SEPARATORS),
)

# Backward-compatible alias used by older imports.
NO_SUFFIX_FORMAT = SONG_ARTIST_FORMAT


class RenameError(Exception):
    """Raised when a rename cannot be performed."""


def strip_youtube_id(stem: str) -> str:
    """Remove a trailing YouTube video id suffix like ``[abc123XYZ]``."""
    return _YOUTUBE_ID_SUFFIX.sub("", stem).strip()


def split_title(stem: str) -> list[str]:
    """Split a title stem into non-empty parts using common karaoke delimiters."""
    cleaned = strip_youtube_id(stem)
    parts = [part.strip() for part in _SPLIT_DELIMITERS.split(cleaned)]
    return [part for part in parts if part]


def default_slot_values(stem: str, fmt: FilenameFormat) -> dict[int, str]:
    """Suggest initial rename values from a filename stem and format configuration."""
    fmt._normalize_shape()
    values: dict[int, str] = {}
    parts = split_title(stem)
    part_index = 0

    for slot_index in fmt.enabled_slot_indices():
        slot = fmt.slots[slot_index]
        if slot.kind == SLOT_KIND_ADDITIONAL and slot.hint_fixed and slot.hint:
            values[slot_index] = slot.hint
            continue

        if part_index < len(parts):
            values[slot_index] = parts[part_index]
            part_index += 1

    return values


def sanitize_filename(name: str) -> str:
    """Remove invalid filename characters while preserving intentional separators."""
    cleaned = _INVALID_FILENAME_CHARS.sub("", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.rstrip(". ")
    return cleaned


def compose_filename(slot_values: dict[int, str], fmt: FilenameFormat) -> str:
    """Build a filename stem from per-slot values and format configuration."""
    fmt._normalize_shape()
    included: list[tuple[int, str]] = []
    for index, slot in enumerate(fmt.slots):
        if not slot.enabled:
            continue
        value = slot_values.get(index, "").strip()
        if value:
            included.append((index, value))

    song_index = fmt.song_slot_index()
    if song_index is not None and fmt.slots[song_index].enabled:
        if not slot_values.get(song_index, "").strip():
            return ""

    if not included:
        return ""

    result = included[0][1]
    for position in range(1, len(included)):
        index = included[position][0]
        separator = fmt.separators[index - 1] if index > 0 else " - "
        result += separator + included[position][1]

    return sanitize_filename(result)


def format_preview(fmt: FilenameFormat) -> str:
    """Return a human-readable pattern preview for the UI."""
    fmt._normalize_shape()
    enabled_indices = fmt.enabled_slot_indices()
    if not enabled_indices:
        return ""

    parts: list[str] = []
    for position, index in enumerate(enabled_indices):
        if position > 0:
            parts.append(fmt.separators[index - 1] if index > 0 else " - ")
        parts.append(f"{{{fmt.slots[index].label}}}")
    return "".join(parts)


def _parse_slots_backtrack(
    remaining: str,
    fmt: FilenameFormat,
    enabled_indices: list[int],
    position: int,
) -> dict[int, str] | None:
    if position < 0:
        return {} if not remaining.strip() else None

    slot_index = enabled_indices[position]
    slot = fmt.slots[slot_index]

    if position == 0:
        value = remaining.strip()
        if not value:
            return None
        return {slot_index: value}

    separator = fmt.separators[slot_index - 1] if slot_index > 0 else ""
    if separator and separator in remaining:
        head, _, tail = remaining.rpartition(separator)
        if tail.strip():
            parsed = _parse_slots_backtrack(head, fmt, enabled_indices, position - 1)
            if parsed is not None:
                parsed[slot_index] = tail.strip()
                return parsed

    if slot.kind != SLOT_KIND_SONG:
        return _parse_slots_backtrack(remaining, fmt, enabled_indices, position - 1)

    return None


def parse_slots_from_stem(stem: str, fmt: FilenameFormat) -> dict[int, str] | None:
    """Parse a filename stem into slot values when it matches *fmt*, else None."""
    cleaned = strip_youtube_id(stem)
    if not cleaned:
        return None

    enabled_indices = fmt.enabled_slot_indices()
    if not enabled_indices:
        return None

    return _parse_slots_backtrack(cleaned, fmt, enabled_indices, len(enabled_indices) - 1)


def looks_canonical(path: Path, fmt: FilenameFormat) -> bool:
    """Return True when *path* already matches the configured format."""
    slots = parse_slots_from_stem(path.stem, fmt)
    if slots is None:
        return False
    recomposed = compose_filename(slots, fmt)
    if not recomposed:
        return False
    return recomposed == strip_youtube_id(path.stem)


def safe_rename(path: Path, new_stem: str) -> Path:
    """Rename *path* to *new_stem* plus the original extension."""
    cleaned = sanitize_filename(new_stem)
    if not cleaned:
        raise RenameError("Filename cannot be empty.")

    target = path.with_name(cleaned + path.suffix)
    if target.resolve() == path.resolve():
        return path
    if target.exists():
        raise RenameError(f"A file named '{target.name}' already exists.")

    path.rename(target)
    return target
