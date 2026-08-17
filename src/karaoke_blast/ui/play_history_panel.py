"""Unified play history sidebar list."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QMenu

from karaoke_blast.models.play_history_entry import PlayHistoryEntry
from karaoke_blast.ui.context_menu_style import CONTEXT_MENU_STYLE, copy_text_to_clipboard
from karaoke_blast.ui.youtube_queue_widget import format_duration
from karaoke_blast.utils.display import display_name

_ROLE_ENTRY = Qt.ItemDataRole.UserRole


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


class PlayHistoryPanel(QListWidget):
    """List of previously played local and YouTube items."""

    play_requested = pyqtSignal(object)
    queue_requested = pyqtSignal(object)
    remove_requested = pyqtSignal(object)
    edit_metadata_requested = pyqtSignal(object)
    download_requested = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entries: list[PlayHistoryEntry] = []
        self._current_local: Path | None = None
        self._current_video_id: str | None = None
        self._display_resolver: Callable[[Path], str] = display_name
        self._library_root: Path | None = None
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def set_display_resolver(self, resolver: Callable[[Path], str] | None) -> None:
        self._display_resolver = resolver if resolver is not None else display_name
        if self._entries:
            self.set_history(self._entries, current_local=self._current_local, current_video_id=self._current_video_id)

    def set_library_root(self, root: Path | None) -> None:
        self._library_root = root.resolve() if root is not None else None

    def set_history(
        self,
        entries: list[PlayHistoryEntry],
        *,
        current_local: Path | None = None,
        current_video_id: str | None = None,
    ) -> None:
        self._entries = list(entries)
        self._current_local = _safe_resolve(current_local) if current_local is not None else None
        self._current_video_id = current_video_id
        self.clear()
        for entry in entries:
            is_current = False
            if entry.kind == "local" and entry.path is not None:
                resolved = _safe_resolve(entry.path)
                is_current = self._current_local is not None and resolved == self._current_local
                label = self._display_resolver(entry.path)
                secondary = self._path_hint(entry.path)
                prefix = "▶ " if is_current else "📁 "
                title = f"{prefix}{label}\n{secondary}"
                tip = f"{label}\n{entry.path}"
            elif entry.kind == "youtube" and entry.video is not None:
                video = entry.video
                is_current = video.video_id == self._current_video_id
                duration = format_duration(video.duration_seconds)
                suffix = f" ({duration})" if duration else ""
                prefix = "▶ " if is_current else "▶︎ "
                title = f"{prefix}{video.title}{suffix}\n{video.channel}"
                tip = f"{video.title}\n{video.channel}\n{video.watch_url}"
            else:
                continue

            item = QListWidgetItem(title)
            item.setData(_ROLE_ENTRY, entry)
            item.setToolTip(tip)
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            if is_current:
                item.setForeground(QColor("#7ee787"))
            self.addItem(item)

    def _path_hint(self, path: Path) -> str:
        if self._library_root is None:
            return str(path)
        try:
            relative = path.resolve().relative_to(self._library_root)
            return str(relative)
        except (OSError, ValueError):
            return str(path)

    def _entry_from_item(self, item: QListWidgetItem | None) -> PlayHistoryEntry | None:
        if item is None:
            return None
        value = item.data(_ROLE_ENTRY)
        return value if isinstance(value, PlayHistoryEntry) else None

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        entry = self._entry_from_item(item)
        if entry is not None:
            self.play_requested.emit(entry)

    def _defer(self, signal: pyqtSignal, payload: object) -> None:
        QTimer.singleShot(0, lambda: signal.emit(payload))

    def _show_context_menu(self, pos) -> None:
        entry = self._entry_from_item(self.itemAt(pos))
        if entry is None:
            return

        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

        play_now = QAction("Play Now", self)
        play_now.triggered.connect(lambda: self._defer(self.play_requested, entry))
        menu.addAction(play_now)

        play_next = QAction("Play Next", self)
        play_next.triggered.connect(lambda: self._defer(self.queue_requested, entry))
        menu.addAction(play_next)

        if entry.kind == "local" and entry.path is not None:
            edit_meta = QAction("Edit Metadata…", self)
            edit_meta.triggered.connect(
                lambda: self._defer(self.edit_metadata_requested, entry.path)
            )
            menu.addAction(edit_meta)

        if entry.kind == "youtube" and entry.video is not None:
            video = entry.video
            download = QAction("Download", self)
            download.triggered.connect(
                lambda: self._defer(self.download_requested, video)
            )
            menu.addAction(download)
            copy_url = QAction("Copy URL", self)
            copy_url.triggered.connect(lambda: copy_text_to_clipboard(video.watch_url))
            menu.addAction(copy_url)

        remove = QAction("Remove from History", self)
        remove.triggered.connect(lambda: self._defer(self.remove_requested, entry))
        menu.addAction(remove)

        menu.exec(self.mapToGlobal(pos))
