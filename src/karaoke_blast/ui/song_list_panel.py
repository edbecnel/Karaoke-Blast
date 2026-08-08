"""Sidebar song list with sort controls."""

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QPalette
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.models.sort_strategy import SortStrategy
from karaoke_blast.ui.context_menu_style import CONTEXT_MENU_STYLE
from karaoke_blast.ui.list_style import QUEUE_LIST_STYLE, SIDEBAR_LIST_STYLE
from karaoke_blast.ui.local_history_panel import LocalHistoryPanel
from karaoke_blast.ui.panel_splitter import EDGE_GRIP_WIDTH, PanelEdgeGrip
from karaoke_blast.ui.recent_folders_panel import PINNED_LABEL
from karaoke_blast.ui.queue_list_widget import PlayOrderListWidget, _ROLE_INDEX, _ROLE_PATH
from karaoke_blast.utils.display import display_name

PANEL_DEFAULT_WIDTH = 320
PANEL_MIN_WIDTH = 200
PANEL_MAX_WIDTH = 700
QUEUE_SECTION_DEFAULT_RATIO = 0.28
QUEUE_SECTION_MIN_RATIO = 0.12
QUEUE_SECTION_MAX_RATIO = 0.75
QUEUE_SECTION_MIN_HEIGHT = 72
LIST_MIN_HEIGHT = 80

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

QUEUE_SPLITTER_STYLE = """
QSplitter::handle:vertical {
    background: rgba(255, 255, 255, 30);
    height: 4px;
}
QSplitter::handle:vertical:hover {
    background: rgba(233, 69, 96, 160);
}
"""

FOLDER_BTN_STYLE = """
QPushButton {
    background: transparent;
    color: white;
    border: none;
    font-size: 16px;
    font-weight: bold;
    text-align: left;
    padding: 2px 4px;
    border-radius: 4px;
}
QPushButton:hover {
    background: rgba(255, 255, 255, 30);
}
QPushButton::menu-indicator {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 12px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #ffffff;
    margin-right: 4px;
}
"""


class SongListPanel(QWidget):
    """Left sidebar listing songs in the current folder."""

    song_selected = pyqtSignal(int)
    play_next_requested = pyqtSignal(int)
    remove_from_queue_requested = pyqtSignal(int)
    remove_path_from_queue_requested = pyqtSignal(object)
    play_path_requested = pyqtSignal(object)
    clear_queue_requested = pyqtSignal()
    queue_reordered = pyqtSignal(list)
    sort_changed = pyqtSignal(object)
    close_requested = pyqtSignal()
    refresh_requested = pyqtSignal()
    resize_dragged = pyqtSignal(int)
    queue_split_changed = pyqtSignal(float)
    history_play_requested = pyqtSignal(object)
    history_queue_requested = pyqtSignal(object)
    history_remove_requested = pyqtSignal(object)
    history_clear_requested = pyqtSignal()
    rename_requested = pyqtSignal(int)
    folder_selected = pyqtSignal(object)
    browse_folder_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(PANEL_MIN_WIDTH)
        self.setMaximumWidth(PANEL_MAX_WIDTH)
        # Resize grip is a real child widget (not CSS border) so hover works
        # even when VLC covers the QSplitter handle in macOS fullscreen.
        self.setStyleSheet("background-color: rgba(15, 15, 25, 230);")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, EDGE_GRIP_WIDTH + 8, 12)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        self._folder_btn = QPushButton("Songs")
        self._folder_btn.setStyleSheet(FOLDER_BTN_STYLE)
        self._folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._folder_btn.setToolTip("Switch folder")
        self._folder_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._folder_btn.clicked.connect(self._show_folder_menu)
        header_row.addWidget(self._folder_btn, 1)

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
        clear_queue_btn.setToolTip("Clear now playing and all queued songs")
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
        self._queue_list.setStyleSheet(QUEUE_LIST_STYLE)
        self._queue_list.itemClicked.connect(self._on_item_clicked)
        self._queue_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._queue_list.customContextMenuRequested.connect(self._show_queue_context_menu)
        self._queue_list.queue_reordered.connect(self.queue_reordered.emit)
        queue_outer.addWidget(self._queue_list, 1)
        self._queue_section.setMinimumHeight(QUEUE_SECTION_MIN_HEIGHT)
        layout.addWidget(self._queue_section)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: none; background: transparent; }"
            "QTabBar::tab {"
            " background: #2d2d42; color: #b8b8c8; padding: 8px 14px;"
            " border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px;"
            "}"
            "QTabBar::tab:selected { background: #e94560; color: white; }"
        )

        songs_tab = QWidget()
        songs_layout = QVBoxLayout(songs_tab)
        songs_layout.setContentsMargins(0, 0, 0, 0)
        songs_layout.setSpacing(8)

        self._sort_combo = QComboBox()
        self._sort_combo.setStyleSheet(COMBO_STYLE)
        sort_palette = self._sort_combo.palette()
        sort_palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        self._sort_combo.setPalette(sort_palette)
        for strategy in SortStrategy:
            self._sort_combo.addItem(strategy.label, strategy)
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        songs_layout.addWidget(self._sort_combo)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search songs…")
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet(SEARCH_STYLE)
        search_palette = self._search.palette()
        search_palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        search_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#b8b8c8"))
        self._search.setPalette(search_palette)
        self._search.textChanged.connect(self._apply_filter)
        songs_layout.addWidget(self._search)

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
        songs_layout.addWidget(self._now_playing_btn)

        self._count_label = QLabel()
        self._count_label.setStyleSheet("color: #888; font-size: 11px;")
        songs_layout.addWidget(self._count_label)

        self._list = PlayOrderListWidget()
        self._list.queue_reordered.connect(self.queue_reordered.emit)
        self._list.setStyleSheet(SIDEBAR_LIST_STYLE)
        self._list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._list.setMouseTracking(True)
        self._list.setMinimumHeight(LIST_MIN_HEIGHT)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        self._list.itemClicked.connect(self._on_item_clicked)

        self._list_splitter = QSplitter(Qt.Orientation.Vertical)
        self._list_splitter.setStyleSheet(QUEUE_SPLITTER_STYLE)
        self._list_splitter.setHandleWidth(4)
        self._list_splitter.setChildrenCollapsible(False)
        self._list_splitter.addWidget(self._list)
        self._list_splitter.setStretchFactor(0, 1)
        songs_layout.addWidget(self._list_splitter, 1)

        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_layout.setSpacing(8)

        history_header = QHBoxLayout()
        history_title = QLabel("History")
        history_title.setStyleSheet("color: #e94560; font-size: 12px; font-weight: bold;")
        history_header.addWidget(history_title)
        history_header.addStretch()
        clear_history_btn = QPushButton("Clear")
        clear_history_btn.setToolTip("Remove all history entries")
        clear_history_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #aaa; border: none;"
            " font-size: 11px; padding: 2px 6px; }"
            "QPushButton:hover { color: white; background: rgba(255,255,255,25);"
            " border-radius: 3px; }"
        )
        clear_history_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_history_btn.clicked.connect(self.history_clear_requested.emit)
        history_header.addWidget(clear_history_btn)
        history_layout.addLayout(history_header)

        self._history_list = LocalHistoryPanel()
        self._history_list.setStyleSheet(SIDEBAR_LIST_STYLE)
        self._history_list.setMinimumHeight(LIST_MIN_HEIGHT)
        self._history_list.play_requested.connect(self.history_play_requested)
        self._history_list.queue_requested.connect(self.history_queue_requested)
        self._history_list.remove_requested.connect(self.history_remove_requested)
        history_layout.addWidget(self._history_list, 1)

        self._tabs.addTab(songs_tab, "Songs")
        self._tabs.addTab(history_tab, "History")
        layout.addWidget(self._tabs, 1)

        self._paths: list[Path] = []
        self._current_folder: Path | None = None
        self._recent_folders: list[Path] = []
        self._pinned_folders: list[Path] = []
        self._current_index: int | None = None
        self._selected_index: int | None = None
        self._queue_indices: list[int] = []
        self._path_queue_paths: list[Path] = []
        self._external_current: Path | None = None
        self._queue_includes_now_playing = True
        self._now_playing_only = False
        self._queue_section_ratio: float | None = None

        self._edge_grip = PanelEdgeGrip(self)
        self._edge_grip.dragged.connect(self.resize_dragged.emit)
        self._edge_grip.raise_()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_queue_split_sizes)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_edge_grip()

    def raise_edge_grip(self) -> None:
        """Keep the grip above siblings after fullscreen / layout changes."""
        self._position_edge_grip()
        self._edge_grip.raise_()
        self._edge_grip.setCursor(Qt.CursorShape.SizeHorCursor)

    def _position_edge_grip(self) -> None:
        self._edge_grip.setGeometry(
            self.width() - EDGE_GRIP_WIDTH,
            0,
            EDGE_GRIP_WIDTH,
            self.height(),
        )

    def set_queue_section_ratio(self, ratio: float | None) -> None:
        self._queue_section_ratio = ratio

    def _apply_queue_split_sizes(self) -> None:
        return

    def set_history(self, paths: list[Path], *, current: Path | None = None) -> None:
        self._history_list.set_history(paths, current=current)

    def set_folder(self, folder: Path | None) -> None:
        self._current_folder = folder.resolve() if folder is not None else None
        if folder is None:
            self._folder_btn.setText("Songs")
            self._folder_btn.setToolTip("Switch folder")
        else:
            self._folder_btn.setText(folder.name)
            self._folder_btn.setToolTip(str(folder.resolve()))

    def set_recent_folders(
        self,
        folders: list[Path],
        *,
        pinned: list[Path] | None = None,
    ) -> None:
        self._recent_folders = folders
        self._pinned_folders = pinned or []

    def _show_folder_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)
        current = self._current_folder
        pinned_resolved = {path.resolve() for path in self._pinned_folders}

        for folder in self._pinned_folders:
            action = QAction(PINNED_LABEL, self)
            action.setToolTip(str(folder))
            resolved = folder.resolve()
            if current == resolved:
                action.setCheckable(True)
                action.setChecked(True)
                action.setEnabled(False)
            else:
                action.triggered.connect(
                    lambda _checked=False, selected=folder: self.folder_selected.emit(
                        selected
                    )
                )
            menu.addAction(action)

        recent = [
            folder
            for folder in self._recent_folders
            if folder.resolve() not in pinned_resolved
        ]
        if recent and self._pinned_folders:
            menu.addSeparator()

        for folder in recent:
            action = QAction(folder.name, self)
            action.setToolTip(str(folder))
            resolved = folder.resolve()
            if current == resolved:
                action.setCheckable(True)
                action.setChecked(True)
                action.setEnabled(False)
            else:
                action.triggered.connect(
                    lambda _checked=False, selected=folder: self.folder_selected.emit(
                        selected
                    )
                )
            menu.addAction(action)

        if self._pinned_folders or recent:
            menu.addSeparator()

        browse = QAction("Browse…", self)
        browse.triggered.connect(self.browse_folder_requested.emit)
        menu.addAction(browse)

        menu.exec(
            self._folder_btn.mapToGlobal(self._folder_btn.rect().bottomLeft())
        )

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
            self._apply_queue_split_sizes()
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
        has_queue = self._queue_row_count() > 0
        self._now_playing_btn.setEnabled(has_queue)
        if not has_queue:
            self._clear_now_playing_filter()

    def _on_sort_changed(self, _index: int) -> None:
        strategy = self._sort_combo.currentData()
        if strategy is not None:
            self.sort_changed.emit(strategy)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(_ROLE_PATH)
        if isinstance(path, Path):
            self.play_path_requested.emit(path)
            return
        index = item.data(_ROLE_INDEX)
        if index is None:
            return
        self._on_song_index_clicked(index)

    def _on_song_index_clicked(self, index: int) -> None:
        if index == self._selected_index:
            self.song_selected.emit(index)
        else:
            self._selected_index = index

    def _show_context_menu(self, pos) -> None:
        self._show_song_context_menu(self._list, pos, from_queue=False)

    def _show_queue_context_menu(self, pos) -> None:
        item = self._queue_list.itemAt(pos)
        if item is None:
            return
        path = item.data(_ROLE_PATH)
        if isinstance(path, Path):
            self._show_path_context_menu(self._queue_list, pos, path, from_queue=True)
            return
        index = item.data(_ROLE_INDEX)
        if index is None:
            return
        self._show_song_context_menu(self._queue_list, pos, from_queue=True, index=index)

    def _show_path_context_menu(
        self,
        list_widget: PlayOrderListWidget,
        pos,
        path: Path,
        *,
        from_queue: bool,
    ) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

        play_now = QAction("Play Now", self)
        play_now.triggered.connect(lambda: self.play_path_requested.emit(path))
        menu.addAction(play_now)

        play_next = QAction("Play Next", self)
        play_next.triggered.connect(lambda: self.history_queue_requested.emit(path))
        menu.addAction(play_next)

        if from_queue and self._is_path_in_path_queue(path):
            remove = QAction("Remove from Queue", self)
            remove.triggered.connect(
                lambda: self.remove_path_from_queue_requested.emit(path)
            )
            menu.addAction(remove)
        elif (
            from_queue
            and self._external_current is not None
            and self._paths_equal(path, self._external_current)
            and self._queue_includes_now_playing
        ):
            remove = QAction("Remove", self)
            remove.triggered.connect(
                lambda: self.remove_path_from_queue_requested.emit(path)
            )
            menu.addAction(remove)

        menu.exec(list_widget.mapToGlobal(pos))

    @staticmethod
    def _paths_equal(left: Path, right: Path) -> bool:
        try:
            return left.resolve() == right.resolve()
        except OSError:
            return left == right

    def _is_path_in_path_queue(self, path: Path) -> bool:
        try:
            target = path.resolve()
        except OSError:
            target = path
        for queued in self._path_queue_paths:
            try:
                if queued.resolve() == target:
                    return True
            except OSError:
                if queued == path:
                    return True
        return False

    def _show_song_context_menu(
        self,
        list_widget: PlayOrderListWidget,
        pos,
        *,
        from_queue: bool,
        index: int | None = None,
    ) -> None:
        if index is None:
            item = list_widget.itemAt(pos)
            if item is None:
                return
            index = item.data(_ROLE_INDEX)
            if index is None:
                return

        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

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
        elif (
            from_queue
            and index == self._current_index
            and self._queue_includes_now_playing
        ):
            remove = QAction("Remove", self)
            remove.triggered.connect(lambda: self.remove_from_queue_requested.emit(index))
            menu.addAction(remove)

        rename = QAction("Rename…", self)
        rename.triggered.connect(lambda: self.rename_requested.emit(index))
        menu.addAction(rename)

        menu.exec(list_widget.mapToGlobal(pos))

    def set_queue_indices(
        self,
        indices: list[int],
        *,
        include_now_playing: bool | None = None,
        external_current: Path | None = None,
        path_queue: list[Path] | None = None,
    ) -> None:
        self._queue_indices = indices
        self._external_current = external_current
        self._path_queue_paths = list(path_queue or [])
        if include_now_playing is not None:
            self._queue_includes_now_playing = include_now_playing
        self._update_now_playing_filter_state()
        if self._now_playing_only:
            self._queue_section.hide()
            self._apply_queue_split_sizes()
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
        order_count = self._queue_row_count()
        if order_count == 0:
            self._queue_section.hide()
            self._apply_queue_split_sizes()
            return

        display_queue = self._display_queue_indices()
        self._queue_title.setText(f"Now playing + queue ({order_count})")
        self._queue_list.set_reorder_enabled(
            not self._path_queue_paths and len(display_queue) >= 2
        )
        playlist_current = (
            None
            if self._external_current is not None
            else self._current_index
        )
        external = (
            self._external_current
            if self._queue_includes_now_playing
            else None
        )
        self._queue_list.set_play_order(
            self._paths,
            current_index=playlist_current,
            queue_indices=self._queue_indices,
            external_current=external,
            path_queue=self._path_queue_paths,
        )
        self._queue_section.show()
        self._apply_queue_split_sizes()

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
            self._apply_queue_split_sizes()
        else:
            self._rebuild_queue_ui()
        self._apply_filter()

    def set_current_index(self, index: int | None) -> None:
        self._current_index = index
        self._list.blockSignals(True)
        self._update_now_playing_filter_state()
        if not self._now_playing_only:
            self._rebuild_queue_ui()
        self._apply_filter()
        self._list.blockSignals(False)

    def clear_current_index(self) -> None:
        self.set_current_index(None)

    def playing_index(self) -> int | None:
        return self._current_index

    def _play_order_indices(self) -> list[int]:
        """Current song first, then queued songs in FIFO order."""
        order: list[int] = []
        if (
            self._queue_includes_now_playing
            and self._external_current is None
            and self._current_index is not None
            and 0 <= self._current_index < len(self._paths)
        ):
            order.append(self._current_index)
        order.extend(self._display_queue_indices())
        return order

    def _queue_row_count(self) -> int:
        count = 0
        if self._queue_includes_now_playing:
            if self._external_current is not None:
                count += 1
            elif (
                self._current_index is not None
                and 0 <= self._current_index < len(self._paths)
            ):
                count += 1
        count += len(self._path_queue_paths)
        count += len(self._display_queue_indices())
        return count

    def _apply_filter(self) -> None:
        query = self._search.text().strip().lower()
        now_playing_only = self._now_playing_only
        total = len(self._paths)
        display_queue = self._display_queue_indices()

        self._list.blockSignals(True)

        if now_playing_only:
            display_queue = self._display_queue_indices()
            self._list.set_reorder_enabled(
                not self._path_queue_paths and len(display_queue) >= 2
            )
            playlist_current = (
                None
                if self._external_current is not None
                else self._current_index
            )
            external = (
                self._external_current
                if self._queue_includes_now_playing
                else None
            )
            self._list.set_play_order(
                self._paths,
                current_index=playlist_current,
                queue_indices=self._queue_indices,
                external_current=external,
                path_queue=self._path_queue_paths,
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
