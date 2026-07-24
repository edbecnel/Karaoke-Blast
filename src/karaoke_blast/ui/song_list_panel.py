"""Sidebar song list with sort controls."""

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QPalette
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.models.sort_strategy import SortStrategy
from karaoke_blast.ui.queue_list_widget import PlayOrderListWidget
from karaoke_blast.utils.display import display_name

PANEL_DEFAULT_WIDTH = 320
PANEL_MIN_WIDTH = 200
PANEL_MAX_WIDTH = 700

LIST_STYLE = """
QListWidget {
    background-color: rgba(20, 20, 30, 230);
    color: white;
    border: none;
    font-size: 13px;
    outline: none;
}
QListWidget::item {
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 20);
}
QListWidget::item:selected {
    background-color: rgba(233, 69, 96, 120);
}
QListWidget::item:hover {
    background-color: rgba(255, 255, 255, 30);
}
"""

QUEUE_PANEL_LIST_STYLE = """
QListWidget {
    background-color: rgba(20, 20, 30, 120);
    color: white;
    border: none;
    font-size: 12px;
    outline: none;
}
QListWidget::item {
    padding: 6px 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 15);
}
QListWidget::item:selected {
    background-color: rgba(233, 69, 96, 120);
}
QListWidget::item:hover {
    background-color: rgba(255, 255, 255, 25);
}
"""

COMBO_STYLE = """
QComboBox {
    background-color: #2d2d42;
    color: #ffffff;
    border: 1px solid #5a5a72;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
}
QComboBox:hover {
    border-color: #7a7a92;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #ffffff;
    margin-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    color: #ffffff;
    border: 1px solid #5a5a72;
    selection-background-color: #e94560;
    selection-color: #ffffff;
    outline: none;
}
"""

SEARCH_STYLE = """
QLineEdit {
    background-color: #2d2d42;
    color: #ffffff;
    border: 1px solid #5a5a72;
    border-radius: 4px;
    padding: 8px 10px;
    font-size: 13px;
    selection-background-color: #e94560;
    selection-color: #ffffff;
}
QLineEdit:hover {
    border-color: #7a7a92;
}
QLineEdit:focus {
    border-color: #e94560;
    background-color: #35354c;
}
"""


class SongListPanel(QWidget):
    """Left sidebar listing songs in the current folder."""

    song_selected = pyqtSignal(int)
    play_next_requested = pyqtSignal(int)
    remove_from_queue_requested = pyqtSignal(int)
    clear_queue_requested = pyqtSignal()
    queue_reordered = pyqtSignal(list)
    sort_changed = pyqtSignal(object)
    close_requested = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(PANEL_MIN_WIDTH)
        self.setMaximumWidth(PANEL_MAX_WIDTH)
        self.setStyleSheet(
            "background-color: rgba(15, 15, 25, 230);"
            " border-right: 1px solid rgba(255, 255, 255, 30);"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header = QLabel("Songs")
        header.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        header_row.addWidget(header)
        header_row.addStretch()

        refresh_btn = QPushButton("↻")
        refresh_btn.setToolTip("Refresh song list")
        refresh_btn.setFixedSize(28, 28)
        refresh_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #aaa; border: none;"
            " font-size: 18px; border-radius: 4px; }"
            "QPushButton:hover { background: rgba(255,255,255,30); color: white; }"
        )
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._on_refresh_clicked)
        header_row.addWidget(refresh_btn)

        close_btn = QPushButton("×")
        close_btn.setToolTip("Hide song list (L)")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #aaa; border: none;"
            " font-size: 20px; border-radius: 4px; }"
            "QPushButton:hover { background: rgba(255,255,255,30); color: white; }"
        )
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._on_close_clicked)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        self._sort_combo = QComboBox()
        self._sort_combo.setStyleSheet(COMBO_STYLE)
        sort_palette = self._sort_combo.palette()
        sort_palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        self._sort_combo.setPalette(sort_palette)
        for strategy in SortStrategy:
            self._sort_combo.addItem(strategy.label, strategy)
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        layout.addWidget(self._sort_combo)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search songs…")
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet(SEARCH_STYLE)
        search_palette = self._search.palette()
        search_palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        search_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#b8b8c8"))
        self._search.setPalette(search_palette)
        self._search.textChanged.connect(self._apply_filter)
        layout.addWidget(self._search)

        self._now_playing_btn = QPushButton("Current + queue")
        self._now_playing_btn.setCheckable(True)
        self._now_playing_btn.setToolTip(
            "Show only the song playing now and songs waiting in the queue"
        )
        self._now_playing_btn.setEnabled(False)
        self._now_playing_btn.setStyleSheet(
            "QPushButton { background-color: #2d2d42; color: #b8b8c8; border: 1px solid #5a5a72;"
            " border-radius: 4px; padding: 6px 10px; font-size: 12px; }"
            "QPushButton:hover:enabled { border-color: #7a7a92; color: white; }"
            "QPushButton:checked { background-color: #e94560; color: white; border-color: #e94560; }"
            "QPushButton:disabled { color: #555; border-color: #3a3a4a; }"
        )
        self._now_playing_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._now_playing_btn.toggled.connect(self._on_now_playing_filter_toggled)
        layout.addWidget(self._now_playing_btn)

        self._count_label = QLabel()
        self._count_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._count_label)

        self._queue_section = QWidget()
        self._queue_section.hide()
        queue_outer = QVBoxLayout(self._queue_section)
        queue_outer.setContentsMargins(0, 0, 0, 0)
        queue_outer.setSpacing(4)

        queue_header = QHBoxLayout()
        self._queue_title = QLabel("Queue")
        self._queue_title.setStyleSheet("color: #e94560; font-size: 12px; font-weight: bold;")
        queue_header.addWidget(self._queue_title)
        queue_header.addStretch()
        clear_queue_btn = QPushButton("Clear")
        clear_queue_btn.setToolTip("Remove all queued songs")
        clear_queue_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #aaa; border: none;"
            " font-size: 11px; padding: 2px 6px; }"
            "QPushButton:hover { color: white; background: rgba(255,255,255,25);"
            " border-radius: 3px; }"
        )
        clear_queue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_queue_btn.clicked.connect(self._on_clear_queue_clicked)
        queue_header.addWidget(clear_queue_btn)
        queue_outer.addLayout(queue_header)

        self._queue_list = PlayOrderListWidget()
        self._queue_list.setStyleSheet(QUEUE_PANEL_LIST_STYLE)
        self._queue_list.itemClicked.connect(self._on_item_clicked)
        self._queue_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._queue_list.customContextMenuRequested.connect(self._show_queue_context_menu)
        self._queue_list.queue_reordered.connect(self.queue_reordered.emit)
        queue_outer.addWidget(self._queue_list)

        layout.addWidget(self._queue_section)

        self._list = PlayOrderListWidget()
        self._list.queue_reordered.connect(self.queue_reordered.emit)
        self._list.setStyleSheet(LIST_STYLE)
        self._list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._list.setMouseTracking(True)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        self._paths: list[Path] = []
        self._current_index: int | None = None
        self._selected_index: int | None = None
        self._queue_indices: list[int] = []
        self._now_playing_only = False

    def _on_refresh_clicked(self, _checked: bool = False) -> None:
        self.refresh_requested.emit()

    def _on_close_clicked(self, _checked: bool = False) -> None:
        self.close_requested.emit()

    def _on_clear_queue_clicked(self, _checked: bool = False) -> None:
        self.clear_queue_requested.emit()

    def _on_now_playing_filter_toggled(self, checked: bool) -> None:
        self._now_playing_only = checked
        self._search.setEnabled(not checked)
        if checked:
            self._search.blockSignals(True)
            self._search.clear()
            self._search.blockSignals(False)
            self._queue_section.hide()
        else:
            self._rebuild_queue_ui()
        self._apply_filter()

    def _clear_now_playing_filter(self) -> None:
        if not self._now_playing_only:
            return
        self._now_playing_only = False
        self._search.setEnabled(True)
        self._now_playing_btn.blockSignals(True)
        self._now_playing_btn.setChecked(False)
        self._now_playing_btn.blockSignals(False)
        self._rebuild_queue_ui()
        self._apply_filter()

    def _update_now_playing_filter_state(self) -> None:
        has_queue = bool(self._play_order_indices())
        self._now_playing_btn.setEnabled(has_queue)
        if not has_queue:
            self._clear_now_playing_filter()

    def _on_sort_changed(self, _index: int) -> None:
        strategy = self._sort_combo.currentData()
        if strategy is not None:
            self.sort_changed.emit(strategy)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        index = item.data(Qt.ItemDataRole.UserRole)
        if index is None:
            return
        self._on_song_index_clicked(index)

    def _on_song_index_clicked(self, index: int) -> None:
        if index == self._selected_index:
            self.song_selected.emit(index)
        else:
            self._selected_index = index

    def _show_context_menu(self, pos) -> None:
        self._show_song_context_menu(self._list, pos)

    def _show_queue_context_menu(self, pos) -> None:
        self._show_song_context_menu(self._queue_list, pos)

    def _show_song_context_menu(self, list_widget: PlayOrderListWidget, pos) -> None:
        item = list_widget.itemAt(pos)
        if item is None:
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        if index is None:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #1e1e2e; color: white; border: 1px solid #5a5a72; }"
            "QMenu::item:selected { background-color: #e94560; }"
        )

        play_now = QAction("Play Now", self)
        play_now.triggered.connect(lambda: self.song_selected.emit(index))
        menu.addAction(play_now)

        play_next = QAction("Play Next", self)
        play_next.triggered.connect(lambda: self.play_next_requested.emit(index))
        menu.addAction(play_next)

        if index in self._queue_indices:
            remove = QAction("Remove from Queue", self)
            remove.triggered.connect(lambda: self.remove_from_queue_requested.emit(index))
            menu.addAction(remove)

        menu.exec(list_widget.mapToGlobal(pos))

    def set_queue_indices(self, indices: list[int]) -> None:
        self._queue_indices = indices
        self._update_now_playing_filter_state()
        if self._now_playing_only:
            self._queue_section.hide()
        else:
            self._rebuild_queue_ui()
        self._apply_filter()

    def _display_queue_indices(self) -> list[int]:
        return [
            index
            for index in self._queue_indices
            if index != self._current_index and 0 <= index < len(self._paths)
        ]

    def _rebuild_queue_ui(self) -> None:
        order = self._play_order_indices()
        if not order:
            self._queue_section.hide()
            return

        display_queue = self._display_queue_indices()
        self._queue_title.setText(f"Now playing + queue ({len(order)})")
        self._queue_list.set_reorder_enabled(len(display_queue) >= 2)
        self._queue_list.set_play_order(
            self._paths,
            current_index=self._current_index,
            queue_indices=self._queue_indices,
        )
        row_height = 34
        self._queue_list.setFixedHeight(max(1, self._queue_list.count()) * row_height + 6)
        self._queue_section.show()

    def set_sort_strategy(self, strategy: SortStrategy) -> None:
        index = self._sort_combo.findData(strategy)
        if index >= 0:
            self._sort_combo.blockSignals(True)
            self._sort_combo.setCurrentIndex(index)
            self._sort_combo.blockSignals(False)

    def set_songs(
        self,
        paths: list[Path],
        *,
        current_index: int | None = None,
        clear_search: bool = True,
    ) -> None:
        self._paths = paths
        self._current_index = current_index
        self._selected_index = None
        if clear_search:
            self._search.blockSignals(True)
            self._search.clear()
            self._search.blockSignals(False)
        if self._now_playing_only:
            self._queue_section.hide()
        else:
            self._rebuild_queue_ui()
        self._apply_filter()

    def set_current_index(self, index: int) -> None:
        self._current_index = index
        self._list.blockSignals(True)
        self._update_now_playing_filter_state()
        if not self._now_playing_only:
            self._rebuild_queue_ui()
        self._apply_filter()
        self._list.blockSignals(False)

    def playing_index(self) -> int | None:
        return self._current_index

    def _play_order_indices(self) -> list[int]:
        """Current song first, then queued songs in FIFO order."""
        order: list[int] = []
        if self._current_index is not None and 0 <= self._current_index < len(self._paths):
            order.append(self._current_index)
        order.extend(self._display_queue_indices())
        return order

    def _apply_filter(self) -> None:
        query = self._search.text().strip().lower()
        now_playing_only = self._now_playing_only
        total = len(self._paths)
        display_queue = self._display_queue_indices()

        self._list.blockSignals(True)

        if now_playing_only:
            self._list.set_reorder_enabled(len(display_queue) >= 2)
            self._list.set_play_order(
                self._paths,
                current_index=self._current_index,
                queue_indices=self._queue_indices,
            )
            visible = self._list.count()
            self._count_label.setText(
                f"{visible} shown (current + queue) · {total} total"
            )
            self._sync_list_selection()
            self._list.blockSignals(False)
            return

        self._list.set_reorder_enabled(False)
        candidate_indices = list(range(len(self._paths)))
        self._list.clear()

        visible = 0
        for i in candidate_indices:
            path = self._paths[i]
            name = display_name(path).lower()
            filename = path.name.lower()
            if (
                not now_playing_only
                and query
                and query not in name
                and query not in filename
            ):
                continue
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            title = display_name(path)
            if self._current_index is not None and i == self._current_index:
                title = f"▶ {title}"
            elif i in display_queue:
                queue_pos = display_queue.index(i) + 1
                title = f"⏭ {queue_pos} · {title}"
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, i)
            tip = f"{display_name(path)}\n{path}\nModified: {mtime.strftime('%Y-%m-%d %H:%M')}"
            if self._current_index is not None and i == self._current_index:
                tip = f"Now playing\n{tip}"
            elif i in display_queue:
                tip = f"Queued (#{display_queue.index(i) + 1})\n{tip}"
            item.setToolTip(tip)
            if self._current_index is not None and i == self._current_index:
                item.setForeground(QColor("#7ee787"))
            elif i in display_queue:
                item.setForeground(QColor("#ffb3c1"))
            self._list.addItem(item)
            visible += 1

        if query:
            self._count_label.setText(
                f"{visible} of {total} song{'s' if total != 1 else ''}"
            )
        else:
            self._count_label.setText(f"{total} song{'s' if total != 1 else ''}")

        self._sync_list_selection()
        self._list.blockSignals(False)

    def _sync_list_selection(self) -> None:
        if self._selected_index is None:
            self._list.clearSelection()
            self._list.setCurrentRow(-1)
            return
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == self._selected_index:
                self._list.setCurrentRow(row)
                self._list.scrollToItem(item)
                return
        self._list.clearSelection()
        self._list.setCurrentRow(-1)

    def show_panel(self) -> None:
        self.show()
        self.raise_()
