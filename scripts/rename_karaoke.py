#!/usr/bin/env python3
"""CLI for batch-renaming karaoke video files to a standard format."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from karaoke_blast.storage.paths import config_dir
from karaoke_blast.utils.filename_rename import (
    DEFAULT_KARAOKE_FORMAT,
    FilenameFormat,
    RenameError,
    compose_filename,
    looks_canonical,
    safe_rename,
    split_title,
)
from karaoke_blast.utils.video_scanner import scan_videos


def _load_settings_format() -> tuple[FilenameFormat, bool]:
    settings_path = config_dir() / "settings.json"
    if not settings_path.exists():
        return DEFAULT_KARAOKE_FORMAT.copy(), True
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_KARAOKE_FORMAT.copy(), True

    rename_data = data.get("filename_rename")
    fmt = (
        FilenameFormat.from_dict(rename_data)
        if isinstance(rename_data, dict)
        else DEFAULT_KARAOKE_FORMAT.copy()
    )
    skip_canonical = data.get("filename_rename_skip_canonical", True)
    return fmt, bool(skip_canonical)


def _build_format(args: argparse.Namespace) -> FilenameFormat:
    if args.separators or args.suffix is not None or args.no_suffix or args.slots:
        slots = args.slots or list(DEFAULT_KARAOKE_FORMAT.slot_names)
        separators = args.separators or list(DEFAULT_KARAOKE_FORMAT.separators)
        suffix_enabled = not args.no_suffix
        suffix_text = args.suffix if args.suffix is not None else DEFAULT_KARAOKE_FORMAT.suffix_text
        return FilenameFormat(
            slot_names=slots,
            separators=separators,
            suffix_enabled=suffix_enabled,
            suffix_text=suffix_text,
        )
    fmt, _skip = _load_settings_format()
    return fmt


def _prompt_slot(slot_name: str, parts: list[str]) -> str:
    if parts:
        print(f"  Available parts:")
        for index, part in enumerate(parts, start=1):
            print(f"    {index}. {part}")
    while True:
        raw = input(f"{slot_name} [1-{len(parts)} or custom text]: ").strip()
        if not raw:
            return ""
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(parts):
                return parts[choice - 1]
        return raw


def _confirm(prompt: str) -> str:
    while True:
        answer = input(f"{prompt} [y/n/s/q]: ").strip().lower()
        if answer in {"y", "n", "s", "q", "yes", "no", "skip", "quit"}:
            return answer[0]
        print("Please enter y (yes), n (no), s (skip), or q (quit).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rename karaoke video files to a standard format.")
    parser.add_argument("--folder", type=Path, required=True, help="Folder containing video files")
    parser.add_argument(
        "--separators",
        nargs="+",
        help="Separator strings in order (e.g. ' - ' ' | ')",
    )
    parser.add_argument("--suffix", help="Suffix text (default: Karaoke)")
    parser.add_argument("--no-suffix", action="store_true", help="Omit the suffix")
    parser.add_argument(
        "--slots",
        nargs="+",
        help="Slot names in order (default: 'Song Name' 'Artist Name')",
    )
    parser.add_argument(
        "--include-canonical",
        action="store_true",
        help="Include files that already appear to match the format",
    )
    args = parser.parse_args(argv)

    folder = args.folder.resolve()
    if not folder.is_dir():
        print(f"Not a directory: {folder}", file=sys.stderr)
        return 1

    fmt = _build_format(args)
    skip_canonical = not args.include_canonical and _load_settings_format()[1]

    files = sorted(scan_videos(folder), key=lambda path: path.name.lower())
    if skip_canonical:
        files = [path for path in files if not looks_canonical(path, fmt)]

    if not files:
        print("No video files found to rename.")
        return 0

    renamed = 0
    skipped = 0

    for index, path in enumerate(files, start=1):
        print()
        print(f"File {index} of {len(files)}: {path.name}")
        parts = split_title(path.stem)
        print(f"Parts: {parts if parts else '(none)'}")

        slots: dict[str, str] = {}
        for slot_name in fmt.slot_names:
            slots[slot_name] = _prompt_slot(slot_name, parts)

        preview = compose_filename(slots, fmt)
        if not preview:
            print("Could not build a filename. Skipping.")
            skipped += 1
            continue

        print(f"Preview: {preview}{path.suffix}")
        answer = _confirm("Rename this file?")
        if answer == "q":
            break
        if answer in {"n", "s"}:
            skipped += 1
            continue

        try:
            safe_rename(path, preview)
            renamed += 1
            print(f"Renamed to: {preview}{path.suffix}")
        except RenameError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            skipped += 1

    print()
    print(f"Done. Renamed {renamed}, skipped {skipped}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
