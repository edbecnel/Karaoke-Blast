"""YouTube play history sidebar list."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QMenu

from karaoke_blast.ui.context_menu_style import CONTEXT_MENU_STYLE

from karaoke_blast.models.youtube_video import YouTubeVideo
from karaoke_blast.ui.youtube_queue_widget import format_duration

_ROLE_VIDEO = Qt.ItemDataRole.UserRole


class YouTubeHistoryPanel(QListWidget):
    """List of previously played YouTube videos with play/queue actions."""

    play_requested = pyqtSignal(object)
    queue_requested = pyqtSignal(object)
    remove_requested = pyqtSignal(str)
    download_requested = pyqtSignal(object)
    clear_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_video_id: str | None = None
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def set_history(
        self,
        videos: list[YouTubeVideo],
        *,
        current: YouTubeVideo | None = None,
    ) -> None:
        self._current_video_id = current.video_id if current is not None else None
        self.clear()
        for video in videos:
            is_current = video.video_id == self._current_video_id
            duration = format_duration(video.duration_seconds)
            suffix = f" ({duration})" if duration else ""
            prefix = "▶ " if is_current else ""
            item = QListWidgetItem(f"{prefix}{video.title}{suffix}\n{video.channel}")
            item.setData(_ROLE_VIDEO, video)
            item.setToolTip(f"{video.title}\n{video.channel}\n{video.watch_url}")
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            if is_current:
                item.setForeground(QColor("#7ee787"))
            self.addItem(item)

    def _video_from_item(self, item: QListWidgetItem | None) -> YouTubeVideo | None:
        if item is None:
            return None
        value = item.data(_ROLE_VIDEO)
        return value if isinstance(value, YouTubeVideo) else None

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        video = self._video_from_item(item)
        if video is not None:
            self.play_requested.emit(video)

    def _show_context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        video = self._video_from_item(item)
        if video is None:
            return

        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

        play_now = QAction("Play Now", self)
        play_now.triggered.connect(lambda: self.play_requested.emit(video))
        menu.addAction(play_now)

        play_next = QAction("Play Next", self)
        play_next.triggered.connect(lambda: self.queue_requested.emit(video))
        menu.addAction(play_next)

        remove = QAction("Remove from History", self)
        remove.triggered.connect(lambda: self.remove_requested.emit(video.video_id))
        menu.addAction(remove)

        download = QAction("Download", self)
        download.triggered.connect(lambda: self.download_requested.emit(video))
        menu.addAction(download)

        menu.exec(self.mapToGlobal(pos))
