"""Filename parsing, composition, and safe rename for karaoke videos."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_YOUTUBE_ID_SUFFIX = re.compile(r"\s*\[[\w-]{6,}\]\s*$")
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')
_SPLIT_DELIMITERS = re.compile(r"\s*[-–—|｜]\s*|\s*\|\s*|_+|\s*\(\s*|\s*\)\s*")

DEFAULT_SLOT_NAMES = ("Song Name", "Artist Name")
DEFAULT_SEPARATORS = (" - ", " - ")
DEFAULT_SUFFIX_TEXT = "Karaoke"


@dataclass
class FilenameFormat:
    """Configurable filename layout: slots, separators, and optional suffix."""

    slot_names: list[str] = field(default_factory=lambda: list(DEFAULT_SLOT_NAMES))
    separators: list[str] = field(default_factory=lambda: list(DEFAULT_SEPARATORS))
    suffix_enabled: bool = True
    suffix_text: str = DEFAULT_SUFFIX_TEXT

    def normalized_separators(self) -> list[str]:
        """Return separators sized for the current slot/suffix configuration."""
        needed = len(self.slot_names) - 1
        if self.suffix_enabled and self.suffix_text:
            needed += 1
        separators = list(self.separators[:needed])
        while len(separators) < needed:
            separators.append(" - ")
        return separators

    def to_dict(self) -> dict[str, object]:
        return {
            "slot_names": list(self.slot_names),
            "separators": list(self.separators),
            "suffix_enabled": self.suffix_enabled,
            "suffix_text": self.suffix_text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> FilenameFormat:
        if not data:
            return DEFAULT_KARAOKE_FORMAT.copy()
        slot_names = data.get("slot_names", DEFAULT_SLOT_NAMES)
        separators = data.get("separators", DEFAULT_SEPARATORS)
        suffix_enabled = data.get("suffix_enabled", True)
        suffix_text = data.get("suffix_text", DEFAULT_SUFFIX_TEXT)
        fmt = cls(
            slot_names=[str(name) for name in slot_names] if isinstance(slot_names, list) else list(DEFAULT_SLOT_NAMES),
            separators=[str(sep) for sep in separators] if isinstance(separators, list) else list(DEFAULT_SEPARATORS),
            suffix_enabled=bool(suffix_enabled),
            suffix_text=str(suffix_text) if isinstance(suffix_text, str) else DEFAULT_SUFFIX_TEXT,
        )
        if not fmt.slot_names:
            fmt.slot_names = list(DEFAULT_SLOT_NAMES)
        return fmt

    def copy(self) -> FilenameFormat:
        return FilenameFormat.from_dict(self.to_dict())


DEFAULT_KARAOKE_FORMAT = FilenameFormat(
    slot_names=list(DEFAULT_SLOT_NAMES),
    separators=list(DEFAULT_SEPARATORS),
    suffix_enabled=True,
    suffix_text=DEFAULT_SUFFIX_TEXT,
)

NO_SUFFIX_FORMAT = FilenameFormat(
    slot_names=list(DEFAULT_SLOT_NAMES),
    separators=[" - "],
    suffix_enabled=False,
    suffix_text="",
)


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


def sanitize_filename(name: str) -> str:
    """Remove invalid filename characters while preserving intentional separators."""
    cleaned = _INVALID_FILENAME_CHARS.sub("", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.rstrip(". ")
    return cleaned


def compose_filename(slots: dict[str, str], fmt: FilenameFormat) -> str:
    """Build a filename stem from slot values and format configuration."""
    values = [slots.get(name, "").strip() for name in fmt.slot_names]
    if not values or not values[0]:
        return ""

    separators = fmt.normalized_separators()
    result = values[0]
    for index in range(1, len(values)):
        separator = separators[index - 1] if index - 1 < len(separators) else " - "
        result += separator + values[index]

    if fmt.suffix_enabled and fmt.suffix_text:
        suffix_sep_index = len(values) - 1
        separator = (
            separators[suffix_sep_index]
            if suffix_sep_index < len(separators)
            else " - "
        )
        result += separator + fmt.suffix_text

    return sanitize_filename(result)


def format_preview(fmt: FilenameFormat) -> str:
    """Return a human-readable pattern preview for the UI."""
    separators = fmt.normalized_separators()
    parts: list[str] = []
    for index, slot_name in enumerate(fmt.slot_names):
        if index > 0:
            sep_index = index - 1
            parts.append(separators[sep_index] if sep_index < len(separators) else " - ")
        parts.append(f"{{{slot_name}}}")
    if fmt.suffix_enabled and fmt.suffix_text:
        suffix_sep_index = len(fmt.slot_names) - 1
        parts.append(
            separators[suffix_sep_index]
            if suffix_sep_index < len(separators)
            else " - "
        )
        parts.append(fmt.suffix_text)
    return "".join(parts)


def parse_slots_from_stem(stem: str, fmt: FilenameFormat) -> dict[str, str] | None:
    """Parse a filename stem into slot values when it matches *fmt*, else None."""
    cleaned = strip_youtube_id(stem)
    if not cleaned:
        return None

    separators = fmt.normalized_separators()
    remaining = cleaned

    if fmt.suffix_enabled and fmt.suffix_text:
        suffix_sep_index = len(fmt.slot_names) - 1
        suffix_sep = (
            separators[suffix_sep_index]
            if suffix_sep_index < len(separators)
            else " - "
        )
        suffix = suffix_sep + fmt.suffix_text
        if not remaining.endswith(suffix):
            return None
        remaining = remaining[: -len(suffix)]

    if not fmt.slot_names:
        return None

    values: list[str] = [""] * len(fmt.slot_names)
    for index in range(len(fmt.slot_names) - 1, 0, -1):
        sep = separators[index - 1] if index - 1 < len(separators) else " - "
        if sep not in remaining:
            return None
        head, _, tail = remaining.rpartition(sep)
        if not tail.strip():
            return None
        values[index] = tail.strip()
        remaining = head
    if not remaining.strip():
        return None
    values[0] = remaining.strip()

    return dict(zip(fmt.slot_names, values, strict=True))


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
