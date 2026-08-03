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
from karaoke_blast.services.youtube_search import start_search
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

_ROLE_VIDEO = Qt.ItemDataRole.UserRole + 1


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

        self._search_btn = QPushButton("Search")
        self._search_btn.setStyleSheet(
            "QPushButton { background-color: #e94560; color: white; border: none;"
            " border-radius: 4px; padding: 8px 12px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background-color: #ff6b81; }"
            "QPushButton:disabled { background-color: #5a5a72; color: #ccc; }"
        )
        self._search_btn.clicked.connect(self._start_search)
        layout.addWidget(self._search_btn)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #aaa; font-size: 11px;")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

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

    def set_results(self, results: list[YouTubeVideo]) -> None:
        self._results_list.clear()
        for video in results:
            duration = format_duration(video.duration_seconds)
            suffix = f" ({duration})" if duration else ""
            item = QListWidgetItem(f"{video.title}{suffix}\n{video.channel}")
            item.setData(_ROLE_VIDEO, video)
            item.setToolTip(f"{video.title}\n{video.channel}\n{video.watch_url}")
            self._results_list.addItem(item)
        if results:
            self._status_label.setText(f"{len(results)} result(s)")
        else:
            self._status_label.setText("No results found.")

    def show_search_error(self, message: str) -> None:
        self._status_label.setText(message)

    def _start_search(self) -> None:
        query = build_karaoke_query(self._song_input.text(), self._artist_input.text())
        if not query:
            self._status_label.setText("Enter a song name to search.")
            return
        if self._search_thread is not None and self._search_thread.isRunning():
            return

        backend_name = self._backend_name
        api_key = self._api_key
        if backend_name == "api" and not api_key:
            self.search_backend_fallback.emit(
                "YouTube API key is not configured. Using yt-dlp search instead."
            )
            backend_name = "yt-dlp"

        self._search_btn.setEnabled(False)
        self._status_label.setText("Searching…")
        self._search_thread = start_search(
            query=query,
            backend_name=backend_name,
            api_key=api_key,
            on_finished=self._on_search_finished,
            on_failed=self._on_search_failed,
            parent=self,
        )

    def _on_search_finished(self, results: list) -> None:
        self._search_btn.setEnabled(True)
        self._search_thread = None
        self.set_results(results)

    def _on_search_failed(self, message: str) -> None:
        self._search_btn.setEnabled(True)
        self._search_thread = None
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
