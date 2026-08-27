"""Open folders and reveal files in the system file manager."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QUrl, QFile
from PyQt6.QtGui import QDesktopServices


def reveal_action_label() -> str:
    """Menu label for revealing a file in the OS file manager."""
    if sys.platform == "darwin":
        return "Reveal in Finder"
    if sys.platform == "win32":
        return "Show in Explorer"
    return "Show in file manager"


def trash_action_label() -> str:
    """Menu label for moving a file to the system trash."""
    if sys.platform == "win32":
        return "Move to Recycle Bin"
    return "Move to Trash"


def move_path_to_trash(path: Path) -> bool:
    """Move *path* to the system trash/recycle bin."""
    try:
        resolved = path.resolve()
    except OSError:
        return False
    if not resolved.is_file():
        return False
    return QFile.moveToTrash(str(resolved))


def open_folder_in_file_manager(folder: Path) -> bool:
    """Open *folder* in Explorer, Finder, or the default Linux file manager."""
    try:
        resolved = folder.resolve()
    except OSError:
        return False
    if not resolved.is_dir():
        return False
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(resolved)))


def reveal_in_file_manager(path: Path) -> bool:
    """Open the file manager with *path* selected, when the platform supports it."""
    try:
        resolved = path.resolve()
    except OSError:
        return False
    if not resolved.is_file():
        return False

    if sys.platform == "win32":
        return _reveal_windows(resolved)
    if sys.platform == "darwin":
        return _reveal_macos(resolved)
    return _reveal_linux(resolved)


def _reveal_windows(path: Path) -> bool:
    try:
        subprocess.Popen(["explorer", "/select,", os.path.normpath(str(path))])
        return True
    except OSError:
        return False


def _reveal_macos(path: Path) -> bool:
    try:
        subprocess.Popen(["open", "-R", str(path)])
        return True
    except OSError:
        return False


def _reveal_linux(path: Path) -> bool:
    path_str = str(path)
    commands = (
        (["nautilus", "--select", path_str], "nautilus"),
        (["dolphin", "--select", path_str], "dolphin"),
        (["nemo", "--select", path_str], "nemo"),
        (["pcmanfm", "--select", path_str], "pcmanfm"),
        (["thunar", path_str], "thunar"),
    )
    for args, binary in commands:
        if shutil.which(binary) is None:
            continue
        try:
            subprocess.Popen(args)
            return True
        except OSError:
            continue

    if shutil.which("xdg-open") is not None:
        try:
            subprocess.Popen(["xdg-open", str(path.parent)])
            return True
        except OSError:
            pass

    return open_folder_in_file_manager(path.parent)
