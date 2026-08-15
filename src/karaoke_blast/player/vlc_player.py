"""VLC media player wrapper."""

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal

from karaoke_blast.player.video_widget import VideoWidget
from karaoke_blast.utils.runtime_deps import configure_vlc_environment

logger = logging.getLogger(__name__)

SEEK_STEP_MS = 10_000
# Volume/mute set before VLC's audio output is ready is often ignored (silent play).
_AUDIO_RETRY_MS = (0, 50, 150, 400, 800, 1500)
_AUDIO_VERIFY_RETRY_MS = 100
_AUDIO_VERIFY_MAX_ATTEMPTS = 30
# Brief pause after stop() so libvlc can release the previous media before set_media().
_TRACK_CHANGE_DEFER_MS = 50


class VlcPlayer(QObject):
    """Thin wrapper around python-vlc with Qt signals."""

    end_reached = pyqtSignal()
    playback_error = pyqtSignal(str)
    _audio_ready = pyqtSignal()

    def __init__(self, video_widget: VideoWidget, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._widget = video_widget
        self._desired_volume = 80
        self._desired_mute = False
        self._play_generation = 0
        self._suppress_end_reached = False
        self._audio_verify_attempts = 0

        configure_vlc_environment()

        try:
            import vlc
        except (OSError, SystemExit) as exc:
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

        # VLC event callbacks run off the Qt thread.
        self._audio_ready.connect(self._apply_audio, Qt.ConnectionType.QueuedConnection)

        event_manager = self._player.event_manager()
        event_manager.event_attach(
            vlc.EventType.MediaPlayerEndReached,
            self._on_end_reached,
        )
        event_manager.event_attach(
            vlc.EventType.MediaPlayerEncounteredError,
            self._on_error,
        )
        event_manager.event_attach(
            vlc.EventType.MediaPlayerPlaying,
            self._on_playing,
        )
        event_manager.event_attach(
            vlc.EventType.MediaPlayerMediaChanged,
            self._on_media_changed,
        )

    def bind_output(self) -> None:
        """Re-attach VLC to the video widget (required after show/resize on macOS)."""
        self._widget.bind_player(self._player)

    def play(self, path: Path) -> None:
        path = Path(path)
        self._play_generation += 1
        generation = self._play_generation

        if self._is_active():
            # Stop first so libvlc fully releases the previous track. set_media() while
            # still playing often leaves the next track silent.
            self._suppress_end_reached = True
            self._player.stop()
            QTimer.singleShot(
                _TRACK_CHANGE_DEFER_MS,
                lambda: self._start_media(path, generation),
            )
            return

        self._start_media(path, generation)

    def _start_media(self, path: Path, generation: int) -> None:
        if generation != self._play_generation:
            return

        self._suppress_end_reached = False
        try:
            if not path.is_file():
                self.playback_error.emit(f"File not found: {path.name}")
                logger.error("VLC play skipped; file missing: %s", path)
                return
        except OSError as exc:
            self.playback_error.emit(f"Cannot open: {path.name}")
            logger.error("VLC play skipped; cannot access %s: %s", path, exc)
            return

        media = self._instance.media_new(str(path))
        self._player.set_media(media)
        self.bind_output()
        result = self._player.play()
        if result == -1:
            self.playback_error.emit(f"Failed to play: {path.name}")
            logger.error("VLC failed to start playback for %s", path)
            return
        if sys.platform in ("darwin", "win32"):
            QTimer.singleShot(0, self.bind_output)
            QTimer.singleShot(100, self.bind_output)
        self._schedule_audio_apply()

    def resume(self) -> None:
        self._player.play()
        self._schedule_audio_apply()

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
        self._desired_volume = max(0, min(100, volume))
        self._apply_audio()

    def is_muted(self) -> bool:
        return bool(self._player.audio_get_mute())

    def set_mute(self, muted: bool) -> None:
        self._desired_mute = muted
        self._apply_audio()

    def toggle_mute(self) -> bool:
        self._desired_mute = not self._desired_mute
        self._apply_audio()
        return self._desired_mute

    def _is_active(self) -> bool:
        return self.is_playing() or self.is_paused()

    def _schedule_audio_apply(self) -> None:
        generation = self._play_generation
        self._audio_verify_attempts = 0
        for delay_ms in _AUDIO_RETRY_MS:
            QTimer.singleShot(delay_ms, lambda g=generation: self._apply_audio(g))

    def _apply_audio(self, generation: int | None = None) -> None:
        if generation is not None and generation != self._play_generation:
            return

        self._player.audio_set_volume(self._desired_volume)
        self._player.audio_set_mute(self._desired_mute)

        if not self._player.is_playing() or self._desired_mute:
            return

        actual = self._player.audio_get_volume()
        if actual == self._desired_volume:
            self._audio_verify_attempts = 0
            return

        self._audio_verify_attempts += 1
        if self._audio_verify_attempts > _AUDIO_VERIFY_MAX_ATTEMPTS:
            logger.warning(
                "Audio volume not confirmed (wanted %s, got %s) after %s attempts",
                self._desired_volume,
                actual,
                self._audio_verify_attempts,
            )
            self._audio_verify_attempts = 0
            return

        gen = self._play_generation
        QTimer.singleShot(_AUDIO_VERIFY_RETRY_MS, lambda: self._apply_audio(gen))

    def _notify_audio_ready(self) -> None:
        self._audio_ready.emit()

    def _on_playing(self, _event) -> None:
        self._notify_audio_ready()

    def _on_media_changed(self, _event) -> None:
        # MediaPlayerPlaying does not always fire again on track changes.
        self._notify_audio_ready()

    def _on_end_reached(self, _event) -> None:
        if self._suppress_end_reached:
            return
        self.end_reached.emit()

    def _on_error(self, _event) -> None:
        self.playback_error.emit("Playback error")
