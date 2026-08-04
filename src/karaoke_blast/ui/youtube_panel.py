"""Tabbed YouTube sidebar with search, paste-URL, and history."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.models.youtube_video import YouTubeVideo
from karaoke_blast.ui.panel_splitter import EDGE_GRIP_WIDTH
from karaoke_blast.ui.youtube_download_status import YouTubeDownloadStatus
from karaoke_blast.ui.youtube_history_panel import YouTubeHistoryPanel
from karaoke_blast.ui.youtube_queue_widget import QUEUE_PANEL_LIST_STYLE, YouTubeQueueWidget
from karaoke_blast.ui.youtube_search_panel import (
    LIST_STYLE,
    PANEL_MAX_WIDTH,
    PANEL_MIN_WIDTH,
    RESULTS_MIN_HEIGHT,
    YouTubeSearchPanel,
)
from karaoke_blast.utils.youtube_url import extract_video_id

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

QUEUE_SECTION_MIN_HEIGHT = 72
TAB_STYLE = (
    "QTabWidget::pane { border: none; background: transparent; }"
    "QTabBar::tab {"
    " background: #2d2d42; color: #b8b8c8; padding: 8px 14px;"
    " border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px;"
    "}"
    "QTabBar::tab:selected { background: #e94560; color: white; }"
)

_DISMISS_BTN_STYLE = (
    "QPushButton { background: transparent; color: #aaa; border: none;"
    " font-size: 16px; border-radius: 4px; }"
    "QPushButton:hover { background: rgba(255,255,255,30); color: white; }"
)
_URL_STATUS_STYLE = "color: #aaa; font-size: 11px;"
_URL_ERROR_STYLE = "color: #ff6b81; font-size: 11px;"


class YouTubePanel(QWidget):
    """Left sidebar wrapper for YouTube search, URL entry, and history."""

    play_requested = pyqtSignal(object)
    queue_requested = pyqtSignal(object)
    remove_from_queue_requested = pyqtSignal(str)
    clear_queue_requested = pyqtSignal()
    close_requested = pyqtSignal()
    resize_dragged = pyqtSignal(int)
    search_backend_fallback = pyqtSignal(str)
    append_karaoke_changed = pyqtSignal(bool)
    history_remove_requested = pyqtSignal(str)
    history_clear_requested = pyqtSignal()
    download_requested = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(PANEL_MIN_WIDTH)
        self.setMaximumWidth(PANEL_MAX_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._queue_section = QWidget()
        self._queue_section.hide()
        queue_outer = QVBoxLayout(self._queue_section)
        queue_outer.setContentsMargins(12, 8, EDGE_GRIP_WIDTH + 8, 0)
        queue_outer.setSpacing(4)

        queue_header = QHBoxLayout()
        queue_title = QLabel("Queue")
        queue_title.setStyleSheet("color: #e94560; font-size: 12px; font-weight: bold;")
        queue_header.addWidget(queue_title)
        queue_header.addStretch()
        clear_queue_btn = QPushButton("Clear")
        clear_queue_btn.setToolTip("Clear now playing and all queued videos")
        clear_queue_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #aaa; border: none;"
            " font-size: 11px; padding: 2px 6px; }"
            "QPushButton:hover { color: white; background: rgba(255,255,255,25);"
            " border-radius: 3px; }"
        )
        clear_queue_btn.clicked.connect(self.clear_queue_requested.emit)
        queue_header.addWidget(clear_queue_btn)
        queue_outer.addLayout(queue_header)

        self._queue_list = YouTubeQueueWidget()
        self._queue_list.setStyleSheet(QUEUE_PANEL_LIST_STYLE)
        self._queue_list.play_requested.connect(self.play_requested)
        self._queue_list.queue_requested.connect(self.queue_requested)
        self._queue_list.remove_requested.connect(self.remove_from_queue_requested)
        self._queue_list.download_requested.connect(self.download_requested)
        queue_outer.addWidget(self._queue_list, 1)
        self._queue_section.setMinimumHeight(QUEUE_SECTION_MIN_HEIGHT)
        layout.addWidget(self._queue_section)

        self._download_status = YouTubeDownloadStatus()
        layout.addWidget(self._download_status)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(TAB_STYLE)

        self._search_panel = YouTubeSearchPanel()
        self._search_panel.play_requested.connect(self.play_requested)
        self._search_panel.queue_requested.connect(self.queue_requested)
        self._search_panel.close_requested.connect(self.close_requested)
        self._search_panel.resize_dragged.connect(self.resize_dragged)
        self._search_panel.search_backend_fallback.connect(self.search_backend_fallback)
        self._search_panel.append_karaoke_changed.connect(self.append_karaoke_changed)
        self._search_panel.download_requested.connect(self.download_requested)

        self._url_page = QWidget()
        url_layout = QVBoxLayout(self._url_page)
        url_layout.setContentsMargins(12, 12, EDGE_GRIP_WIDTH + 8, 12)
        url_layout.setSpacing(8)

        url_header = QLabel("Paste YouTube URL")
        url_header.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        url_layout.addWidget(url_header)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://www.youtube.com/watch?v=…")
        self._url_input.setClearButtonEnabled(True)
        self._url_input.setStyleSheet(INPUT_STYLE)
        palette = self._url_input.palette()
        palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#b8b8c8"))
        self._url_input.setPalette(palette)
        url_layout.addWidget(self._url_input)

        button_row = QHBoxLayout()
        self._url_play_btn = QPushButton("Play")
        self._url_queue_btn = QPushButton("Queue")
        self._url_download_btn = QPushButton("Download")
        for button in (self._url_play_btn, self._url_queue_btn, self._url_download_btn):
            button.setStyleSheet(
                "QPushButton { background-color: #e94560; color: white; border: none;"
                " border-radius: 4px; padding: 8px 12px; font-size: 13px; font-weight: bold; }"
                "QPushButton:hover { background-color: #ff6b81; }"
            )
        self._url_play_btn.clicked.connect(self._play_from_url)
        self._url_queue_btn.clicked.connect(self._queue_from_url)
        self._url_download_btn.clicked.connect(self._download_from_url)
        button_row.addWidget(self._url_play_btn)
        button_row.addWidget(self._url_queue_btn)
        button_row.addWidget(self._url_download_btn)
        url_layout.addLayout(button_row)

        url_status_row = QHBoxLayout()
        url_status_row.setSpacing(4)
        self._url_status = QLabel("")
        self._url_status.setStyleSheet(_URL_STATUS_STYLE)
        self._url_status.setWordWrap(True)
        url_status_row.addWidget(self._url_status, 1)

        self._url_status_close_btn = QPushButton("×")
        self._url_status_close_btn.setToolTip("Dismiss")
        self._url_status_close_btn.setFixedSize(24, 24)
        self._url_status_close_btn.setStyleSheet(_DISMISS_BTN_STYLE)
        self._url_status_close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._url_status_close_btn.clicked.connect(self._clear_url_status)
        self._url_status_close_btn.hide()
        url_status_row.addWidget(self._url_status_close_btn)
        url_layout.addLayout(url_status_row)
        url_layout.addStretch(1)

        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        history_layout.setContentsMargins(12, 12, EDGE_GRIP_WIDTH + 8, 12)
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
        clear_history_btn.clicked.connect(self.history_clear_requested.emit)
        history_header.addWidget(clear_history_btn)
        history_layout.addLayout(history_header)

        self._history_list = YouTubeHistoryPanel()
        self._history_list.setStyleSheet(LIST_STYLE)
        self._history_list.setMinimumHeight(RESULTS_MIN_HEIGHT)
        self._history_list.play_requested.connect(self.play_requested)
        self._history_list.queue_requested.connect(self.queue_requested)
        self._history_list.remove_requested.connect(self.history_remove_requested)
        self._history_list.download_requested.connect(self.download_requested)
        history_layout.addWidget(self._history_list, 1)

        self._tabs.addTab(self._search_panel, "Search")
        self._tabs.addTab(self._url_page, "Paste URL")
        self._tabs.addTab(history_tab, "History")
        layout.addWidget(self._tabs, 1)

    def configure_search(self, *, backend_name: str, api_key: str | None) -> None:
        self._search_panel.configure_search(backend_name=backend_name, api_key=api_key)

    def set_append_karaoke(self, checked: bool) -> None:
        self._search_panel.set_append_karaoke(checked)

    def focus_search(self) -> None:
        self._tabs.setCurrentIndex(0)
        self._search_panel.focus_search()

    def focus_url(self) -> None:
        self._tabs.setCurrentIndex(1)
        self._url_input.setFocus()

    def set_queue_state(
        self,
        *,
        current: YouTubeVideo | None,
        queued: list[YouTubeVideo],
    ) -> None:
        has_queue = current is not None or bool(queued)
        self._queue_section.setVisible(has_queue)
        self._queue_list.set_queue(current=current, queued=queued)

    def set_history(
        self,
        videos: list[YouTubeVideo],
        *,
        current: YouTubeVideo | None = None,
    ) -> None:
        self._history_list.set_history(videos, current=current)

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
        """Hide download status, search errors, and URL validation messages."""
        self.reset_download_status()
        self._search_panel.clear_status()
        self._clear_url_status()

    def raise_edge_grip(self) -> None:
        self._search_panel.raise_edge_grip()

    def _clear_url_status(self) -> None:
        self._url_status.clear()
        self._url_status.setStyleSheet(_URL_STATUS_STYLE)
        self._url_status_close_btn.hide()

    def _show_url_error(self, message: str) -> None:
        self._url_status.setText(message)
        self._url_status.setStyleSheet(_URL_ERROR_STYLE)
        self._url_status_close_btn.show()

    def _video_from_url_field(self) -> YouTubeVideo | None:
        video_id = extract_video_id(self._url_input.text())
        if video_id is None:
            self._show_url_error("Enter a valid YouTube URL or video ID.")
            return None
        self._clear_url_status()
        return YouTubeVideo(
            video_id=video_id,
            title=self._url_input.text().strip() or video_id,
            channel="YouTube",
        )

    def _play_from_url(self) -> None:
        video = self._video_from_url_field()
        if video is not None:
            self.play_requested.emit(video)

    def _queue_from_url(self) -> None:
        video = self._video_from_url_field()
        if video is not None:
            self.queue_requested.emit(video)

    def _download_from_url(self) -> None:
        video = self._video_from_url_field()
        if video is not None:
            self.download_requested.emit(video)
