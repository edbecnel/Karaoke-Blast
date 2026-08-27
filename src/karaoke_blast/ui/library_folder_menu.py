"""Shared pinned/recent folder menu for library folder pickers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu, QWidgetAction

from karaoke_blast.ui.folder_history_list_widget import FolderHistoryListWidget
from karaoke_blast.ui.recent_folders_panel import PINNED_LABEL


def safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


class HistoryFolderMenu(QMenu):
    """Folder menu that supports removing recent entries from an embedded list."""

    folder_remove_requested = pyqtSignal(object)


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
    on_folder_remove: Callable[[Path], None] | None = None,
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

    if recent:
        _add_folder_history_list(
            menu,
            recent,
            current=current,
            on_folder_selected=on_folder_selected,
            on_folder_remove=on_folder_remove,
        )

    if pinned_folders or recent:
        menu.addSeparator()

    if include_browse:
        browse = QAction("Browse…", menu)
        browse.triggered.connect(on_browse)
        menu.addAction(browse)


def populate_downloads_folder_menu(
    menu: HistoryFolderMenu,
    *,
    current: Path | None,
    history_folders: list[Path],
    on_folder_selected: Callable[[Path], None],
    on_use_current: Callable[[], None],
    on_browse: Callable[[], None],
    use_current_enabled: bool,
    use_current_label: str,
) -> None:
    """Fill *menu* with use-current, download history, and browse actions."""
    menu.clear()

    use_current = QAction(use_current_label, menu)
    use_current.setEnabled(use_current_enabled)
    use_current.triggered.connect(on_use_current)
    menu.addAction(use_current)

    if history_folders:
        menu.addSeparator()
        _add_folder_history_list(
            menu,
            history_folders,
            current=current,
            on_folder_selected=on_folder_selected,
            on_folder_remove=menu.folder_remove_requested.emit,
        )

    menu.addSeparator()
    browse = QAction("Browse…", menu)
    browse.triggered.connect(on_browse)
    menu.addAction(browse)


def _add_folder_history_list(
    menu: QMenu,
    folders: list[Path],
    *,
    current: Path | None,
    on_folder_selected: Callable[[Path], None],
    on_folder_remove: Callable[[Path], None] | None,
) -> FolderHistoryListWidget:
    widget = FolderHistoryListWidget(menu)
    widget.set_folders(folders, current=current)

    def _select_folder(folder: Path) -> None:
        on_folder_selected(folder)
        menu.close()

    widget.folder_selected.connect(_select_folder)
    if on_folder_remove is not None:
        def _remove_folder(folder: Path) -> None:
            on_folder_remove(folder)
            menu.close()

        widget.folder_remove_requested.connect(_remove_folder)

    action = QWidgetAction(menu)
    action.setDefaultWidget(widget)
    menu.addAction(action)
    return widget


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
