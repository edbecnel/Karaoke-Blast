"""Unified library sidebar with local search, YouTube search, history, and queue."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.models.play_history_entry import PlayHistoryEntry
from karaoke_blast.models.queue_item import QueueItem
from karaoke_blast.models.youtube_video import YouTubeVideo
from karaoke_blast.ui.checkbox_style import CHECKBOX_STYLE
from karaoke_blast.ui.context_menu_style import CONTEXT_MENU_STYLE
from karaoke_blast.ui.list_style import SIDEBAR_LIST_STYLE
from karaoke_blast.ui.mixed_queue_list_widget import (
    QUEUE_PANEL_LIST_STYLE,
    MixedQueueListWidget,
)
from karaoke_blast.ui.panel_splitter import EDGE_GRIP_WIDTH, PanelEdgeGrip
from karaoke_blast.ui.play_history_panel import PlayHistoryPanel
from karaoke_blast.ui.song_list_panel import SongListPanel
from karaoke_blast.ui.visible_space_field import VisibleSpaceLineEdit
from karaoke_blast.ui.youtube_download_status import YouTubeDownloadStatus
from karaoke_blast.ui.youtube_downloads_folder_row import YouTubeDownloadsFolderRow
from karaoke_blast.ui.youtube_search_panel import (
    PANEL_MAX_WIDTH,
    PANEL_MIN_WIDTH,
    RESULTS_MIN_HEIGHT,
    YouTubeSearchPanel,
)
from karaoke_blast.utils.song_display import DisplayFormat
from karaoke_blast.utils.youtube_url import extract_video_id

PANEL_DEFAULT_WIDTH = 320
QUEUE_SECTION_MIN_HEIGHT = 72
LIST_MIN_HEIGHT = 80
QUEUE_SECTION_DEFAULT_RATIO = 0.28

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

INPUT_STYLE = SEARCH_STYLE

SEARCH_BTN_STYLE = (
    "QPushButton { background-color: #e94560; color: white; border: none;"
    " border-radius: 4px; padding: 8px 12px; font-size: 13px; font-weight: bold; }"
    "QPushButton:hover { background-color: #ff6b81; }"
    "QPushButton:disabled { background-color: #5a5a72; color: #ccc; }"
)

SEARCH_MORE_BTN_STYLE = (
    "QPushButton { background-color: #2d2d42; color: white; border: 1px solid #5a5a72;"
    " border-radius: 4px; padding: 8px 12px; font-size: 13px; }"
    "QPushButton:hover { background-color: #3a3a52; border-color: #7a7a92; }"
    "QPushButton:disabled { background-color: #1a1a28; color: #666; border-color: #3a3a52; }"
)

TAB_STYLE = (
    "QTabWidget::pane { border: none; background: transparent; }"
    "QTabBar::tab {"
    " background: #2d2d42; color: #b8b8c8; padding: 8px 14px;"
    " border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px;"
    "}"
    "QTabBar::tab:selected { background: #e94560; color: white; }"
)

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

_DISMISS_BTN_STYLE = (
    "QPushButton { background: transparent; color: #aaa; border: none;"
    " font-size: 16px; border-radius: 4px; }"
    "QPushButton:hover { background: rgba(255,255,255,30); color: white; }"
)

_URL_STATUS_STYLE = "color: #aaa; font-size: 11px;"
_URL_ERROR_STYLE = "color: #ff6b81; font-size: 11px;"

TAB_LOCAL = 0
TAB_YOUTUBE = 1
TAB_HISTORY = 2


class LibraryPanel(QWidget):
    """Unified sidebar for local files, YouTube, history, and the mixed queue."""

    song_selected = pyqtSignal(int)
    play_next_requested = pyqtSignal(int)
    play_path_requested = pyqtSignal(object)
    sort_changed = pyqtSignal(object)
    refresh_requested = pyqtSignal()
    local_search_changed = pyqtSignal(str)
    display_mode_changed = pyqtSignal(str)
    display_format_changed = pyqtSignal(object)
    rename_requested = pyqtSignal(int)
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
    close_requested = pyqtSignal()
    resize_dragged = pyqtSignal(int)
    queue_reordered = pyqtSignal(list)
    remove_from_queue_requested = pyqtSignal(object)
    clear_queue_requested = pyqtSignal()
    play_requested = pyqtSignal(object)
    queue_requested = pyqtSignal(object)
    youtube_play_requested = pyqtSignal(object)
    youtube_queue_requested = pyqtSignal(object)
    download_requested = pyqtSignal(object)
    history_play_requested = pyqtSignal(object)
    history_queue_requested = pyqtSignal(object)
    history_remove_requested = pyqtSignal(object)
    history_clear_requested = pyqtSignal()
    search_backend_fallback = pyqtSignal(str)
    append_karaoke_changed = pyqtSignal(bool)
    browse_downloads_folder_requested = pyqtSignal()
    youtube_search_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(PANEL_MIN_WIDTH)
        self.setMaximumWidth(PANEL_MAX_WIDTH)
        self.setStyleSheet("background-color: rgba(15, 15, 25, 230);")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, EDGE_GRIP_WIDTH + 8, 12)
        layout.setSpacing(8)

        self._song_list = SongListPanel(embedded=True)

        header_row = QHBoxLayout()
        self._folder_btn = QPushButton("Library")
        self._folder_btn.setStyleSheet(FOLDER_BTN_STYLE)
        self._folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._folder_btn.setToolTip("Switch folder")
        self._folder_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._folder_menu = QMenu(self)
        self._folder_menu.setStyleSheet(CONTEXT_MENU_STYLE)
        self._folder_menu.aboutToShow.connect(
            lambda: self._song_list.populate_folder_menu(self._folder_menu)
        )
        self._folder_btn.setMenu(self._folder_menu)
        header_row.addWidget(self._folder_btn, 1)

        refresh_btn = QPushButton("↻")
        refresh_btn.setToolTip("Refresh song list")
        refresh_btn.setFixedSize(28, 28)
        refresh_btn.setStyleSheet(_DISMISS_BTN_STYLE)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        header_row.addWidget(refresh_btn)

        close_btn = QPushButton("×")
        close_btn.setToolTip("Hide library panel (L)")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(_DISMISS_BTN_STYLE)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close_requested.emit)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        self._search = VisibleSpaceLineEdit()
        self._search.setPlaceholderText("Search songs or YouTube…")
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet(SEARCH_STYLE)
        search_palette = self._search.palette()
        search_palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        search_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#b8b8c8"))
        self._search.setPalette(search_palette)
        self._search.textChanged.connect(self._on_search_text_changed)
        self._search.returnPressed.connect(self._on_search_return_pressed)
        layout.addWidget(self._search)

        self._search_panel = YouTubeSearchPanel(embedded=True)
        self._search_panel.play_requested.connect(self.youtube_play_requested)
        self._search_panel.queue_requested.connect(self.youtube_queue_requested)
        self._search_panel.download_requested.connect(self.download_requested)
        self._search_panel.search_backend_fallback.connect(self.search_backend_fallback)
        self._search_panel.append_karaoke_changed.connect(self._sync_append_karaoke)

        self._youtube_controls = QWidget()
        youtube_controls_layout = QVBoxLayout(self._youtube_controls)
        youtube_controls_layout.setContentsMargins(0, 0, 0, 0)
        youtube_controls_layout.setSpacing(6)

        self._append_karaoke_checkbox = QCheckBox('Append "karaoke" to search')
        self._append_karaoke_checkbox.setChecked(True)
        self._append_karaoke_checkbox.setStyleSheet(CHECKBOX_STYLE)
        self._append_karaoke_checkbox.toggled.connect(self.append_karaoke_changed.emit)
        youtube_controls_layout.addWidget(self._append_karaoke_checkbox)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self._search_btn = QPushButton("Search")
        self._search_btn.setStyleSheet(SEARCH_BTN_STYLE)
        self._search_btn.clicked.connect(self._trigger_youtube_search)
        search_row.addWidget(self._search_btn)
        self._search_more_btn = QPushButton("Search more")
        self._search_more_btn.setStyleSheet(SEARCH_MORE_BTN_STYLE)
        self._search_more_btn.clicked.connect(self._search_panel.start_search_more)
        search_row.addWidget(self._search_more_btn)
        youtube_controls_layout.addLayout(search_row)
        self._search_panel.search_more_enabled_changed.connect(self._search_more_btn.setEnabled)
        self._youtube_controls.hide()
        layout.addWidget(self._youtube_controls)

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
        clear_queue_btn.setToolTip("Clear now playing and all queued items")
        clear_queue_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #aaa; border: none;"
            " font-size: 11px; padding: 2px 6px; }"
            "QPushButton:hover { color: white; background: rgba(255,255,255,25);"
            " border-radius: 3px; }"
        )
        clear_queue_btn.clicked.connect(self.clear_queue_requested.emit)
        queue_header.addWidget(clear_queue_btn)
        queue_outer.addLayout(queue_header)

        self._queue_list = MixedQueueListWidget()
        self._queue_list.setStyleSheet(QUEUE_PANEL_LIST_STYLE)
        self._queue_list.play_requested.connect(self.play_requested)
        self._queue_list.queue_requested.connect(self.queue_requested)
        self._queue_list.remove_requested.connect(self.remove_from_queue_requested)
        self._queue_list.download_requested.connect(self.download_requested)
        self._queue_list.queue_reordered.connect(self.queue_reordered)
        queue_outer.addWidget(self._queue_list, 1)
        self._queue_section.setMinimumHeight(QUEUE_SECTION_MIN_HEIGHT)
        layout.addWidget(self._queue_section)

        self._download_status = YouTubeDownloadStatus()
        layout.addWidget(self._download_status)

        self._downloads_folder_row = YouTubeDownloadsFolderRow()
        self._downloads_folder_row.browse_clicked.connect(
            self.browse_downloads_folder_requested.emit
        )
        layout.addWidget(self._downloads_folder_row)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(TAB_STYLE)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._wire_song_list()

        youtube_tab = QWidget()
        youtube_layout = QVBoxLayout(youtube_tab)
        youtube_layout.setContentsMargins(0, 0, 0, 0)
        youtube_layout.setSpacing(0)
        youtube_layout.addWidget(self._search_panel, 1)

        self._url_page = self._build_url_page()

        youtube_inner = QTabWidget()
        youtube_inner.setStyleSheet(TAB_STYLE)
        youtube_inner.addTab(youtube_tab, "Results")
        youtube_inner.addTab(self._url_page, "Paste URL")
        youtube_layout_outer = QVBoxLayout()
        youtube_layout_outer.setContentsMargins(0, 0, 0, 0)
        youtube_outer = QWidget()
        youtube_outer.setLayout(youtube_layout_outer)
        youtube_layout_outer.addWidget(youtube_inner, 1)

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
        clear_history_btn.clicked.connect(self.history_clear_requested.emit)
        clear_history_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #aaa; border: none;"
            " font-size: 11px; padding: 2px 6px; }"
            "QPushButton:hover { color: white; background: rgba(255,255,255,25);"
            " border-radius: 3px; }"
        )
        history_header.addWidget(clear_history_btn)
        history_layout.addLayout(history_header)

        self._history_list = PlayHistoryPanel()
        self._history_list.setStyleSheet(SIDEBAR_LIST_STYLE)
        self._history_list.setMinimumHeight(LIST_MIN_HEIGHT)
        self._history_list.play_requested.connect(self.history_play_requested)
        self._history_list.queue_requested.connect(self.history_queue_requested)
        self._history_list.remove_requested.connect(self.history_remove_requested)
        self._history_list.edit_metadata_requested.connect(self.edit_metadata_requested)
        self._history_list.download_requested.connect(self.download_requested)
        history_layout.addWidget(self._history_list, 1)

        self._tabs.addTab(self._song_list, "Local")
        self._tabs.addTab(youtube_outer, "YouTube")
        self._tabs.addTab(history_tab, "History")
        layout.addWidget(self._tabs, 1)

        self._edge_grip = PanelEdgeGrip(self)
        self._edge_grip.dragged.connect(self.resize_dragged)
        self._edge_grip.raise_()

    def _wire_song_list(self) -> None:
        self._song_list.song_selected.connect(self.song_selected)
        self._song_list.play_next_requested.connect(self.play_next_requested)
        self._song_list.play_path_requested.connect(self.play_path_requested)
        self._song_list.sort_changed.connect(self.sort_changed)
        self._song_list.display_mode_changed.connect(self.display_mode_changed)
        self._song_list.display_format_changed.connect(self.display_format_changed)
        self._song_list.rename_requested.connect(self.rename_requested)
        self._song_list.edit_metadata_requested.connect(self.edit_metadata_requested)
        self._song_list.folder_selected.connect(self.folder_selected)
        self._song_list.browse_folder_requested.connect(self.browse_folder_requested)
        self._song_list.folder_entered.connect(self.folder_entered)
        self._song_list.navigate_up_requested.connect(self.navigate_up_requested)
        self._song_list.play_all_requested.connect(self.play_all_requested)
        self._song_list.queue_all_requested.connect(self.queue_all_requested)
        self._song_list.play_all_folder_requested.connect(self.play_all_folder_requested)
        self._song_list.queue_all_folder_requested.connect(self.queue_all_folder_requested)
        self._song_list.back_to_folders_requested.connect(self.back_to_folders_requested)

    def _build_url_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QLabel("Paste YouTube URL")
        header.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        self._url_input = VisibleSpaceLineEdit()
        self._url_input.setPlaceholderText("https://www.youtube.com/watch?v=…")
        self._url_input.setClearButtonEnabled(True)
        self._url_input.setStyleSheet(INPUT_STYLE)
        palette = self._url_input.palette()
        palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#b8b8c8"))
        self._url_input.setPalette(palette)
        layout.addWidget(self._url_input)

        button_row = QHBoxLayout()
        for label, slot in (
            ("Play", self._play_from_url),
            ("Queue", self._queue_from_url),
            ("Download", self._download_from_url),
        ):
            button = QPushButton(label)
            button.setStyleSheet(SEARCH_BTN_STYLE)
            button.clicked.connect(slot)
            button_row.addWidget(button)
        layout.addLayout(button_row)

        self._url_status = QLabel("")
        self._url_status.setStyleSheet(_URL_STATUS_STYLE)
        self._url_status.setWordWrap(True)
        layout.addWidget(self._url_status)
        layout.addStretch(1)
        return page

    def _on_tab_changed(self, index: int) -> None:
        self._youtube_controls.setVisible(index == TAB_YOUTUBE)
        if index == TAB_LOCAL:
            self._search.setPlaceholderText("Search local songs…")
            self._on_search_text_changed(self._search.text())
        elif index == TAB_YOUTUBE:
            self._search.setPlaceholderText("Search YouTube…")
        else:
            self._search.setPlaceholderText("Search history…")

    def _on_search_text_changed(self, text: str) -> None:
        if self._tabs.currentIndex() == TAB_LOCAL:
            self.local_search_changed.emit(text)
            self._song_list.set_search_query(text)

    def _on_search_return_pressed(self) -> None:
        if self._tabs.currentIndex() == TAB_YOUTUBE:
            self._trigger_youtube_search()

    def _trigger_youtube_search(self) -> None:
        query = self._search.text().strip()
        if not query:
            return
        self._search_panel.search_with_query(
            query,
            append_karaoke=self._append_karaoke_checkbox.isChecked(),
        )

    def _sync_append_karaoke(self, checked: bool) -> None:
        self._append_karaoke_checkbox.blockSignals(True)
        self._append_karaoke_checkbox.setChecked(checked)
        self._append_karaoke_checkbox.blockSignals(False)
        self.append_karaoke_changed.emit(checked)

    def set_active_tab(self, tab: str) -> None:
        mapping = {"local": TAB_LOCAL, "youtube": TAB_YOUTUBE, "history": TAB_HISTORY}
        self._tabs.setCurrentIndex(mapping.get(tab, TAB_LOCAL))

    def focus_search(self, *, tab: str = "youtube") -> None:
        self.set_active_tab(tab)
        self._search.setFocus()
        self._search.selectAll()

    def configure_search(self, *, backend_name: str, api_key: str | None) -> None:
        self._search_panel.configure_search(backend_name=backend_name, api_key=api_key)

    def set_append_karaoke(self, checked: bool) -> None:
        self._append_karaoke_checkbox.setChecked(checked)
        self._search_panel.set_append_karaoke(checked)

    def set_downloads_folder(self, path: Path) -> None:
        self._downloads_folder_row.set_folder(path)

    def set_folder(self, folder: Path | None) -> None:
        self._song_list.set_folder(folder)
        if folder is None:
            self._folder_btn.setText("Library")
            self._folder_btn.setToolTip("Switch folder")
        else:
            self._folder_btn.setText(folder.name)
            try:
                self._folder_btn.setToolTip(str(folder.resolve()))
            except OSError:
                self._folder_btn.setToolTip(str(folder))

    def set_recent_folders(self, folders: list[Path], *, pinned: list[Path] | None = None) -> None:
        self._song_list.set_recent_folders(folders, pinned=pinned)

    def set_queue_state(self, *, current: QueueItem | None, queued: list[QueueItem]) -> None:
        has_queue = current is not None or bool(queued)
        self._queue_section.setVisible(has_queue)
        if has_queue:
            count = (1 if current else 0) + len(queued)
            self._queue_title.setText(f"Queue ({count})")
        self._queue_list.set_queue(current=current, queued=queued)

    def set_history(
        self,
        entries: list[PlayHistoryEntry],
        *,
        current_local: Path | None = None,
        current_video_id: str | None = None,
    ) -> None:
        self._history_list.set_history(
            entries,
            current_local=current_local,
            current_video_id=current_video_id,
        )

    def set_library_root(self, root: Path | None) -> None:
        self._history_list.set_library_root(root)
        self._song_list.set_library_root(root)

    def set_display_format(self, fmt: DisplayFormat) -> None:
        self._song_list.set_display_format(fmt)
        self._queue_list.set_display_resolver(self._song_list.display_resolver())
        self._history_list.set_display_resolver(self._song_list.display_resolver())

    def set_display_mode(self, mode: str) -> None:
        self._song_list.set_display_mode(mode)

    def display_sort_key(self, path: Path) -> str:
        return self._song_list.display_sort_key(path)

    def local_search_text(self) -> str:
        return self._search.text().strip()

    def set_sort_strategy(self, strategy) -> None:
        self._song_list.set_sort_strategy(strategy)

    def set_songs(self, *args, **kwargs) -> None:
        self._song_list.set_songs(*args, **kwargs)

    def set_current_index(self, index: int | None) -> None:
        self._song_list.set_current_index(index)

    def clear_current_index(self) -> None:
        self._song_list.clear_current_index()

    def playing_index(self) -> int | None:
        return self._song_list.playing_index()

    def refresh_display_labels(self) -> None:
        self._song_list.refresh_display_labels()
        self._queue_list.set_display_resolver(self._song_list.display_resolver())
        self._history_list.set_display_resolver(self._song_list.display_resolver())

    def show_downloading(self, title: str, *, percent: float = 0.0, status: str = "Downloading…") -> None:
        self._download_status.show_downloading(title, percent=percent, status=status)

    def update_download_progress(self, title: str, percent: float, status: str) -> None:
        self._download_status.update_progress(title, percent, status)

    def show_download_success(self, title: str, *, message: str = "Download complete") -> None:
        self._download_status.show_success(title, message=message)

    def show_download_error(self, title: str, message: str) -> None:
        self._download_status.show_error(title, message)

    def reset_download_status(self) -> None:
        self._download_status.reset()

    def clear_messages(self) -> None:
        self.reset_download_status()
        self._search_panel.clear_status()
        self._url_status.clear()

    def raise_edge_grip(self) -> None:
        self._edge_grip.raise_()
        self._edge_grip.setCursor(Qt.CursorShape.SizeHorCursor)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._edge_grip.setGeometry(
            self.width() - EDGE_GRIP_WIDTH,
            0,
            EDGE_GRIP_WIDTH,
            self.height(),
        )

    def _video_from_url_field(self) -> YouTubeVideo | None:
        video_id = extract_video_id(self._url_input.text())
        if video_id is None:
            self._url_status.setText("Enter a valid YouTube URL or video ID.")
            self._url_status.setStyleSheet(_URL_ERROR_STYLE)
            return None
        self._url_status.clear()
        return YouTubeVideo(
            video_id=video_id,
            title=self._url_input.text().strip() or video_id,
            channel="YouTube",
        )

    def _play_from_url(self) -> None:
        video = self._video_from_url_field()
        if video is not None:
            self.youtube_play_requested.emit(video)

    def _queue_from_url(self) -> None:
        video = self._video_from_url_field()
        if video is not None:
            self.youtube_queue_requested.emit(video)

    def _download_from_url(self) -> None:
        video = self._video_from_url_field()
        if video is not None:
            self.download_requested.emit(video)
