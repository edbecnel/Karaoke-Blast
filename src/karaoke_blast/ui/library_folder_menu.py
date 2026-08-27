"""Shared pinned/recent folder menu for library folder pickers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu

from karaoke_blast.ui.recent_folders_panel import PINNED_LABEL


def safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


def populate_library_folder_menu(
    menu: QMenu,
    *,
    current: Path | None,
    recent_folders: list[Path],
    pinned_folders: list[Path],
    pinned_folder_label: str | None,
    on_folder_selected: Callable[[Path], None],
    on_browse: Callable[[], None],
    include_browse: bool = True,
) -> None:
    """Fill *menu* with pinned/recent folders and a Browse action."""
    menu.clear()
    pinned_resolved = {safe_resolve(path) for path in pinned_folders}
    pinned_label = pinned_folder_label or PINNED_LABEL

    for folder in pinned_folders:
        _add_folder_menu_action(
            menu,
            folder,
            pinned_label,
            current,
            on_folder_selected,
        )

    recent = [
        folder
        for folder in recent_folders
        if safe_resolve(folder) not in pinned_resolved
    ]
    if recent and pinned_folders:
        menu.addSeparator()

    for folder in recent:
        _add_folder_menu_action(
            menu,
            folder,
            folder.name,
            current,
            on_folder_selected,
        )

    if pinned_folders or recent:
        menu.addSeparator()

    if include_browse:
        browse = QAction("Browse…", menu)
        browse.triggered.connect(on_browse)
        menu.addAction(browse)


def _add_folder_menu_action(
    menu: QMenu,
    folder: Path,
    label: str,
    current: Path | None,
    on_folder_selected: Callable[[Path], None],
) -> None:
    action = QAction(label, menu)
    action.setToolTip(str(folder))
    resolved = safe_resolve(folder)
    if current is not None and current == resolved:
        action.setCheckable(True)
        action.setChecked(True)
        action.setEnabled(False)
    else:
        action.triggered.connect(
            lambda _checked=False, selected=folder: on_folder_selected(selected)
        )
    menu.addAction(action)
