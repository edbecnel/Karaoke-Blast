"""List widget for the mixed local/YouTube play queue."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QMenu,
)

from karaoke_blast.models.queue_item import QueueItem
from karaoke_blast.ui.context_menu_style import CONTEXT_MENU_STYLE, copy_text_to_clipboard
from karaoke_blast.ui.list_style import QUEUE_LIST_STYLE
from karaoke_blast.ui.youtube_queue_widget import format_duration
from karaoke_blast.utils.display import display_name

_ROLE_ITEM = Qt.ItemDataRole.UserRole


class MixedQueueListWidget(QListWidget):
    """Shows now playing and queued local/YouTube items with drag reorder."""

    play_requested = pyqtSignal(object)
    queue_requested = pyqtSignal(object)
    remove_requested = pyqtSignal(object)
    download_requested = pyqtSignal(object)
    queue_reordered = pyqtSignal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_item: QueueItem | None = None
        self._display_resolver: Callable[[Path], str] = display_name
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def set_display_resolver(self, resolver: Callable[[Path], str] | None) -> None:
        self._display_resolver = resolver if resolver is not None else display_name

    def set_queue(
        self,
        *,
        current: QueueItem | None,
        queued: list[QueueItem],
    ) -> None:
        self._current_item = current
        self.clear()
        if current is not None:
            self._add_row(current, label_prefix="▶ ", color="#7ee787", is_current=True)
        for position, item in enumerate(queued, start=1):
            self._add_row(
                item,
                label_prefix=f"⏭ {position} · ",
                color="#ffb3c1",
                is_current=False,
            )

    def _label_for(self, item: QueueItem) -> str:
        if item.kind == "local" and item.path is not None:
            return f"📁 {self._display_resolver(item.path)}"
        if item.kind == "youtube" and item.video is not None:
            duration = format_duration(item.video.duration_seconds)
            suffix = f" ({duration})" if duration else ""
            return f"▶︎ {item.video.title}{suffix}"
        return "Unknown"

    def _secondary_line(self, item: QueueItem) -> str:
        if item.kind == "local" and item.path is not None:
            return str(item.path)
        if item.kind == "youtube" and item.video is not None:
            return item.video.channel
        return ""

    def _add_row(
        self,
        item: QueueItem,
        *,
        label_prefix: str,
        color: str,
        is_current: bool,
    ) -> None:
        label = self._label_for(item)
        secondary = self._secondary_line(item)
        title = f"{label_prefix}{label}"
        if secondary:
            title = f"{title}\n{secondary}"
        row = QListWidgetItem(title)
        row.setData(_ROLE_ITEM, item)
        tip = label
        if secondary:
            tip = f"{label}\n{secondary}"
        row.setToolTip(tip)
        flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        if not is_current:
            flags |= Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled
        else:
            flags |= Qt.ItemFlag.ItemIsDropEnabled
        row.setFlags(flags)
        row.setForeground(QColor(color))
        self.addItem(row)

    def _item_from_row(self, item: QListWidgetItem | None) -> QueueItem | None:
        if item is None:
            return None
        value = item.data(_ROLE_ITEM)
        return value if isinstance(value, QueueItem) else None

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        queue_item = self._item_from_row(item)
        if queue_item is not None:
            self.play_requested.emit(queue_item)

    def _show_context_menu(self, pos) -> None:
        item = self._item_from_row(self.itemAt(pos))
        if item is None:
            return

        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

        play_now = QAction("Play Now", self)
        play_now.triggered.connect(lambda: self.play_requested.emit(item))
        menu.addAction(play_now)

        is_current = self._current_item is not None and self._current_item.key() == item.key()
        if not is_current:
            play_next = QAction("Play Next", self)
            play_next.triggered.connect(lambda: self.queue_requested.emit(item))
            menu.addAction(play_next)

        remove = QAction("Remove from Queue", self)
        remove.triggered.connect(lambda: self.remove_requested.emit(item))
        menu.addAction(remove)

        if item.kind == "youtube" and item.video is not None:
            video = item.video
            download = QAction("Download", self)
            download.triggered.connect(lambda: self.download_requested.emit(video))
            menu.addAction(download)
            copy_url = QAction("Copy URL", self)
            copy_url.triggered.connect(lambda: copy_text_to_clipboard(video.watch_url))
            menu.addAction(copy_url)

        menu.exec(self.mapToGlobal(pos))

    def _now_playing_row(self) -> int | None:
        if self._current_item is None:
            return None
        for row in range(self.count()):
            item = self._item_from_row(self.item(row))
            if item is not None and item.key() == self._current_item.key():
                return row
        return None

    def _drop_row_at(self, pos) -> int:
        row = self.indexAt(pos).row()
        if row < 0:
            return self.count()
        item = self.item(row)
        if item is None:
            return self.count()
        rect = self.visualItemRect(item)
        if pos.y() > rect.center().y():
            row += 1
        return row

    def startDrag(self, supported_actions) -> None:
        item = self.currentItem()
        queue_item = self._item_from_row(item)
        if queue_item is None:
            return
        if self._current_item is not None and queue_item.key() == self._current_item.key():
            return
        super().startDrag(supported_actions)

    def dragEnterEvent(self, event) -> None:
        if event.source() is self:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.source() is not self:
            event.ignore()
            return
        drop_row = self._drop_row_at(event.position().toPoint())
        now_row = self._now_playing_row()
        if now_row is not None and drop_row <= now_row:
            event.ignore()
            return
        event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if event.source() is not self:
            event.ignore()
            return

        selected = sorted(index.row() for index in self.selectedIndexes())
        if len(selected) != 1:
            event.ignore()
            return
        source_row = selected[0]
        source_item = self._item_from_row(self.item(source_row))
        if source_item is None:
            event.ignore()
            return
        if self._current_item is not None and source_item.key() == self._current_item.key():
            event.ignore()
            return

        target_row = self._drop_row_at(event.position().toPoint())
        now_row = self._now_playing_row()
        if now_row is not None and target_row <= now_row:
            target_row = now_row + 1

        moved = self.takeItem(source_row)
        insert_at = target_row
        if source_row < target_row:
            insert_at -= 1
        self.insertItem(insert_at, moved)
        self.setCurrentItem(moved)
        self._emit_queue_order()
        event.acceptProposedAction()

    def _emit_queue_order(self) -> None:
        queue: list[QueueItem] = []
        for row in range(self.count()):
            item = self._item_from_row(self.item(row))
            if item is None:
                continue
            if self._current_item is not None and item.key() == self._current_item.key():
                continue
            queue.append(item)
        self.queue_reordered.emit(queue)


QUEUE_PANEL_LIST_STYLE = QUEUE_LIST_STYLE
