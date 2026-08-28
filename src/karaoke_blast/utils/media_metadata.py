"""Read and write Title / Artist / Comment tags for supported media files."""

from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from mutagen.flac import FLAC
from mutagen.id3 import COMM, ID3, ID3NoHeaderError, TALB, TCON, TIT2, TPE1
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE

from karaoke_blast.utils.runtime_deps import resolve_ffmpeg_location, resolve_ffprobe_location

_MP4_EXTENSIONS = {".mp4", ".m4a", ".m4v", ".mov", ".aac"}
_OGG_EXTENSIONS = {".ogg", ".oga"}
_MUTAGEN_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".wav",
    ".opus",
    *_OGG_EXTENSIONS,
    ".m4a",
    ".aac",
    *_MP4_EXTENSIONS,
}
_FFMPEG_METADATA_EXTENSIONS = frozenset({".mkv", ".webm", ".avi"})
_SUPPORTED_EXTENSIONS = _MUTAGEN_EXTENSIONS | _FFMPEG_METADATA_EXTENSIONS


class MetadataError(Exception):
    """Raised when tags cannot be read or written."""


@dataclass(frozen=True)
class MediaTags:
    """Embedded title, artist, description, genre, and album values."""

    title: str = ""
    artist: str = ""
    comment: str = ""
    genre: str = ""
    album: str = ""

    def has_title_and_artist(self) -> bool:
        return bool(self.title.strip() and self.artist.strip())


def supports_metadata(path: Path) -> bool:
    """Return True when *path* can be tagged with the available tools."""
    suffix = path.suffix.lower()
    if suffix in _FFMPEG_METADATA_EXTENSIONS:
        return (
            resolve_ffmpeg_location() is not None
            and resolve_ffprobe_location() is not None
        )
    if suffix in _MUTAGEN_EXTENSIONS:
        return True
    return False


def _uses_ffmpeg_metadata(path: Path) -> bool:
    return path.suffix.lower() in _FFMPEG_METADATA_EXTENSIONS


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


def _tag_value(tags: dict[str, object], *names: str) -> str:
    lowered = {str(key).lower(): value for key, value in tags.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is None:
            continue
        text = _first_text(value)
        if text:
            return text
    return ""


def _read_ffmpeg_tags(path: Path) -> MediaTags:
    ffprobe = resolve_ffprobe_location()
    if ffprobe is None:
        raise MetadataError("ffprobe is required to read metadata from video files.")
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise MetadataError(f"Could not run ffprobe: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise MetadataError(f"Could not read metadata with ffprobe: {detail}")
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise MetadataError("Could not parse ffprobe metadata output.") from exc
    raw_tags = payload.get("format", {}).get("tags")
    tags = raw_tags if isinstance(raw_tags, dict) else {}
    return MediaTags(
        title=_tag_value(
            tags,
            "30/title",
            "50/title",
            "track/title",
            "movie/title",
            "title",
        ),
        artist=_tag_value(
            tags,
            "0/artist",
            "artist",
            "50/artist",
            "track/artist",
            "album_artist",
        ),
        comment=_tag_value(
            tags,
            "0/description",
            "0/comment",
            "description",
            "comment",
            "50/description",
            "50/comment",
        ),
        album=_tag_value(tags, "0/album", "album", "50/album"),
        genre=_tag_value(
            tags,
            "0/genre",
            "genre",
            "50/genre",
            "0/GENRE",
            "GENRE",
        ),
    )


def _ffmpeg_metadata_args(
    suffix: str,
    *,
    title: str,
    artist: str,
    comment: str,
    genre: str,
    album: str,
) -> list[str]:
    """Build ffmpeg -metadata arguments in a form VLC can read."""
    pairs: list[tuple[str, str]] = []
    if suffix == ".mkv":
        # VLC's Matroska demuxer maps TITLE@30 -> Title, ARTIST@0 -> Artist, etc.
        pairs.extend(
            [
                ("30/TITLE", title),
                ("title", title),
                ("0/ARTIST", artist),
                ("ARTIST", artist),
                ("0/DESCRIPTION", comment),
                ("0/COMMENT", comment),
                ("DESCRIPTION", comment),
                ("COMMENT", comment),
            ]
        )
        if album:
            pairs.extend([("0/ALBUM", album), ("ALBUM", album)])
        if genre:
            pairs.extend([("0/GENRE", genre), ("GENRE", genre), ("genre", genre)])
    elif suffix == ".webm":
        pairs.extend(
            [
                ("title", title),
                ("artist", artist),
                ("description", comment),
                ("comment", comment),
            ]
        )
        if album:
            pairs.append(("album", album))
        if genre:
            pairs.append(("genre", genre))
    else:
        pairs.extend(
            [
                ("title", title),
                ("artist", artist),
                ("comment", comment),
                ("description", comment),
                ("INAM", title),
                ("IART", artist),
                ("ICMT", comment),
            ]
        )
        if album:
            pairs.append(("album", album))
        if genre:
            pairs.extend([("genre", genre), ("IGNR", genre)])
    args: list[str] = []
    for key, value in pairs:
        args.extend(["-metadata", f"{key}={value}"])
    return args


def _write_ffmpeg_tags(
    path: Path,
    title: str,
    artist: str,
    comment: str | None,
    album: str | None = None,
    genre: str | None = None,
) -> None:
    ffmpeg = resolve_ffmpeg_location()
    if ffmpeg is None:
        raise MetadataError("ffmpeg is required to write metadata to video files.")
    if comment is None or album is None or genre is None:
        existing = _read_ffmpeg_tags(path)
        if comment is None:
            comment = existing.comment
        if album is None:
            album = existing.album
        if genre is None:
            genre = existing.genre

    temp_path = path.with_name(f".karaoke-blast-meta-{uuid.uuid4().hex}{path.suffix}")
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-c",
        "copy",
        "-map",
        "0",
        "-map_metadata",
        "0",
        *_ffmpeg_metadata_args(
            path.suffix.lower(),
            title=title,
            artist=artist,
            comment=comment,
            album=album,
            genre=genre,
        ),
        str(temp_path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        raise MetadataError(f"Could not run ffmpeg: {exc}") from exc
    if result.returncode != 0:
        temp_path.unlink(missing_ok=True)
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise MetadataError(f"Could not write metadata with ffmpeg: {detail}")
    try:
        temp_path.replace(path)
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        raise MetadataError(f"Could not replace tagged file: {exc}") from exc


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
            genre=_first_text(tags.get("TCON")),
            album=_first_text(tags.get("TALB")),
        )
    except Exception as exc:  # noqa: BLE001
        raise MetadataError(f"Could not read MP3 tags: {exc}") from exc


def _write_mp3(
    path: Path,
    title: str,
    artist: str,
    comment: str | None,
    album: str | None = None,
    genre: str | None = None,
) -> None:
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
        if album is not None:
            tags.delall("TALB")
            if album:
                tags.add(TALB(encoding=3, text=album))
        if genre is not None:
            tags.delall("TCON")
            if genre:
                tags.add(TCON(encoding=3, text=genre))
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
        artist=_first_text(tags.get("\xa9ART")) or _first_text(tags.get("\xa9aut")),
        comment=_first_text(tags.get("\xa9cmt")) or _first_text(tags.get("desc")),
        genre=_first_text(tags.get("\xa9gen")),
        album=_first_text(tags.get("\xa9alb")),
    )


def _write_mp4(
    path: Path,
    title: str,
    artist: str,
    comment: str | None,
    album: str | None = None,
    genre: str | None = None,
) -> None:
    try:
        audio = MP4(path)
        if audio.tags is None:
            audio.add_tags()
        assert audio.tags is not None
        audio.tags["\xa9nam"] = [title]
        audio.tags["\xa9ART"] = [artist]
        audio.tags["\xa9aut"] = [artist]
        if comment is not None:
            audio.tags["\xa9cmt"] = [comment]
            audio.tags["desc"] = [comment]
        if album is not None:
            audio.tags["\xa9alb"] = [album]
        if genre is not None:
            audio.tags["\xa9gen"] = [genre]
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
        genre=_first_text(audio.get("genre")),
        album=_first_text(audio.get("album")),
    )


def _write_flac(
    path: Path,
    title: str,
    artist: str,
    comment: str | None,
    album: str | None = None,
    genre: str | None = None,
) -> None:
    try:
        audio = FLAC(path)
        audio["title"] = [title]
        audio["artist"] = [artist]
        if comment is not None:
            audio["comment"] = [comment]
        if album is not None:
            audio["album"] = [album]
        if genre is not None:
            audio["genre"] = [genre]
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
        genre=_first_text(audio.get("genre")),
        album=_first_text(audio.get("album")),
    )


def _write_ogg(
    path: Path,
    title: str,
    artist: str,
    comment: str | None,
    album: str | None = None,
    genre: str | None = None,
) -> None:
    try:
        if path.suffix.lower() == ".opus":
            audio = OggOpus(path)
        else:
            audio = OggVorbis(path)
        audio["title"] = [title]
        audio["artist"] = [artist]
        if comment is not None:
            audio["comment"] = [comment]
        if album is not None:
            audio["album"] = [album]
        if genre is not None:
            audio["genre"] = [genre]
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
    return MediaTags(
        title=title,
        artist=artist,
        comment=comment,
        genre=_first_text(tags.get("TCON")),
        album=_first_text(tags.get("TALB")),
    )


def _write_wav(
    path: Path,
    title: str,
    artist: str,
    comment: str | None,
    album: str | None = None,
    genre: str | None = None,
) -> None:
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
        if album is not None:
            audio.tags.delall("TALB")
            if album:
                audio.tags.add(TALB(encoding=3, text=album))
        if genre is not None:
            audio.tags.delall("TCON")
            if genre:
                audio.tags.add(TCON(encoding=3, text=genre))
        audio.save()
    except Exception as exc:  # noqa: BLE001
        raise MetadataError(f"Could not write WAV tags: {exc}") from exc


def read_tags(path: Path) -> MediaTags:
    """Read Title / Artist / Comment from *path*."""
    suffix = path.suffix.lower()
    if _uses_ffmpeg_metadata(path):
        return _read_ffmpeg_tags(path)
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
    description: str | None = None,
    album: str | None = None,
    genre: str | None = None,
) -> None:
    """Write Title / Artist and optionally Description, Genre, and Album to *path*.

    Pass ``comment=None`` and ``description=None`` to leave description unchanged.
    Pass ``album=None`` to leave the existing album unchanged.
    Pass ``genre=None`` to leave the existing genre unchanged.
    """
    title = title.strip()
    artist = artist.strip()
    desc = description if description is not None else comment
    if desc is not None:
        desc = desc.strip()
    if album is not None:
        album = album.strip()
    if genre is not None:
        genre = genre.strip()
    if not title:
        raise MetadataError("Title cannot be empty.")

    suffix = path.suffix.lower()
    if _uses_ffmpeg_metadata(path):
        _write_ffmpeg_tags(path, title, artist, desc, album, genre)
        return
    if suffix == ".mp3":
        _write_mp3(path, title, artist, desc, album, genre)
    elif suffix in _MP4_EXTENSIONS:
        _write_mp4(path, title, artist, desc, album, genre)
    elif suffix == ".flac":
        _write_flac(path, title, artist, desc, album, genre)
    elif suffix == ".opus" or suffix in _OGG_EXTENSIONS:
        _write_ogg(path, title, artist, desc, album, genre)
    elif suffix == ".wav":
        _write_wav(path, title, artist, desc, album, genre)
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
