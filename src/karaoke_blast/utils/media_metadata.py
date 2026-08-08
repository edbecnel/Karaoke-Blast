"""Read and write Title / Artist / Comment tags for supported media files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mutagen.flac import FLAC
from mutagen.id3 import COMM, ID3, ID3NoHeaderError, TIT2, TPE1
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE

_MP4_EXTENSIONS = {".mp4", ".m4a", ".m4v", ".aac"}
_OGG_EXTENSIONS = {".ogg", ".oga"}
_SUPPORTED_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".wav",
    ".opus",
    *_MP4_EXTENSIONS,
    *_OGG_EXTENSIONS,
}


class MetadataError(Exception):
    """Raised when tags cannot be read or written."""


@dataclass(frozen=True)
class MediaTags:
    """Embedded title, artist, and comment values."""

    title: str = ""
    artist: str = ""
    comment: str = ""

    def has_title_and_artist(self) -> bool:
        return bool(self.title.strip() and self.artist.strip())


def supports_metadata(path: Path) -> bool:
    """Return True when *path* uses a container mutagen can tag."""
    return path.suffix.lower() in _SUPPORTED_EXTENSIONS


def _first_text(values: object) -> str:
    if values is None:
        return ""
    if isinstance(values, str):
        return values.strip()
    text_attr = getattr(values, "text", None)
    if text_attr is not None and not callable(text_attr):
        return _first_text(text_attr)
    if isinstance(values, (list, tuple)):
        for item in values:
            text = _first_text(item)
            if text:
                return text
        return ""
    return str(values).strip()


def _id3_comment(tags: ID3) -> str:
    for frame in tags.getall("COMM"):
        text = _first_text(getattr(frame, "text", None))
        if text:
            return text
    return ""


def _read_mp3(path: Path) -> MediaTags:
    try:
        try:
            tags = ID3(path)
        except ID3NoHeaderError:
            return MediaTags()
        return MediaTags(
            title=_first_text(tags.get("TIT2")),
            artist=_first_text(tags.get("TPE1")),
            comment=_id3_comment(tags),
        )
    except Exception as exc:  # noqa: BLE001
        raise MetadataError(f"Could not read MP3 tags: {exc}") from exc


def _write_mp3(path: Path, title: str, artist: str, comment: str | None) -> None:
    try:
        try:
            tags = ID3(path)
        except ID3NoHeaderError:
            tags = ID3()
        tags.delall("TIT2")
        tags.delall("TPE1")
        tags.add(TIT2(encoding=3, text=title))
        tags.add(TPE1(encoding=3, text=artist))
        if comment is not None:
            tags.delall("COMM")
            if comment:
                tags.add(COMM(encoding=3, lang="eng", desc="", text=comment))
        tags.save(path)
    except Exception as exc:  # noqa: BLE001
        raise MetadataError(f"Could not write MP3 tags: {exc}") from exc


def _read_mp4(path: Path) -> MediaTags:
    try:
        audio = MP4(path)
    except Exception as exc:  # noqa: BLE001
        raise MetadataError(f"Could not read MP4 tags: {exc}") from exc
    tags = audio.tags or {}
    return MediaTags(
        title=_first_text(tags.get("\xa9nam")),
        artist=_first_text(tags.get("\xa9ART")),
        comment=_first_text(tags.get("\xa9cmt")),
    )


def _write_mp4(path: Path, title: str, artist: str, comment: str | None) -> None:
    try:
        audio = MP4(path)
        if audio.tags is None:
            audio.add_tags()
        assert audio.tags is not None
        audio.tags["\xa9nam"] = [title]
        audio.tags["\xa9ART"] = [artist]
        if comment is not None:
            audio.tags["\xa9cmt"] = [comment]
        audio.save()
    except Exception as exc:  # noqa: BLE001
        raise MetadataError(f"Could not write MP4 tags: {exc}") from exc


def _read_flac(path: Path) -> MediaTags:
    try:
        audio = FLAC(path)
    except Exception as exc:  # noqa: BLE001
        raise MetadataError(f"Could not read FLAC tags: {exc}") from exc
    return MediaTags(
        title=_first_text(audio.get("title")),
        artist=_first_text(audio.get("artist")),
        comment=_first_text(audio.get("comment")),
    )


def _write_flac(path: Path, title: str, artist: str, comment: str | None) -> None:
    try:
        audio = FLAC(path)
        audio["title"] = [title]
        audio["artist"] = [artist]
        if comment is not None:
            audio["comment"] = [comment]
        audio.save()
    except Exception as exc:  # noqa: BLE001
        raise MetadataError(f"Could not write FLAC tags: {exc}") from exc


def _read_ogg(path: Path) -> MediaTags:
    try:
        if path.suffix.lower() == ".opus":
            audio = OggOpus(path)
        else:
            audio = OggVorbis(path)
    except Exception as exc:  # noqa: BLE001
        raise MetadataError(f"Could not read Ogg tags: {exc}") from exc
    return MediaTags(
        title=_first_text(audio.get("title")),
        artist=_first_text(audio.get("artist")),
        comment=_first_text(audio.get("comment")),
    )


def _write_ogg(path: Path, title: str, artist: str, comment: str | None) -> None:
    try:
        if path.suffix.lower() == ".opus":
            audio = OggOpus(path)
        else:
            audio = OggVorbis(path)
        audio["title"] = [title]
        audio["artist"] = [artist]
        if comment is not None:
            audio["comment"] = [comment]
        audio.save()
    except Exception as exc:  # noqa: BLE001
        raise MetadataError(f"Could not write Ogg tags: {exc}") from exc


def _read_wav(path: Path) -> MediaTags:
    try:
        audio = WAVE(path)
    except Exception as exc:  # noqa: BLE001
        raise MetadataError(f"Could not read WAV tags: {exc}") from exc
    tags = audio.tags
    if tags is None:
        return MediaTags()
    title = _first_text(tags.get("TIT2"))
    artist = _first_text(tags.get("TPE1"))
    comment = _id3_comment(tags) if isinstance(tags, ID3) else ""
    return MediaTags(title=title, artist=artist, comment=comment)


def _write_wav(path: Path, title: str, artist: str, comment: str | None) -> None:
    try:
        audio = WAVE(path)
        if audio.tags is None:
            audio.add_tags()
        assert audio.tags is not None
        audio.tags.delall("TIT2")
        audio.tags.delall("TPE1")
        audio.tags.add(TIT2(encoding=3, text=title))
        audio.tags.add(TPE1(encoding=3, text=artist))
        if comment is not None:
            audio.tags.delall("COMM")
            if comment:
                audio.tags.add(COMM(encoding=3, lang="eng", desc="", text=comment))
        audio.save()
    except Exception as exc:  # noqa: BLE001
        raise MetadataError(f"Could not write WAV tags: {exc}") from exc


def read_tags(path: Path) -> MediaTags:
    """Read Title / Artist / Comment from *path*."""
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        return _read_mp3(path)
    if suffix in _MP4_EXTENSIONS:
        return _read_mp4(path)
    if suffix == ".flac":
        return _read_flac(path)
    if suffix == ".opus" or suffix in _OGG_EXTENSIONS:
        return _read_ogg(path)
    if suffix == ".wav":
        return _read_wav(path)
    raise MetadataError(
        f"Unsupported format for metadata: {suffix or '(no extension)'}"
    )


def write_tags(
    path: Path,
    *,
    title: str,
    artist: str,
    comment: str | None = None,
) -> None:
    """Write Title / Artist and optionally Comment to *path*.

    Pass ``comment=None`` to leave the existing comment unchanged.
    Pass ``comment=""`` to clear it.
    """
    title = title.strip()
    artist = artist.strip()
    if comment is not None:
        comment = comment.strip()
    if not title:
        raise MetadataError("Title cannot be empty.")

    suffix = path.suffix.lower()
    if suffix == ".mp3":
        _write_mp3(path, title, artist, comment)
    elif suffix in _MP4_EXTENSIONS:
        _write_mp4(path, title, artist, comment)
    elif suffix == ".flac":
        _write_flac(path, title, artist, comment)
    elif suffix == ".opus" or suffix in _OGG_EXTENSIONS:
        _write_ogg(path, title, artist, comment)
    elif suffix == ".wav":
        _write_wav(path, title, artist, comment)
    else:
        raise MetadataError(
            f"Unsupported format for metadata: {suffix or '(no extension)'}"
        )


def has_title_and_artist(path: Path) -> bool:
    """Return True when *path* already has both Title and Artist tags."""
    if not supports_metadata(path):
        return False
    try:
        return read_tags(path).has_title_and_artist()
    except MetadataError:
        return False
