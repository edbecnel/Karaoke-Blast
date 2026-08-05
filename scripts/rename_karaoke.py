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
    SLOT_KIND_SONG,
    FilenameFormat,
    RenameError,
    compose_filename,
    default_slot_values,
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
    if args.separators or args.no_suffix or args.suffix:
        fmt = DEFAULT_KARAOKE_FORMAT.copy()
        if args.separators:
            for index, separator in enumerate(args.separators[:3]):
                fmt.separators[index] = separator
        if args.no_suffix:
            fmt.slots[2].enabled = False
        elif args.suffix is not None:
            fmt.slots[2].label = args.suffix
            fmt.slots[2].hint = args.suffix
            fmt.slots[2].hint_fixed = bool(args.suffix)
            fmt.slots[2].enabled = bool(args.suffix)
        return fmt
    fmt, _skip = _load_settings_format()
    return fmt


def _prompt_slot(slot_label: str, parts: list[str], *, required: bool) -> str:
    if parts:
        print("  Available parts:")
        for index, part in enumerate(parts, start=1):
            print(f"    {index}. {part}")
    hint = "required" if required else "optional, press Enter to skip"
    while True:
        raw = input(f"{slot_label} ({hint}) [1-{len(parts)} or custom text]: ").strip()
        if not raw:
            return "" if not required else _retry_required(slot_label, parts)
        if raw.isdigit() and parts:
            choice = int(raw)
            if 1 <= choice <= len(parts):
                return parts[choice - 1]
        return raw


def _retry_required(slot_label: str, parts: list[str]) -> str:
    while True:
        raw = input(f"{slot_label} is required. Enter a value: ").strip()
        if raw:
            if raw.isdigit() and parts:
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
        help="Separator strings in order (up to 3, e.g. ' - ' ' - ' ' - ')",
    )
    parser.add_argument(
        "--suffix",
        help="Label/text for the third slot (default: Karaoke)",
    )
    parser.add_argument(
        "--no-suffix",
        action="store_true",
        help="Disable the third additional slot",
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

        defaults = default_slot_values(path.stem, fmt)
        slot_values: dict[int, str] = {}
        for slot_index in fmt.enabled_slot_indices():
            slot = fmt.slots[slot_index]
            required = slot.kind == SLOT_KIND_SONG
            default = defaults.get(slot_index, "")
            if default:
                raw = input(
                    f"{slot.label} ({'required' if required else 'optional'}) [{default}]: "
                ).strip()
                slot_values[slot_index] = raw or default
            else:
                slot_values[slot_index] = _prompt_slot(slot.label, parts, required=required)

        preview = compose_filename(slot_values, fmt)
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
