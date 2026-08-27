"""Sidebar song list with sort controls."""

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QPalette
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.models.sort_strategy import SortStrategy
from karaoke_blast.ui.context_menu_style import CONTEXT_MENU_STYLE, copy_text_to_clipboard
from karaoke_blast.ui.display_format_dialog import DisplayFormatDialog
from karaoke_blast.ui.list_style import QUEUE_LIST_STYLE, SIDEBAR_LIST_STYLE
from karaoke_blast.ui.local_history_panel import LocalHistoryPanel
from karaoke_blast.ui.panel_splitter import EDGE_GRIP_WIDTH, PanelEdgeGrip
from karaoke_blast.ui.recent_folders_panel import PINNED_LABEL
from karaoke_blast.ui.visible_space_field import VisibleSpaceLineEdit
from karaoke_blast.ui.queue_list_widget import PlayOrderListWidget, _ROLE_INDEX, _ROLE_PATH
from karaoke_blast.utils.file_manager import (
    open_folder_in_file_manager,
    reveal_action_label,
    reveal_in_file_manager,
    trash_action_label,
)
from karaoke_blast.utils.song_display import (
    DEFAULT_DISPLAY_FORMAT,
    DISPLAY_MODE_FILENAME,
    DISPLAY_MODE_METADATA,
    DisplayFormat,
    TagCache,
    song_display_label,
    song_matches_query,
)

PANEL_DEFAULT_WIDTH = 320
PANEL_MIN_WIDTH = 200
PANEL_MAX_WIDTH = 700
QUEUE_SECTION_DEFAULT_RATIO = 0.28
QUEUE_SECTION_MIN_RATIO = 0.12
QUEUE_SECTION_MAX_RATIO = 0.75
QUEUE_SECTION_MIN_HEIGHT = 72
LIST_MIN_HEIGHT = 80

_ROLE_NAV_UP = Qt.ItemDataRole.UserRole + 2
_ROLE_FOLDER = Qt.ItemDataRole.UserRole + 3

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
    padding: 2px 22px 2px 4px;
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


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


class SongListPanel(QWidget):
    """Left sidebar listing songs and subfolders in the current browse folder."""

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
    move_to_trash_requested = pyqtSignal(object)
    edit_metadata_requested = pyqtSignal(object)
    folder_selected = pyqtSignal(object)
    browse_folder_requested = pyqtSignal()
    folder_entered = pyqtSignal(object)
    navigate_up_requested = pyqtSignal()
    play_all_requested = pyqtSignal()
    queue_all_requested = pyqtSignal()
    play_all_folder_requested = pyqtSignal(object)
    queue_all_folder_requested = pyqtSignal(object)
    back_to_folders_requested = pyqtSignal()
    flat_browse_toggled = pyqtSignal(bool)
    display_mode_changed = pyqtSignal(str)
    display_format_changed = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None, *, embedded: bool = False) -> None:
        super().__init__(parent)
        self._embedded = embedded
        if not embedded:
            self.setMinimumWidth(PANEL_MIN_WIDTH)
            self.setMaximumWidth(PANEL_MAX_WIDTH)
            self.setStyleSheet("background-color: rgba(15, 15, 25, 230);")

        layout = QVBoxLayout(self)
        if embedded:
            layout.setContentsMargins(0, 0, 0, 0)
        else:
            layout.setContentsMargins(12, 12, EDGE_GRIP_WIDTH + 8, 12)
        layout.setSpacing(8)

        if not embedded:
            header_row = QHBoxLayout()
            self._folder_btn = QPushButton("Songs")
            self._folder_btn.setStyleSheet(FOLDER_BTN_STYLE)
            self._folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._folder_btn.setToolTip("Switch folder")
            self._folder_btn.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            self._folder_menu = QMenu(self)
            self._folder_menu.setStyleSheet(CONTEXT_MENU_STYLE)
            self._folder_menu.aboutToShow.connect(
                lambda: self.populate_folder_menu(self._folder_menu)
            )
            self._folder_btn.setMenu(self._folder_menu)
            self._folder_btn.setContextMenuPolicy(
                Qt.ContextMenuPolicy.CustomContextMenu
            )
            self._folder_btn.customContextMenuRequested.connect(
                self._show_folder_button_context_menu
            )
            header_row.addWidget(self._folder_btn, 1)

            self._back_folders_btn = QPushButton("←")
            self._back_folders_btn.setToolTip("Back to folders")
            self._back_folders_btn.setFixedSize(28, 28)
            self._back_folders_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #aaa; border: none;"
                " font-size: 16px; border-radius: 4px; }"
                "QPushButton:hover { background: rgba(255,255,255,30); color: white; }"
            )
            self._back_folders_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._back_folders_btn.clicked.connect(self.back_to_folders_requested.emit)
            self._back_folders_btn.hide()
            header_row.addWidget(self._back_folders_btn)

            self._folder_actions_btn = QPushButton("⋯")
            self._folder_actions_btn.setToolTip("Folder actions")
            self._folder_actions_btn.setFixedSize(28, 28)
            self._folder_actions_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #aaa; border: none;"
                " font-size: 18px; border-radius: 4px; }"
                "QPushButton:hover { background: rgba(255,255,255,30); color: white; }"
            )
            self._folder_actions_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._folder_actions_btn.clicked.connect(self._show_folder_actions_menu)
            header_row.addWidget(self._folder_actions_btn)

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

        self._flat_browse_btn = QPushButton("Include subfolders")
        self._flat_browse_btn.setCheckable(True)
        self._flat_browse_btn.setToolTip(
            "Show all media files in subfolders as a flat list"
        )
        self._flat_browse_btn.setStyleSheet(
            "QPushButton { background-color: #2d2d42; color: #b8b8c8; border: 1px solid #5a5a72;"
            " border-radius: 4px; padding: 6px 10px; font-size: 12px; }"
            "QPushButton:hover { border-color: #7a7a92; color: white; }"
            "QPushButton:checked { background-color: #e94560; color: white; border-color: #e94560; }"
        )
        self._flat_browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._flat_browse_btn.toggled.connect(self._on_flat_browse_toggled)
        songs_layout.addWidget(self._flat_browse_btn)

        if not embedded:
            self._search = VisibleSpaceLineEdit()
            self._search.setPlaceholderText("Search songs…")
            self._search.setClearButtonEnabled(True)
            self._search.setStyleSheet(SEARCH_STYLE)
            search_palette = self._search.palette()
            search_palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
            search_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#b8b8c8"))
            self._search.setPalette(search_palette)
            self._search.textChanged.connect(self._apply_filter)
            songs_layout.addWidget(self._search)
        else:
            self._search = None
            self._back_folders_btn = QPushButton("← Back to folders")
            self._back_folders_btn.setStyleSheet(
                "QPushButton { background-color: #2d2d42; color: #b8b8c8; border: 1px solid #5a5a72;"
                " border-radius: 4px; padding: 6px 10px; font-size: 12px; text-align: left; }"
                "QPushButton:hover { border-color: #7a7a92; color: white; }"
            )
            self._back_folders_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._back_folders_btn.clicked.connect(self.back_to_folders_requested.emit)
            self._back_folders_btn.hide()
            songs_layout.addWidget(self._back_folders_btn)

        display_row = QHBoxLayout()
        display_row.setSpacing(6)
        self._metadata_btn = QPushButton("Metadata")
        self._metadata_btn.setCheckable(True)
        self._metadata_btn.setToolTip(
            "Show embedded metadata fields instead of the file name"
        )
        self._metadata_btn.setStyleSheet(
            "QPushButton { background-color: #2d2d42; color: #b8b8c8; border: 1px solid #5a5a72;"
            " border-radius: 4px; padding: 6px 10px; font-size: 12px; }"
            "QPushButton:hover { border-color: #7a7a92; color: white; }"
            "QPushButton:checked { background-color: #e94560; color: white; border-color: #e94560; }"
        )
        self._metadata_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._metadata_btn.toggled.connect(self._on_metadata_toggled)
        display_row.addWidget(self._metadata_btn, 1)

        self._display_format_btn = QPushButton("⚙")
        self._display_format_btn.setFixedSize(32, 32)
        self._display_format_btn.setToolTip("Configure metadata display format")
        self._display_format_btn.setStyleSheet(
            "QPushButton { background-color: #2d2d42; color: #b8b8c8; border: 1px solid #5a5a72;"
            " border-radius: 4px; font-size: 14px; }"
            "QPushButton:hover { border-color: #7a7a92; color: white; }"
        )
        self._display_format_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._display_format_btn.clicked.connect(self._open_display_format_dialog)
        display_row.addWidget(self._display_format_btn)
        songs_layout.addLayout(display_row)

        if not embedded:
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
        else:
            self._now_playing_btn = None

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

        if embedded:
            layout.addWidget(songs_tab, 1)
        else:
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
            self._history_list.play_requested.connect(self.history_play_requested.emit)
            self._history_list.queue_requested.connect(self.history_queue_requested.emit)
            self._history_list.remove_requested.connect(self.history_remove_requested.emit)
            self._history_list.edit_metadata_requested.connect(
                self.edit_metadata_requested.emit
            )
            history_layout.addWidget(self._history_list, 1)

            self._tabs.addTab(songs_tab, "Songs")
            self._tabs.addTab(history_tab, "History")
            layout.addWidget(self._tabs, 1)

        self._paths: list[Path] = []
        self._subfolders: list[Path] = []
        self._can_navigate_up = False
        self._flat_list_mode = False
        self._show_back_to_folders = False
        self._flat_browse_enabled = False
        self._label_root: Path | None = None
        self._library_root: Path | None = None
        self._search_query = ""
        self._current_folder: Path | None = None
        self._recent_folders: list[Path] = []
        self._pinned_folders: list[Path] = []
        self._pinned_folder_label: str | None = None
        self._current_index: int | None = None
        self._selected_index: int | None = None
        self._queue_indices: list[int] = []
        self._path_queue_paths: list[Path] = []
        self._external_current: Path | None = None
        self._queue_includes_now_playing = True
        self._now_playing_only = False
        self._queue_section_ratio: float | None = None
        self._display_mode = DISPLAY_MODE_FILENAME
        self._display_format = DEFAULT_DISPLAY_FORMAT.copy()
        self._media_type_name = "Songs"
        self._display_field_labels: dict[str, str] = {}
        self._use_song_count_label = True
        self._tag_cache = TagCache()
        self._list.set_display_resolver(self._leaf_label)
        if not embedded:
            self._queue_list.set_display_resolver(self._leaf_label)
            self._history_list.set_display_resolver(self._leaf_label)
            self._edge_grip = PanelEdgeGrip(self)
            self._edge_grip.dragged.connect(self.resize_dragged.emit)
            self._edge_grip.raise_()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_queue_split_sizes)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._embedded:
            self._position_edge_grip()

    def raise_edge_grip(self) -> None:
        """Keep the grip above siblings after fullscreen / layout changes."""
        if self._embedded:
            return
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

    def set_flat_browse_enabled(self, enabled: bool) -> None:
        self._flat_browse_enabled = enabled
        self._flat_browse_btn.blockSignals(True)
        self._flat_browse_btn.setChecked(enabled)
        self._flat_browse_btn.blockSignals(False)

    def flat_browse_enabled(self) -> bool:
        return self._flat_browse_enabled

    def _on_flat_browse_toggled(self, checked: bool) -> None:
        self._flat_browse_enabled = checked
        self.flat_browse_toggled.emit(checked)

    def set_search_query(self, query: str) -> None:
        self._search_query = query.strip()
        self._apply_filter()

    def set_library_root(self, root: Path | None) -> None:
        self._library_root = root.resolve() if root is not None else None

    def display_resolver(self):
        return self._leaf_label

    def display_sort_key(self, path: Path) -> str:
        return self._leaf_label(path)

    def set_display_mode(self, mode: str) -> None:
        normalized = (
            DISPLAY_MODE_METADATA
            if mode == DISPLAY_MODE_METADATA
            else DISPLAY_MODE_FILENAME
        )
        if normalized == self._display_mode:
            self._metadata_btn.blockSignals(True)
            self._metadata_btn.setChecked(normalized == DISPLAY_MODE_METADATA)
            self._metadata_btn.blockSignals(False)
            return
        self._display_mode = normalized
        self._metadata_btn.blockSignals(True)
        self._metadata_btn.setChecked(normalized == DISPLAY_MODE_METADATA)
        self._metadata_btn.blockSignals(False)
        self._refresh_display_labels()

    def set_display_format(self, fmt: DisplayFormat) -> None:
        self._display_format = fmt.copy()
        self._refresh_display_labels()

    def set_media_display_context(
        self,
        *,
        media_type_name: str,
        field_labels: dict[str, str],
        fmt: DisplayFormat | None = None,
    ) -> None:
        self._media_type_name = media_type_name.strip() or "Media"
        self._display_field_labels = dict(field_labels)
        if fmt is not None:
            self._display_format = fmt.copy()
        self._refresh_display_labels()

    def display_mode(self) -> str:
        return self._display_mode

    def display_format(self) -> DisplayFormat:
        return self._display_format.copy()

    def set_use_song_count_label(self, use_song_terminology: bool) -> None:
        if self._use_song_count_label == use_song_terminology:
            return
        self._use_song_count_label = use_song_terminology
        if self._paths:
            self._apply_filter()

    def _format_item_count(self, count: int) -> str:
        if self._use_song_count_label:
            return f"{count} song{'s' if count != 1 else ''}"
        return f"{count} entr{'y' if count == 1 else 'ies'}"

    def _format_item_count_range(self, visible: int, total: int) -> str:
        if self._use_song_count_label:
            noun = "song" if total == 1 else "songs"
            return f"{visible} of {total} {noun}"
        noun = "entry" if total == 1 else "entries"
        return f"{visible} of {total} {noun}"

    def _leaf_label(self, path: Path) -> str:
        return song_display_label(
            path,
            mode=self._display_mode,
            fmt=self._display_format,
            cache=self._tag_cache,
        )

    def _on_metadata_toggled(self, checked: bool) -> None:
        mode = DISPLAY_MODE_METADATA if checked else DISPLAY_MODE_FILENAME
        if mode == self._display_mode:
            return
        self._display_mode = mode
        self._refresh_display_labels()
        self.display_mode_changed.emit(mode)

    def _open_display_format_dialog(self) -> None:
        dialog = DisplayFormatDialog(
            self._display_format,
            media_type_name=self._media_type_name,
            field_labels=self._display_field_labels,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._display_format = dialog.format()
        self._refresh_display_labels()
        self.display_format_changed.emit(self._display_format.copy())

    def refresh_display_labels(self) -> None:
        """Reload list labels after metadata or display settings change."""
        self._refresh_display_labels()

    def _refresh_display_labels(self) -> None:
        self._tag_cache.clear()
        self._list.set_display_resolver(self._leaf_label)
        if not self._embedded:
            self._queue_list.set_display_resolver(self._leaf_label)
            self._history_list.set_display_resolver(self._leaf_label)
            if not self._now_playing_only:
                self._rebuild_queue_ui()
        self._apply_filter()

    def _apply_queue_split_sizes(self) -> None:
        return

    def set_history(self, paths: list[Path], *, current: Path | None = None) -> None:
        if not self._embedded:
            self._history_list.set_history(paths, current=current)

    def set_folder(self, folder: Path | None) -> None:
        self._current_folder = folder.resolve() if folder is not None else None
        if self._embedded:
            return
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
        pinned_label: str | None = None,
    ) -> None:
        self._recent_folders = folders
        self._pinned_folders = pinned or []
        self._pinned_folder_label = pinned_label

    def _open_folder_in_file_manager(self, folder: Path) -> None:
        if not open_folder_in_file_manager(folder):
            QMessageBox.warning(
                self,
                "Folder Not Found",
                f"The folder no longer exists:\n{folder}",
            )

    def _reveal_path_in_file_manager(self, path: Path) -> None:
        if not reveal_in_file_manager(path):
            QMessageBox.warning(
                self,
                "File Not Found",
                f"The file no longer exists:\n{path}",
            )

    def _open_current_folder_in_file_manager(self) -> None:
        if self._current_folder is None:
            return
        self._open_folder_in_file_manager(self._current_folder)

    def copy_current_folder_path(self) -> None:
        if self._current_folder is None:
            return
        copy_text_to_clipboard(str(self._current_folder))

    def show_folder_path_context_menu(self, widget: QWidget, pos) -> None:
        if self._current_folder is None:
            return
        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)
        copy_path = QAction("Copy path to clipboard", self)
        copy_path.triggered.connect(self.copy_current_folder_path)
        menu.addAction(copy_path)
        menu.exec(widget.mapToGlobal(pos))

    def _show_folder_button_context_menu(self, pos) -> None:
        if self._embedded:
            return
        self.show_folder_path_context_menu(self._folder_btn, pos)

    def _show_folder_actions_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

        browse_folder = QAction("Browse folder", self)
        browse_folder.setEnabled(self._current_folder is not None)
        browse_folder.triggered.connect(self._open_current_folder_in_file_manager)
        menu.addAction(browse_folder)
        menu.addSeparator()

        if self._show_back_to_folders:
            back = QAction("Back to folders", self)
            back.triggered.connect(self.back_to_folders_requested.emit)
            menu.addAction(back)
            menu.addSeparator()

        include_subfolders = QAction("Include subfolders", self)
        include_subfolders.setCheckable(True)
        include_subfolders.setChecked(self._flat_browse_enabled)
        include_subfolders.triggered.connect(
            lambda checked: self._flat_browse_btn.setChecked(checked)
        )
        menu.addAction(include_subfolders)
        menu.addSeparator()

        play_all = QAction("Play all under this folder", self)
        play_all.triggered.connect(self.play_all_requested.emit)
        menu.addAction(play_all)

        queue_all = QAction("Queue all under this folder", self)
        queue_all.triggered.connect(self.queue_all_requested.emit)
        menu.addAction(queue_all)

        menu.exec(
            self._folder_actions_btn.mapToGlobal(
                self._folder_actions_btn.rect().bottomLeft()
            )
        )

    def populate_folder_menu(self, menu: QMenu) -> None:
        """Fill *menu* with pinned and recent folders from the start-screen list."""
        menu.clear()
        current = self._current_folder
        pinned_resolved = {_safe_resolve(path) for path in self._pinned_folders}
        pinned_label = self._pinned_folder_label or PINNED_LABEL

        for folder in self._pinned_folders:
            self._add_folder_menu_action(menu, folder, pinned_label, current)

        recent = [
            folder
            for folder in self._recent_folders
            if _safe_resolve(folder) not in pinned_resolved
        ]
        if recent and self._pinned_folders:
            menu.addSeparator()

        for folder in recent:
            self._add_folder_menu_action(menu, folder, folder.name, current)

        if self._pinned_folders or recent:
            menu.addSeparator()

        copy_path = QAction("Copy path to clipboard", menu)
        copy_path.setEnabled(current is not None)
        if current is not None:
            copy_path.setToolTip(str(current))
        copy_path.triggered.connect(self.copy_current_folder_path)
        menu.addAction(copy_path)

        menu.addSeparator()

        browse = QAction("Browse…", menu)
        browse.triggered.connect(self.browse_folder_requested.emit)
        menu.addAction(browse)

    def _add_folder_menu_action(
        self,
        menu: QMenu,
        folder: Path,
        label: str,
        current: Path | None,
    ) -> None:
        action = QAction(label, menu)
        action.setToolTip(str(folder))
        resolved = _safe_resolve(folder)
        if current is not None and current == resolved:
            action.setCheckable(True)
            action.setChecked(True)
            action.setEnabled(False)
        else:
            action.triggered.connect(
                lambda _checked=False, selected=folder: self.folder_selected.emit(selected)
            )
        menu.addAction(action)

    def _on_refresh_clicked(self, _checked: bool = False) -> None:
        self.refresh_requested.emit()

    def _on_close_clicked(self, _checked: bool = False) -> None:
        self.close_requested.emit()

    def _on_clear_queue_clicked(self, _checked: bool = False) -> None:
        self.clear_queue_requested.emit()

    def _on_now_playing_filter_toggled(self, checked: bool) -> None:
        if self._embedded or self._search is None:
            return
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
        if self._embedded or not self._now_playing_only:
            return
        self._now_playing_only = False
        self._search.setEnabled(True)
        self._now_playing_btn.blockSignals(True)
        self._now_playing_btn.setChecked(False)
        self._now_playing_btn.blockSignals(False)
        self._rebuild_queue_ui()
        self._apply_filter()

    def _update_now_playing_filter_state(self) -> None:
        if self._embedded or self._now_playing_btn is None:
            return
        has_queue = self._queue_row_count() > 0
        self._now_playing_btn.setEnabled(has_queue)
        if not has_queue:
            self._clear_now_playing_filter()

    def _on_sort_changed(self, _index: int) -> None:
        strategy = self._sort_combo.currentData()
        if strategy is not None:
            self.sort_changed.emit(strategy)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        if item.data(_ROLE_NAV_UP):
            self.navigate_up_requested.emit()
            return
        folder = item.data(_ROLE_FOLDER)
        if isinstance(folder, Path):
            self.folder_entered.emit(folder)
            return
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
        item = self._list.itemAt(pos)
        if item is not None:
            if item.data(_ROLE_NAV_UP):
                return
            folder = item.data(_ROLE_FOLDER)
            if isinstance(folder, Path):
                self._show_folder_item_context_menu(pos, folder)
                return
            path = item.data(_ROLE_PATH)
            if isinstance(path, Path):
                self._show_path_context_menu(
                    self._list, pos, path, from_queue=False
                )
                return
        self._show_song_context_menu(self._list, pos, from_queue=False)

    def _show_folder_item_context_menu(self, pos, folder: Path) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

        open_folder = QAction("Open", self)
        open_folder.triggered.connect(lambda: self.folder_entered.emit(folder))
        menu.addAction(open_folder)

        copy_path = QAction("Copy path to clipboard", self)
        copy_path.triggered.connect(
            lambda _checked=False, selected=folder: copy_text_to_clipboard(str(selected))
        )
        menu.addAction(copy_path)

        menu.addSeparator()

        play_all = QAction("Play all under this folder", self)
        play_all.triggered.connect(lambda: self.play_all_folder_requested.emit(folder))
        menu.addAction(play_all)

        queue_all = QAction("Queue all under this folder", self)
        queue_all.triggered.connect(lambda: self.queue_all_folder_requested.emit(folder))
        menu.addAction(queue_all)

        menu.exec(self._list.mapToGlobal(pos))

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

        browse_folder = QAction(reveal_action_label(), self)
        browse_folder.triggered.connect(
            lambda _checked=False, p=path: self._reveal_path_in_file_manager(p)
        )
        menu.addAction(browse_folder)

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

        edit_meta = QAction("Edit Metadata…", self)
        edit_meta.triggered.connect(
            lambda: self.edit_metadata_requested.emit(path)
        )
        menu.addAction(edit_meta)

        menu.addSeparator()

        move_to_trash = QAction(trash_action_label(), self)
        move_to_trash.triggered.connect(
            lambda _checked=False, selected=path: self.move_to_trash_requested.emit(
                selected
            )
        )
        menu.addAction(move_to_trash)

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
        if 0 <= index < len(self._paths):
            path = self._paths[index]
            play_now.triggered.connect(lambda _checked=False, p=path: self.play_path_requested.emit(p))
        else:
            play_now.triggered.connect(lambda: self.song_selected.emit(index))
        menu.addAction(play_now)

        play_next = QAction("Play Next", self)
        play_next.triggered.connect(lambda: self.play_next_requested.emit(index))
        menu.addAction(play_next)

        if 0 <= index < len(self._paths):
            path = self._paths[index]
            reveal_file = QAction(reveal_action_label(), self)
            reveal_file.triggered.connect(
                lambda _checked=False, p=path: self._reveal_path_in_file_manager(p)
            )
            menu.addAction(reveal_file)

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

        if 0 <= index < len(self._paths):
            path = self._paths[index]
            edit_meta = QAction("Edit Metadata…", self)
            edit_meta.triggered.connect(
                lambda _checked=False, p=path: self.edit_metadata_requested.emit(p)
            )
            menu.addAction(edit_meta)

            menu.addSeparator()

            move_to_trash = QAction(trash_action_label(), self)
            move_to_trash.triggered.connect(
                lambda _checked=False, p=path: self.move_to_trash_requested.emit(p)
            )
            menu.addAction(move_to_trash)

        menu.exec(list_widget.mapToGlobal(pos))

    def set_queue_indices(
        self,
        indices: list[int],
        *,
        include_now_playing: bool | None = None,
        external_current: Path | None = None,
        path_queue: list[Path] | None = None,
    ) -> None:
        if self._embedded:
            return
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
        if self._embedded:
            return
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
        subfolders: list[Path] | None = None,
        can_navigate_up: bool = False,
        flat_list_mode: bool = False,
        show_back_to_folders: bool = False,
        label_root: Path | None = None,
    ) -> None:
        self._paths = paths
        self._subfolders = list(subfolders or [])
        self._can_navigate_up = can_navigate_up
        self._flat_list_mode = flat_list_mode
        self._show_back_to_folders = show_back_to_folders
        self._label_root = label_root.resolve() if label_root is not None else None
        self._current_index = current_index
        self._selected_index = None
        if self._show_back_to_folders:
            self._back_folders_btn.show()
        elif self._embedded and self._search_query:
            self._back_folders_btn.show()
        else:
            self._back_folders_btn.hide()
        if clear_search:
            self._search_query = ""
            if self._search is not None:
                self._search.blockSignals(True)
                self._search.clear()
                self._search.blockSignals(False)
        if not self._embedded:
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
        if not self._embedded and not self._now_playing_only:
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

    def _song_label(self, path: Path) -> str:
        leaf = self._leaf_label(path)
        root = self._label_root or self._library_root
        if root is not None and (self._flat_list_mode or bool(self._search_query)):
            try:
                relative = path.resolve().relative_to(root)
            except (OSError, ValueError):
                return leaf
            parts = list(relative.parts[:-1]) + [leaf]
            return "/".join(parts) if parts else leaf
        return leaf

    def _apply_filter(self) -> None:
        query = (
            self._search_query.lower()
            if self._embedded
            else (self._search.text().strip().lower() if self._search is not None else "")
        )
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
        self._list.clear()

        visible_folders = 0
        if self._can_navigate_up and not query:
            up_item = QListWidgetItem("‥  Up")
            up_item.setData(_ROLE_INDEX, None)
            up_item.setData(_ROLE_PATH, None)
            up_item.setData(_ROLE_NAV_UP, True)
            up_item.setData(_ROLE_FOLDER, None)
            up_item.setToolTip("Go to parent folder")
            up_item.setForeground(QColor("#8ab4f8"))
            self._list.addItem(up_item)

        for folder in self._subfolders:
            name = folder.name
            if query and query not in name.lower():
                continue
            item = QListWidgetItem(f"{name}/")
            item.setData(_ROLE_INDEX, None)
            item.setData(_ROLE_PATH, None)
            item.setData(_ROLE_NAV_UP, False)
            item.setData(_ROLE_FOLDER, folder)
            try:
                tip_path = folder.resolve()
            except OSError:
                tip_path = folder
            item.setToolTip(str(tip_path))
            item.setForeground(QColor("#8ab4f8"))
            self._list.addItem(item)
            visible_folders += 1

        visible = 0
        for i in range(len(self._paths)):
            path = self._paths[i]
            label = self._song_label(path)
            if query and not song_matches_query(
                path,
                query,
                mode=self._display_mode,
                fmt=self._display_format,
                cache=self._tag_cache,
                label=label,
            ):
                continue
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                mtime_text = mtime.strftime("%Y-%m-%d %H:%M")
            except OSError:
                mtime_text = "unknown"
            title = label
            if self._current_index is not None and i == self._current_index:
                title = f"▶ {title}"
            elif i in display_queue:
                queue_pos = display_queue.index(i) + 1
                title = f"⏭ {queue_pos} · {title}"
            item = QListWidgetItem(title)
            item.setData(_ROLE_INDEX, i)
            item.setData(_ROLE_PATH, None)
            item.setData(_ROLE_NAV_UP, False)
            item.setData(_ROLE_FOLDER, None)
            tip = f"{label}\n{path}\nModified: {mtime_text}"
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

        folder_part = ""
        if not self._flat_list_mode and self._subfolders:
            if query:
                folder_part = (
                    f"{visible_folders} of {len(self._subfolders)} folder"
                    f"{'s' if len(self._subfolders) != 1 else ''}"
                )
            else:
                folder_part = (
                    f"{len(self._subfolders)} folder"
                    f"{'s' if len(self._subfolders) != 1 else ''}"
                )

        if query:
            song_part = self._format_item_count_range(visible, total)
        else:
            song_part = self._format_item_count(total)

        if folder_part:
            self._count_label.setText(f"{folder_part} · {song_part}")
        else:
            self._count_label.setText(song_part)

        self._sync_list_selection()
        self._list.blockSignals(False)

    def _sync_list_selection(self) -> None:
        if self._selected_index is None:
            self._list.clearSelection()
            self._list.setCurrentRow(-1)
            return
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item.data(_ROLE_INDEX) == self._selected_index:
                self._list.setCurrentRow(row)
                self._list.scrollToItem(item)
                return
        self._list.clearSelection()
        self._list.setCurrentRow(-1)

    def show_panel(self) -> None:
        self.show()
        self.raise_()
