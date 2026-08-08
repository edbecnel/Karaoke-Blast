"""Local play history sidebar list."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QMenu

from karaoke_blast.ui.context_menu_style import CONTEXT_MENU_STYLE

from karaoke_blast.utils.display import display_name

_ROLE_PATH = Qt.ItemDataRole.UserRole


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


class LocalHistoryPanel(QListWidget):
    """List of previously played local videos with play/queue actions."""

    play_requested = pyqtSignal(object)
    queue_requested = pyqtSignal(object)
    remove_requested = pyqtSignal(object)
    clear_requested = pyqtSignal()
    edit_metadata_requested = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_path: Path | None = None
        self._history_paths: list[Path] = []
        self._display_resolver: Callable[[Path], str] = display_name
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def set_display_resolver(self, resolver: Callable[[Path], str] | None) -> None:
        self._display_resolver = resolver if resolver is not None else display_name
        self.refresh_labels()

    def refresh_labels(self) -> None:
        if self._history_paths:
            self.set_history(self._history_paths, current=self._current_path)

    def set_history(self, paths: list[Path], *, current: Path | None = None) -> None:
        self._history_paths = list(paths)
        self._current_path = _safe_resolve(current) if current is not None else None
        self.clear()
        for path in paths:
            resolved = _safe_resolve(path)
            is_current = self._current_path is not None and resolved == self._current_path
            prefix = "▶ " if is_current else ""
            label = self._display_resolver(path)
            item = QListWidgetItem(f"{prefix}{label}")
            item.setData(_ROLE_PATH, resolved)
            item.setToolTip(f"{label}\n{resolved}")
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            if is_current:
                item.setForeground(QColor("#7ee787"))
            self.addItem(item)

    def _path_from_item(self, item: QListWidgetItem | None) -> Path | None:
        if item is None:
            return None
        value = item.data(_ROLE_PATH)
        if isinstance(value, Path):
            return value
        if isinstance(value, str) and value:
            return Path(value)
        return None

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        path = self._path_from_item(item)
        if path is not None:
            self.play_requested.emit(path)

    def _defer(self, signal: pyqtSignal, path: Path) -> None:
        # Defer so the context menu can close before handlers rebuild this list.
        QTimer.singleShot(0, lambda: signal.emit(path))

    def _show_context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        path = self._path_from_item(item)
        if path is None:
            return

        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

        play_now = QAction("Play Now", self)
        play_now.triggered.connect(lambda: self._defer(self.play_requested, path))
        menu.addAction(play_now)

        play_next = QAction("Play Next", self)
        play_next.triggered.connect(lambda: self._defer(self.queue_requested, path))
        menu.addAction(play_next)

        edit_meta = QAction("Edit Metadata…", self)
        edit_meta.triggered.connect(lambda: self._defer(self.edit_metadata_requested, path))
        menu.addAction(edit_meta)

        remove = QAction("Remove from History", self)
        remove.triggered.connect(lambda: self._defer(self.remove_requested, path))
        menu.addAction(remove)

        menu.exec(self.mapToGlobal(pos))
