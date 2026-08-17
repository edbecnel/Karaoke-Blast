"""List widget for the YouTube play queue."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QMenu

from karaoke_blast.models.youtube_video import YouTubeVideo
from karaoke_blast.ui.context_menu_style import CONTEXT_MENU_STYLE, copy_text_to_clipboard
from karaoke_blast.ui.list_style import QUEUE_LIST_STYLE

_ROLE_VIDEO = Qt.ItemDataRole.UserRole

QUEUE_PANEL_LIST_STYLE = QUEUE_LIST_STYLE


def format_duration(seconds: int | None) -> str:
    if seconds is None or seconds < 0:
        return ""
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


class YouTubeQueueWidget(QListWidget):
    """Shows the currently playing YouTube video and queued items."""

    play_requested = pyqtSignal(object)
    queue_requested = pyqtSignal(object)
    remove_requested = pyqtSignal(str)
    download_requested = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_video_id: str | None = None
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def set_queue(
        self,
        *,
        current: YouTubeVideo | None,
        queued: list[YouTubeVideo],
    ) -> None:
        self._current_video_id = current.video_id if current is not None else None
        self.clear()
        if current is not None:
            self._add_row(current, label_prefix="▶ ", color="#7ee787")
        for position, video in enumerate(queued, start=1):
            self._add_row(
                video,
                label_prefix=f"⏭ {position} · ",
                color="#ffb3c1",
            )

    def _add_row(
        self,
        video: YouTubeVideo,
        *,
        label_prefix: str,
        color: str,
    ) -> None:
        duration = format_duration(video.duration_seconds)
        suffix = f" ({duration})" if duration else ""
        item = QListWidgetItem(f"{label_prefix}{video.title}{suffix}")
        item.setData(_ROLE_VIDEO, video)
        item.setToolTip(f"{video.title}\n{video.channel}\n{video.watch_url}")
        item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        item.setForeground(QColor(color))
        self.addItem(item)

    def video_at(self, row: int) -> YouTubeVideo | None:
        item = self.item(row)
        return self._video_from_item(item)

    def _video_from_item(self, item: QListWidgetItem | None) -> YouTubeVideo | None:
        if item is None:
            return None
        value = item.data(_ROLE_VIDEO)
        return value if isinstance(value, YouTubeVideo) else None

    def video_id_at(self, row: int) -> str | None:
        video = self.video_at(row)
        return video.video_id if video is not None else None

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

        if video.video_id != self._current_video_id:
            play_next = QAction("Play Next", self)
            play_next.triggered.connect(lambda: self.queue_requested.emit(video))
            menu.addAction(play_next)

            remove = QAction("Remove from Queue", self)
            remove.triggered.connect(lambda: self.remove_requested.emit(video.video_id))
            menu.addAction(remove)
        else:
            remove = QAction("Remove from Queue", self)
            remove.triggered.connect(lambda: self.remove_requested.emit(video.video_id))
            menu.addAction(remove)

        download = QAction("Download", self)
        download.triggered.connect(lambda: self.download_requested.emit(video))
        menu.addAction(download)

        copy_url = QAction("Copy URL", self)
        copy_url.triggered.connect(lambda: copy_text_to_clipboard(video.watch_url))
        menu.addAction(copy_url)

        menu.exec(self.mapToGlobal(pos))
