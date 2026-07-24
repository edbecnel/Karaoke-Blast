"""VLC media player wrapper."""

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from karaoke_blast.player.video_widget import VideoWidget

logger = logging.getLogger(__name__)

SEEK_STEP_MS = 10_000


class VlcPlayer(QObject):
    """Thin wrapper around python-vlc with Qt signals."""

    end_reached = pyqtSignal()
    playback_error = pyqtSignal(str)

    def __init__(self, video_widget: VideoWidget, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._widget = video_widget

        try:
            import vlc
        except OSError as exc:
            raise RuntimeError(
                "Could not load VLC libraries. Install VLC from https://www.videolan.org/vlc/ "
                "and ensure its architecture matches your Python installation."
            ) from exc

        self._vlc = vlc
        vlc_args: list[str] = ["--no-video-title-show"]
        if sys.platform == "darwin":
            vlc_args.append("--vout=macosx")
        elif sys.platform.startswith("linux"):
            vlc_args.append("--no-xlib")

        try:
            self._instance = vlc.Instance(*vlc_args)
        except Exception as exc:
            raise RuntimeError(
                "Could not initialize VLC. Install VLC from https://www.videolan.org/vlc/"
            ) from exc

        self._player = self._instance.media_player_new()
        self._widget.set_player(self._player)
        self._widget.bind_requested.connect(self.bind_output)

        event_manager = self._player.event_manager()
        event_manager.event_attach(
            vlc.EventType.MediaPlayerEndReached,
            self._on_end_reached,
        )
        event_manager.event_attach(
            vlc.EventType.MediaPlayerEncounteredError,
            self._on_error,
        )

    def bind_output(self) -> None:
        """Re-attach VLC to the video widget (required after show/resize on macOS)."""
        self._widget.bind_player(self._player)

    def play(self, path: Path) -> None:
        media = self._instance.media_new(str(path))
        self._player.set_media(media)
        self.bind_output()
        result = self._player.play()
        if result == -1:
            self.playback_error.emit(f"Failed to play: {path.name}")
            logger.error("VLC failed to start playback for %s", path)
            return
        if sys.platform in ("darwin", "win32"):
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(0, self.bind_output)
            QTimer.singleShot(100, self.bind_output)

    def resume(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.set_pause(1)

    def toggle_pause(self) -> None:
        self._player.pause()

    def is_playing(self) -> bool:
        return bool(self._player.is_playing())

    def is_paused(self) -> bool:
        state = self._player.get_state()
        return state == self._vlc.State.Paused

    def stop(self) -> None:
        self._player.stop()

    def seek_relative(self, delta_ms: int) -> None:
        current = self._player.get_time()
        if current < 0:
            return
        length = self._player.get_length()
        new_time = max(0, current + delta_ms)
        if length > 0:
            new_time = min(new_time, length)
        self._player.set_time(int(new_time))

    def get_time(self) -> int:
        return self._player.get_time()

    def get_length(self) -> int:
        return self._player.get_length()

    def set_time(self, position_ms: int) -> None:
        length = self._player.get_length()
        new_time = max(0, position_ms)
        if length > 0:
            new_time = min(new_time, length)
        self._player.set_time(int(new_time))

    def get_volume(self) -> int:
        volume = self._player.audio_get_volume()
        if volume < 0:
            return -1
        return volume

    def set_volume(self, volume: int) -> None:
        self._player.audio_set_volume(max(0, min(100, volume)))

    def is_muted(self) -> bool:
        return bool(self._player.audio_get_mute())

    def set_mute(self, muted: bool) -> None:
        self._player.audio_set_mute(muted)

    def toggle_mute(self) -> bool:
        self._player.audio_toggle_mute()
        return self.is_muted()

    def _on_end_reached(self, _event) -> None:
        self.end_reached.emit()

    def _on_error(self, _event) -> None:
        self.playback_error.emit("Playback error")
