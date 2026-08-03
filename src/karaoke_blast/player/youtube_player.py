"""YouTube playback controller."""

from PyQt6.QtCore import QObject, pyqtSignal

from karaoke_blast.models.youtube_video import YouTubeVideo
from karaoke_blast.player.youtube_widget import YouTubeWidget


class YouTubePlayer(QObject):
    """Thin wrapper around the embedded YouTube widget."""

    end_reached = pyqtSignal()
    playback_error = pyqtSignal(str)

    def __init__(self, widget: YouTubeWidget, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._widget = widget
        self._current: YouTubeVideo | None = None
        self._widget.playback_ended.connect(self._on_playback_ended)
        self._widget.playback_error.connect(self.playback_error)

    def play(self, video: YouTubeVideo, *, volume: int = 80, muted: bool = False) -> None:
        self._current = video
        self._widget.load_video(video.video_id, volume=volume, muted=muted)

    def stop(self) -> None:
        self._current = None
        self._widget.clear()

    def set_volume(self, volume: int) -> None:
        self._widget.set_volume(volume)

    def set_mute(self, muted: bool) -> None:
        self._widget.set_mute(muted)

    def current(self) -> YouTubeVideo | None:
        return self._current

    def _on_playback_ended(self) -> None:
        self.end_reached.emit()
