"""List widget for now-playing and queue rows with drag-to-reorder queue items."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem

from karaoke_blast.utils.display import display_name

_ROLE_INDEX = Qt.ItemDataRole.UserRole


class PlayOrderListWidget(QListWidget):
    """Shows now playing and queued songs; queued rows can be reordered by dragging."""

    queue_reordered = pyqtSignal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_index: int | None = None
        self._reorder_enabled = False
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def set_reorder_enabled(self, enabled: bool) -> None:
        self._reorder_enabled = enabled
        self.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
            if enabled
            else QAbstractItemView.DragDropMode.NoDragDrop
        )

    def set_play_order(
        self,
        paths: list[Path],
        *,
        current_index: int | None,
        queue_indices: list[int],
    ) -> None:
        self._current_index = current_index
        display_queue = [
            index
            for index in queue_indices
            if index != current_index and 0 <= index < len(paths)
        ]
        order: list[int] = []
        if current_index is not None and 0 <= current_index < len(paths):
            order.append(current_index)
        order.extend(display_queue)

        self.clear()
        for index in order:
            path = paths[index]
            is_current = current_index is not None and index == current_index
            title = display_name(path)
            if is_current:
                title = f"▶ {title}"
            else:
                queue_pos = display_queue.index(index) + 1
                title = f"⏭ {queue_pos} · {title}"

            item = QListWidgetItem(title)
            item.setData(_ROLE_INDEX, index)
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            tip = f"{display_name(path)}\n{path}\nModified: {mtime.strftime('%Y-%m-%d %H:%M')}"
            if is_current:
                tip = f"Now playing\n{tip}"
            else:
                tip = f"Queued (#{display_queue.index(index) + 1})\n{tip}"
            item.setToolTip(tip)

            flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
            if self._reorder_enabled and not is_current:
                flags |= Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled
            elif is_current:
                flags |= Qt.ItemFlag.ItemIsDropEnabled
            item.setFlags(flags)

            if is_current:
                item.setForeground(QColor("#7ee787"))
            else:
                item.setForeground(QColor("#ffb3c1"))
            self.addItem(item)

    def _now_playing_row(self) -> int | None:
        if self._current_index is None:
            return None
        for row in range(self.count()):
            item = self.item(row)
            if item is not None and item.data(_ROLE_INDEX) == self._current_index:
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
        if not self._reorder_enabled:
            return
        item = self.currentItem()
        if item is None or item.data(_ROLE_INDEX) == self._current_index:
            return
        super().startDrag(supported_actions)

    def dragEnterEvent(self, event) -> None:
        if event.source() is self and self._reorder_enabled:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.source() is not self or not self._reorder_enabled:
            event.ignore()
            return
        drop_row = self._drop_row_at(event.position().toPoint())
        now_row = self._now_playing_row()
        if now_row is not None and drop_row <= now_row:
            event.ignore()
            return
        event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if event.source() is not self or not self._reorder_enabled:
            event.ignore()
            return

        selected = sorted(index.row() for index in self.selectedIndexes())
        if len(selected) != 1:
            event.ignore()
            return
        source_row = selected[0]
        source_item = self.item(source_row)
        if source_item is None or source_item.data(_ROLE_INDEX) == self._current_index:
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
        queue: list[int] = []
        for row in range(self.count()):
            item = self.item(row)
            if item is None:
                continue
            index = item.data(_ROLE_INDEX)
            if index != self._current_index:
                queue.append(index)
        self.queue_reordered.emit(queue)
