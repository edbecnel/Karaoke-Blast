"""Local play history sidebar list."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QMenu

from karaoke_blast.utils.display import display_name

_ROLE_PATH = Qt.ItemDataRole.UserRole


class LocalHistoryPanel(QListWidget):
    """List of previously played local videos with play/queue actions."""

    play_requested = pyqtSignal(object)
    queue_requested = pyqtSignal(object)
    remove_requested = pyqtSignal(object)
    clear_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_path: Path | None = None
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def set_history(self, paths: list[Path], *, current: Path | None = None) -> None:
        self._current_path = current.resolve() if current is not None else None
        self.clear()
        for path in paths:
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            is_current = self._current_path is not None and resolved == self._current_path
            prefix = "▶ " if is_current else ""
            item = QListWidgetItem(f"{prefix}{display_name(path)}")
            item.setData(_ROLE_PATH, resolved)
            item.setToolTip(str(resolved))
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            if is_current:
                item.setForeground(QColor("#7ee787"))
            self.addItem(item)

    def _path_from_item(self, item: QListWidgetItem | None) -> Path | None:
        if item is None:
            return None
        value = item.data(_ROLE_PATH)
        return value if isinstance(value, Path) else None

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        path = self._path_from_item(item)
        if path is not None:
            self.play_requested.emit(path)

    def _show_context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        path = self._path_from_item(item)
        if path is None:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #1e1e2e; color: white; border: 1px solid #5a5a72; }"
            "QMenu::item:selected { background-color: #e94560; }"
        )

        play_now = QAction("Play Now", self)
        play_now.triggered.connect(lambda: self.play_requested.emit(path))
        menu.addAction(play_now)

        play_next = QAction("Play Next", self)
        play_next.triggered.connect(lambda: self.queue_requested.emit(path))
        menu.addAction(play_next)

        remove = QAction("Remove from History", self)
        remove.triggered.connect(lambda: self.remove_requested.emit(path))
        menu.addAction(remove)

        menu.exec(self.mapToGlobal(pos))
