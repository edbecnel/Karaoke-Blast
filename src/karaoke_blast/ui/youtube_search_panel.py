"""YouTube search and queue sidebar."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QPalette
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.models.youtube_video import YouTubeVideo
from karaoke_blast.services.youtube_search import (
    MAX_TOTAL_RESULTS,
    YouTubeSearchPage,
    start_search,
)
from karaoke_blast.ui.panel_splitter import EDGE_GRIP_WIDTH, PanelEdgeGrip
from karaoke_blast.ui.youtube_queue_widget import format_duration
from karaoke_blast.utils.youtube_query import build_karaoke_query

PANEL_MIN_WIDTH = 200
PANEL_MAX_WIDTH = 700
RESULTS_MIN_HEIGHT = 120

INPUT_STYLE = """
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

_ROLE_VIDEO = Qt.ItemDataRole.UserRole + 1

_DISMISS_BTN_STYLE = (
    "QPushButton { background: transparent; color: #aaa; border: none;"
    " font-size: 16px; border-radius: 4px; }"
    "QPushButton:hover { background: rgba(255,255,255,30); color: white; }"
)

_STATUS_STYLE = "color: #aaa; font-size: 11px;"
_ERROR_STYLE = "color: #ff6b81; font-size: 11px;"


class YouTubeSearchPanel(QWidget):
    """Left sidebar for searching YouTube and managing the queue."""

    play_requested = pyqtSignal(object)
    queue_requested = pyqtSignal(object)
    download_requested = pyqtSignal(object)
    close_requested = pyqtSignal()
    resize_dragged = pyqtSignal(int)
    search_backend_fallback = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(PANEL_MIN_WIDTH)
        self.setMaximumWidth(PANEL_MAX_WIDTH)
        self.setStyleSheet("background-color: rgba(15, 15, 25, 230);")

        self._backend_name = "yt-dlp"
        self._api_key: str | None = None
        self._search_thread = None
        self._active_query: str | None = None
        self._api_page_token: str | None = None
        self._yt_dlp_skip = 0
        self._has_more = False
        self._append_next = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, EDGE_GRIP_WIDTH + 8, 12)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header = QLabel("YouTube")
        header.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        header_row.addWidget(header)
        header_row.addStretch()

        close_btn = QPushButton("×")
        close_btn.setToolTip("Hide YouTube panel (L)")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #aaa; border: none;"
            " font-size: 20px; border-radius: 4px; }"
            "QPushButton:hover { background: rgba(255,255,255,30); color: white; }"
        )
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close_requested.emit)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        self._song_input = self._make_input("Song")
        layout.addWidget(self._song_input)

        self._artist_input = self._make_input("Artist / band (optional)")
        layout.addWidget(self._artist_input)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self._search_btn = QPushButton("Search")
        self._search_btn.setStyleSheet(SEARCH_BTN_STYLE)
        self._search_btn.clicked.connect(self._start_search)
        search_row.addWidget(self._search_btn)

        self._search_more_btn = QPushButton("Search more")
        self._search_more_btn.setStyleSheet(SEARCH_MORE_BTN_STYLE)
        self._search_more_btn.setEnabled(False)
        self._search_more_btn.clicked.connect(self._start_search_more)
        search_row.addWidget(self._search_more_btn)
        layout.addLayout(search_row)

        status_row = QHBoxLayout()
        status_row.setSpacing(4)
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(_STATUS_STYLE)
        self._status_label.setWordWrap(True)
        status_row.addWidget(self._status_label, 1)

        self._status_close_btn = QPushButton("×")
        self._status_close_btn.setToolTip("Dismiss")
        self._status_close_btn.setFixedSize(24, 24)
        self._status_close_btn.setStyleSheet(_DISMISS_BTN_STYLE)
        self._status_close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._status_close_btn.clicked.connect(self.clear_status)
        self._status_close_btn.hide()
        status_row.addWidget(self._status_close_btn)
        layout.addLayout(status_row)

        self._results_list = QListWidget()
        self._results_list.setStyleSheet(LIST_STYLE)
        self._results_list.setMinimumHeight(RESULTS_MIN_HEIGHT)
        self._results_list.itemDoubleClicked.connect(self._on_result_double_clicked)
        self._results_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._results_list.customContextMenuRequested.connect(self._show_results_context_menu)
        layout.addWidget(self._results_list, 1)

        self._song_input.returnPressed.connect(self._start_search)
        self._artist_input.returnPressed.connect(self._start_search)

        self._edge_grip = PanelEdgeGrip(self)
        self._edge_grip.dragged.connect(self.resize_dragged.emit)
        self._edge_grip.raise_()

    def _make_input(self, placeholder: str) -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setClearButtonEnabled(True)
        field.setStyleSheet(INPUT_STYLE)
        palette = field.palette()
        palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#b8b8c8"))
        field.setPalette(palette)
        return field

    def configure_search(self, *, backend_name: str, api_key: str | None) -> None:
        self._backend_name = backend_name
        self._api_key = api_key

    def focus_search(self) -> None:
        self._song_input.setFocus()
        self._song_input.selectAll()

    def _existing_video_ids(self) -> set[str]:
        ids: set[str] = set()
        for index in range(self._results_list.count()):
            item = self._results_list.item(index)
            video = self._video_at(item)
            if video is not None:
                ids.add(video.video_id)
        return ids

    def _add_result_item(self, video: YouTubeVideo) -> None:
        duration = format_duration(video.duration_seconds)
        suffix = f" ({duration})" if duration else ""
        item = QListWidgetItem(f"{video.title}{suffix}\n{video.channel}")
        item.setData(_ROLE_VIDEO, video)
        item.setToolTip(f"{video.title}\n{video.channel}\n{video.watch_url}")
        self._results_list.addItem(item)

    def set_results(self, results: list[YouTubeVideo]) -> None:
        self._results_list.clear()
        for video in results:
            self._add_result_item(video)
        self._update_status_label()

    def append_results(self, results: list[YouTubeVideo]) -> int:
        existing = self._existing_video_ids()
        added = 0
        for video in results:
            if video.video_id in existing:
                continue
            self._add_result_item(video)
            existing.add(video.video_id)
            added += 1
        self._update_status_label()
        return added

    def _update_status_label(self) -> None:
        count = self._results_list.count()
        self._status_label.setStyleSheet(_STATUS_STYLE)
        self._status_close_btn.hide()
        if count == 0:
            self._status_label.setText("No results found.")
            return
        if count >= MAX_TOTAL_RESULTS and not self._has_more:
            self._status_label.setText(
                f"{count} results — refine your search for more results."
            )
        else:
            self._status_label.setText(f"{count} result(s)")

    def _update_search_more_button(self) -> None:
        enabled = (
            self._active_query is not None
            and self._has_more
            and self._results_list.count() < MAX_TOTAL_RESULTS
        )
        self._search_more_btn.setEnabled(enabled)

    def clear_status(self) -> None:
        self._status_label.clear()
        self._status_label.setStyleSheet(_STATUS_STYLE)
        self._status_close_btn.hide()

    def show_search_error(self, message: str) -> None:
        self._status_label.setText(message)
        self._status_label.setStyleSheet(_ERROR_STYLE)
        self._status_close_btn.show()

    def _show_input_error(self, message: str) -> None:
        self._status_label.setText(message)
        self._status_label.setStyleSheet(_ERROR_STYLE)
        self._status_close_btn.show()

    def _resolve_backend(self) -> tuple[str, str | None]:
        backend_name = self._backend_name
        api_key = self._api_key
        if backend_name == "api" and not api_key:
            self.search_backend_fallback.emit(
                "YouTube API key is not configured. Using yt-dlp search instead."
            )
            backend_name = "yt-dlp"
        return backend_name, api_key

    def _start_search(self) -> None:
        query = build_karaoke_query(self._song_input.text(), self._artist_input.text())
        if not query:
            self._show_input_error("Enter a song name to search.")
            return
        if self._search_thread is not None and self._search_thread.isRunning():
            return

        self._active_query = query
        self._api_page_token = None
        self._yt_dlp_skip = 0
        self._has_more = False
        self._append_next = False

        backend_name, api_key = self._resolve_backend()
        self._set_search_in_progress(True)
        self.clear_status()
        self._status_label.setText("Searching…")
        self._search_thread = start_search(
            query=query,
            backend_name=backend_name,
            api_key=api_key,
            on_finished=self._on_search_finished,
            on_failed=self._on_search_failed,
            parent=self,
        )

    def _start_search_more(self) -> None:
        if not self._active_query or not self._has_more:
            return
        if self._search_thread is not None and self._search_thread.isRunning():
            return

        self._append_next = True
        backend_name, api_key = self._resolve_backend()
        page_token = self._api_page_token if backend_name == "api" else None
        skip = self._yt_dlp_skip if backend_name != "api" else self._results_list.count()

        self._set_search_in_progress(True)
        self.clear_status()
        self._status_label.setText("Searching…")
        self._search_thread = start_search(
            query=self._active_query,
            backend_name=backend_name,
            api_key=api_key,
            on_finished=self._on_search_finished,
            on_failed=self._on_search_failed,
            parent=self,
            page_token=page_token,
            skip=skip,
        )

    def _set_search_in_progress(self, in_progress: bool) -> None:
        self._search_btn.setEnabled(not in_progress)
        if in_progress:
            self._search_more_btn.setEnabled(False)
        else:
            self._update_search_more_button()

    def _on_search_finished(self, page: object) -> None:
        self._set_search_in_progress(False)
        self._search_thread = None

        if not isinstance(page, YouTubeSearchPage):
            return

        if self._append_next:
            self.append_results(page.videos)
            self._append_next = False
        else:
            self.set_results(page.videos)

        self._api_page_token = page.next_page_token
        self._yt_dlp_skip = self._results_list.count()
        self._has_more = page.has_more
        self._update_search_more_button()
        self._update_status_label()

    def _on_search_failed(self, message: str) -> None:
        self._set_search_in_progress(False)
        self._search_thread = None
        self._append_next = False
        self.show_search_error(message)

    def _video_at(self, item: QListWidgetItem | None) -> YouTubeVideo | None:
        if item is None:
            return None
        value = item.data(_ROLE_VIDEO)
        return value if isinstance(value, YouTubeVideo) else None

    def _on_result_double_clicked(self, item: QListWidgetItem) -> None:
        video = self._video_at(item)
        if video is not None:
            self.play_requested.emit(video)

    def _show_results_context_menu(self, pos) -> None:
        item = self._results_list.itemAt(pos)
        video = self._video_at(item)
        if video is None:
            return
        menu = QMenu(self)
        play_action = QAction("Play Now", self)
        play_action.triggered.connect(lambda: self.play_requested.emit(video))
        menu.addAction(play_action)
        queue_action = QAction("Play Next", self)
        queue_action.triggered.connect(lambda: self.queue_requested.emit(video))
        menu.addAction(queue_action)
        download_action = QAction("Download", self)
        download_action.triggered.connect(lambda: self.download_requested.emit(video))
        menu.addAction(download_action)
        menu.exec(self._results_list.mapToGlobal(pos))

    def showEvent(self, event) -> None:
        super().showEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_edge_grip()

    def raise_edge_grip(self) -> None:
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
