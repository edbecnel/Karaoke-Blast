"""List widget for now-playing and queue rows with drag-to-reorder queue items."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem

from karaoke_blast.utils.display import display_name

_ROLE_INDEX = Qt.ItemDataRole.UserRole
_ROLE_PATH = Qt.ItemDataRole.UserRole + 1


class PlayOrderListWidget(QListWidget):
    """Shows now playing and queued songs; queued rows can be reordered by dragging."""

    queue_reordered = pyqtSignal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_index: int | None = None
        self._external_current: Path | None = None
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
        external_current: Path | None = None,
        path_queue: list[Path] | None = None,
    ) -> None:
        self._external_current = external_current
        self._current_index = current_index
        queued_paths = list(path_queue or [])
        display_queue = [
            index
            for index in queue_indices
            if index != current_index and 0 <= index < len(paths)
        ]

        self.clear()
        queue_pos = 0

        if external_current is not None:
            self._add_path_row(
                external_current,
                is_current=True,
                queue_pos=None,
            )
        elif current_index is not None and 0 <= current_index < len(paths):
            self._add_index_row(
                paths,
                current_index,
                is_current=True,
                queue_pos=None,
            )

        for path in queued_paths:
            queue_pos += 1
            self._add_path_row(path, is_current=False, queue_pos=queue_pos)

        for index in display_queue:
            queue_pos += 1
            self._add_index_row(
                paths,
                index,
                is_current=False,
                queue_pos=queue_pos,
            )

    def _add_path_row(
        self,
        path: Path,
        *,
        is_current: bool,
        queue_pos: int | None,
    ) -> None:
        title = display_name(path)
        if is_current:
            title = f"▶ {title}"
        else:
            title = f"⏭ {queue_pos} · {title}"

        item = QListWidgetItem(title)
        item.setData(_ROLE_INDEX, None)
        item.setData(_ROLE_PATH, path)
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            mtime_text = mtime.strftime("%Y-%m-%d %H:%M")
        except OSError:
            mtime_text = "unknown"
        tip = f"{display_name(path)}\n{path}\nModified: {mtime_text}"
        if is_current:
            tip = f"Now playing\n{tip}"
        else:
            tip = f"Queued (#{queue_pos})\n{tip}"
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

    def _add_index_row(
        self,
        paths: list[Path],
        index: int,
        *,
        is_current: bool,
        queue_pos: int | None,
    ) -> None:
        path = paths[index]
        title = display_name(path)
        if is_current:
            title = f"▶ {title}"
        else:
            title = f"⏭ {queue_pos} · {title}"

        item = QListWidgetItem(title)
        item.setData(_ROLE_INDEX, index)
        item.setData(_ROLE_PATH, None)
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            mtime_text = mtime.strftime("%Y-%m-%d %H:%M")
        except OSError:
            mtime_text = "unknown"
        tip = f"{display_name(path)}\n{path}\nModified: {mtime_text}"
        if is_current:
            tip = f"Now playing\n{tip}"
        else:
            tip = f"Queued (#{queue_pos})\n{tip}"
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
        if self._external_current is not None:
            external = self._resolve_path(self._external_current)
            for row in range(self.count()):
                item = self.item(row)
                if item is None:
                    continue
                path = item.data(_ROLE_PATH)
                if isinstance(path, Path) and self._resolve_path(path) == external:
                    return row
            return None
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
        if item is None:
            return
        if item.data(_ROLE_PATH) is not None:
            return
        if item.data(_ROLE_INDEX) == self._current_index:
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
        if source_item is None:
            event.ignore()
            return
        if source_item.data(_ROLE_PATH) is not None:
            event.ignore()
            return
        if source_item.data(_ROLE_INDEX) == self._current_index:
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
            if index is None:
                continue
            if index != self._current_index:
                queue.append(index)
        self.queue_reordered.emit(queue)

    @staticmethod
    def _resolve_path(path: Path) -> Path:
        try:
            return path.resolve()
        except OSError:
            return path
