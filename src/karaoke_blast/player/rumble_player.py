"""Rumble playback controller."""

from PyQt6.QtCore import QObject, pyqtSignal

from karaoke_blast.models.rumble_video import RumbleVideo
from karaoke_blast.player.rumble_widget import RumbleWidget


class RumblePlayer(QObject):
    playback_error = pyqtSignal(str)

    def __init__(self, widget: RumbleWidget, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._widget = widget
        self._current: RumbleVideo | None = None
        self._widget.playback_error.connect(self.playback_error)

    def play(self, video: RumbleVideo) -> None:
        self._current = video
        if video.embed_id:
            self._widget.load_embed(video.embed_id, page_referer=video.page_url)
        else:
            self._widget.load_watch_page(video.page_url)

    def stop(self) -> None:
        self._current = None
        self._widget.clear()

    def activate_playback(self) -> None:
        self._widget.activate_playback()

    def pause_playback(self) -> None:
        self._widget.pause_playback()

    def toggle_playback(self) -> None:
        self._widget.toggle_playback()

    def current(self) -> RumbleVideo | None:
        return self._current
