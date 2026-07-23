"""Main application window."""

import logging
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QCloseEvent, QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.models.play_queue import PlayQueue
from karaoke_blast.models.playlist import Playlist
from karaoke_blast.models.sort_strategy import SortStrategy, sort_paths
from karaoke_blast.player.controls_bar import ControlsBar
from karaoke_blast.player.video_widget import VideoWidget
from karaoke_blast.player.vlc_player import SEEK_STEP_MS, VlcPlayer
from karaoke_blast.storage.folder_history import FolderHistory
from karaoke_blast.storage.folder_queues import FolderQueues
from karaoke_blast.storage.settings import Settings
from karaoke_blast.ui.recent_folders_panel import RecentFoldersPanel
from karaoke_blast.ui.song_list_panel import PANEL_DEFAULT_WIDTH, SongListPanel
from karaoke_blast.utils.display import display_name
from karaoke_blast.utils.resources import icon_pixmap
from karaoke_blast.utils.video_scanner import scan_videos

logger = logging.getLogger(__name__)

OVERLAY_HIDE_MS = 4000
CONTROLS_HIDE_MS = 3000


def _same_paths(left: list[Path], right: list[Path]) -> bool:
    if len(left) != len(right):
        return False
    return all(a.resolve() == b.resolve() for a, b in zip(left, right, strict=True))


class MainWindow(QWidget):
    """Full-screen karaoke player with folder-based playlist."""

    def __init__(self, initial_folder: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Karaoke Blast")
        self.setMinimumSize(800, 450)
        self.setMouseTracking(True)

        self._playlist = Playlist()
        self._folder: Path | None = None
        self._raw_paths: list[Path] = []
        self._sort_strategy = SortStrategy.NAME_ASC
        self._list_visible = False
        self._stopped = False
        self._saved_splitter_sizes: list[int] | None = None
        self._play_queue = PlayQueue()
        self._folder_history = FolderHistory()
        self._folder_queues = FolderQueues()
        self._settings = Settings()

        self._stack = QStackedWidget()
        self._empty_state = self._build_empty_state()
        self._player_page = self._build_player_page()

        self._stack.addWidget(self._empty_state)
        self._stack.addWidget(self._player_page)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

        self._vlc: VlcPlayer | None = None

        self._overlay_timer = QTimer(self)
        self._overlay_timer.setSingleShot(True)
        self._overlay_timer.timeout.connect(self._hide_overlay)

        self._controls_timer = QTimer(self)
        self._controls_timer.setSingleShot(True)
        self._controls_timer.timeout.connect(self._hide_controls)

        if initial_folder is not None:
            QTimer.singleShot(0, lambda: self._load_folder(initial_folder))

    def _ensure_vlc(self) -> bool:
        if self._vlc is not None:
            return True
        try:
            self._vlc = VlcPlayer(self._video_widget)
        except RuntimeError as exc:
            QMessageBox.critical(self, "VLC Not Found", str(exc))
            return False

        self._vlc.end_reached.connect(
            self._on_end_reached, Qt.ConnectionType.QueuedConnection
        )
        self._vlc.playback_error.connect(
            self._on_playback_error, Qt.ConnectionType.QueuedConnection
        )

        self._apply_saved_audio()
        return True

    def _apply_saved_audio(self) -> None:
        if self._vlc is None:
            return
        self._vlc.set_volume(self._settings.volume)
        self._controls.set_volume(self._settings.volume)
        self._vlc.set_mute(self._settings.muted)
        self._controls.set_muted(self._settings.muted)

    def _build_empty_state(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: #1a1a2e;")
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo = QLabel()
        logo.setPixmap(icon_pixmap(128))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("background: transparent; margin-bottom: 8px;")

        title = QLabel("Karaoke Blast")
        title.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Open a folder to start playing")
        subtitle.setStyleSheet("color: #aaa; font-size: 16px; margin-bottom: 24px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        open_btn = QPushButton("Open Folder")
        open_btn.setFixedSize(160, 44)
        open_btn.setStyleSheet(
            "QPushButton { background: #e94560; color: white; border: none;"
            " border-radius: 6px; font-size: 15px; }"
            "QPushButton:hover { background: #ff6b81; }"
        )
        open_btn.clicked.connect(self._open_folder_dialog)

        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._recent_folders = RecentFoldersPanel()
        self._recent_folders.folder_selected.connect(self._load_folder)
        layout.addSpacing(16)
        layout.addWidget(self._recent_folders, alignment=Qt.AlignmentFlag.AlignCenter)
        self._refresh_recent_folders()

        return page

    def _refresh_recent_folders(self) -> None:
        self._recent_folders.set_folders(self._folder_history.folders())

    def _build_player_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: black;")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(True)
        self._splitter.splitterMoved.connect(self._on_splitter_moved)

        self._song_list = SongListPanel()
        self._song_list.hide()
        self._song_list.song_selected.connect(self._on_song_selected)
        self._song_list.play_next_requested.connect(self._on_play_next_requested)
        self._song_list.remove_from_queue_requested.connect(self._on_remove_from_queue)
        self._song_list.clear_queue_requested.connect(self._on_clear_queue)
        self._song_list.sort_changed.connect(self._on_sort_changed)
        self._song_list.close_requested.connect(self._hide_song_list)
        self._song_list.refresh_requested.connect(self._refresh_song_list)

        self._video_container = QWidget()
        self._video_container.setStyleSheet("background-color: black;")
        self._video_container.setMouseTracking(True)
        self._video_container.installEventFilter(self)

        self._video_widget = VideoWidget(self._video_container)

        self._overlay = QLabel(self._video_container)
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._overlay.setStyleSheet(
            "background-color: rgba(0, 0, 0, 160); color: white;"
            " padding: 8px 16px; border-radius: 4px; font-size: 14px;"
        )
        self._overlay.hide()

        self._status_label = QLabel(self._video_container)
        self._status_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(
            "color: white; font-size: 24px; background: transparent;"
        )
        self._status_label.hide()

        self._splitter.addWidget(self._song_list)
        self._splitter.addWidget(self._video_container)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([0, 800])

        self._controls = ControlsBar()
        self._controls.set_volume(self._settings.volume)
        self._controls.set_muted(self._settings.muted)
        self._controls.installEventFilter(self)
        self._controls.set_pinned(not self._settings.controls_auto_hide)
        if self._settings.controls_auto_hide:
            self._controls.hide()
        self._wire_controls()

        layout.addWidget(self._splitter, 1)
        layout.addWidget(self._controls)
        return page

    def _wire_controls(self) -> None:
        self._controls.play_clicked.connect(self._on_play)
        self._controls.pause_clicked.connect(self._on_pause)
        self._controls.stop_clicked.connect(self._on_stop)
        self._controls.previous_clicked.connect(self._previous_track)
        self._controls.next_clicked.connect(self._next_track)
        self._controls.rewind_clicked.connect(self._on_rewind)
        self._controls.forward_clicked.connect(self._on_forward)
        self._controls.volume_changed.connect(self._on_volume_changed)
        self._controls.mute_toggled.connect(self._on_mute_toggled)
        self._controls.list_toggled.connect(self._toggle_song_list)
        self._controls.pin_toggled.connect(self._on_controls_pin_toggled)

    def eventFilter(self, obj, event) -> bool:
        if (
            event.type() == QEvent.Type.MouseMove
            and obj in (self._video_container, self._controls)
            and self._stack.currentWidget() == self._player_page
        ):
            self._show_controls()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_video_container"):
            self._reposition_video_ui()
            if self._vlc is not None:
                self._vlc.bind_output()

    def _on_splitter_moved(self, _pos: int, _index: int) -> None:
        sizes = self._splitter.sizes()
        self._list_visible = sizes[0] > 0 and self._song_list.isVisible()
        self._reposition_video_ui()
        if self._vlc is not None:
            QTimer.singleShot(0, self._vlc.bind_output)

    def _reposition_video_ui(self) -> None:
        w = self._video_container.width()
        h = self._video_container.height()
        self._video_widget.setGeometry(0, 0, w, h)
        self._reposition_status_label()
        self._reposition_overlay()

    def _reposition_status_label(self, *, show: bool = False) -> None:
        w = self._video_container.width()
        h = self._video_container.height()
        if w <= 0 or h <= 0:
            return
        should_show = show or self._status_label.isVisible()
        if self._status_label.isVisible():
            self._status_label.hide()
            self._video_container.update()
        self._status_label.setGeometry(0, 0, w, h)
        if should_show:
            self._status_label.show()
            self._status_label.raise_()

    def _show_status_message(self, message: str) -> None:
        self._status_label.setText(message)
        self._reposition_status_label(show=True)

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)
        if self._stack.currentWidget() == self._player_page:
            self._show_controls()

    def _reposition_overlay(self) -> None:
        if not self._overlay.isVisible():
            return
        self._overlay.adjustSize()
        margin = 16
        w = self._video_container.width()
        h = self._video_container.height()
        x = (w - self._overlay.width()) // 2
        y = h - self._overlay.height() - margin
        self._overlay.move(max(margin, x), max(margin, y))

    def _reposition_controls(self) -> None:
        self._reposition_video_ui()

    def _show_song_list(self) -> None:
        self._list_visible = True
        self._song_list.show()
        total = max(self._splitter.width(), PANEL_DEFAULT_WIDTH + 400)
        if self._saved_splitter_sizes and self._saved_splitter_sizes[0] > 0:
            self._splitter.setSizes(self._saved_splitter_sizes)
        else:
            self._splitter.setSizes([PANEL_DEFAULT_WIDTH, total - PANEL_DEFAULT_WIDTH])
        if self._playlist.paths:
            self._song_list.set_current_index(self._playlist.index)

    def _toggle_song_list(self) -> None:
        if self._stack.currentWidget() != self._player_page or not self._playlist.paths:
            return
        if self._list_visible:
            self._hide_song_list()
        else:
            self._show_song_list()

    def _hide_song_list(self) -> None:
        sizes = self._splitter.sizes()
        if sizes[0] <= 0 and not self._song_list.isVisible():
            return
        if sizes[0] > 0:
            self._saved_splitter_sizes = sizes
        self._list_visible = False
        total = sum(sizes) or self._splitter.width()
        self._splitter.setSizes([0, total])
        self._song_list.hide()

    def _hide_controls(self) -> None:
        if not self._settings.controls_auto_hide:
            return
        self._controls.hide()

    def _on_controls_pin_toggled(self, pinned: bool) -> None:
        self._settings.controls_auto_hide = not pinned
        self._settings.save()
        if pinned:
            self._controls_timer.stop()
            self._show_controls()
        else:
            self._controls_timer.start(CONTROLS_HIDE_MS)

    def _raise_ui_layers(self) -> None:
        if self._status_label.isVisible():
            self._status_label.raise_()
        if self._overlay.isVisible():
            self._overlay.raise_()

    def _show_controls(self) -> None:
        if self._stack.currentWidget() != self._player_page:
            return
        self._controls.show()
        self._reposition_video_ui()
        if self._settings.controls_auto_hide:
            self._controls_timer.start(CONTROLS_HIDE_MS)
        else:
            self._controls_timer.stop()

    def _open_folder_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open Video Folder")
        if folder:
            self._load_folder(Path(folder))

    def _load_folder(self, folder: Path) -> None:
        folder = folder.resolve()
        if not folder.is_dir():
            QMessageBox.warning(self, "Invalid Folder", f"Not a directory:\n{folder}")
            return

        paths = scan_videos(folder)
        if not paths:
            QMessageBox.information(
                self,
                "No Videos Found",
                f"No supported video files found in:\n{folder}\n\n"
                "Supported formats: .mp4, .mkv, .avi, .mov, .webm, .m4v",
            )
            return

        self._folder = folder
        self._raw_paths = paths
        self._folder_history.add(folder)
        self._refresh_recent_folders()
        self._sort_strategy = SortStrategy.NAME_ASC
        sorted_paths = sort_paths(self._raw_paths, self._sort_strategy)
        restored_index = self._restore_folder_current(sorted_paths)
        self._playlist = Playlist(
            paths=sorted_paths,
            index=restored_index if restored_index is not None else 0,
        )
        self._stopped = True
        self._overlay.hide()
        self._status_label.hide()
        self._stack.setCurrentWidget(self._player_page)
        self.showFullScreen()
        QApplication.processEvents()
        if not self._ensure_vlc():
            self._stack.setCurrentWidget(self._empty_state)
            self.showNormal()
            return
        self._vlc.stop()
        self._song_list.set_sort_strategy(self._sort_strategy)
        self._restore_folder_queue(sorted_paths)
        self._song_list.set_songs(sorted_paths, current_index=restored_index)
        self._update_queue_display()
        self._show_song_list()
        self._show_controls()
        self._reposition_video_ui()
        QTimer.singleShot(0, self._show_ready_to_play)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._vlc is not None:
            self._vlc.bind_output()
        if hasattr(self, "_status_label") and self._status_label.isVisible():
            QTimer.singleShot(0, self._reposition_status_label)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_folder_state()
        super().closeEvent(event)

    def _show_toast(self, message: str, duration_ms: int = 4000) -> None:
        """Show a temporary overlay message."""
        self._overlay.setText(message)
        self._overlay.show()
        self._overlay.raise_()
        self._reposition_overlay()
        self._overlay_timer.start(duration_ms)

    def _play_current(self) -> None:
        if self._vlc is None:
            return
        current = self._playlist.current()
        if current is None:
            self._show_end_of_playlist()
            return
        if not current.exists():
            logger.warning("File not found, skipping: %s", current)
            self._show_toast(
                f'"{display_name(current)}" not found — try refreshing the song list',
                duration_ms=5000,
            )
            QTimer.singleShot(0, self._advance_to_next_track)
            return
        queue_changed = False
        if self._play_queue.contains(self._playlist.index):
            self._play_queue.remove(self._playlist.index)
            queue_changed = True
        self._stopped = False
        self._status_label.hide()
        self._show_overlay()
        self._show_controls()
        self._vlc.play(current)
        self._apply_saved_audio()
        QTimer.singleShot(0, self._apply_saved_audio)
        QTimer.singleShot(100, self._apply_saved_audio)
        self._song_list.set_current_index(self._playlist.index)
        if queue_changed:
            self._update_queue_display()
        else:
            self._save_folder_state()
        self._raise_ui_layers()

    def _on_song_selected(self, index: int) -> None:
        if self._vlc is None:
            return
        self._playlist.go_to(index)
        self._play_current()

    def _on_sort_changed(self, strategy: SortStrategy) -> None:
        self._sort_strategy = strategy
        current = self._playlist.current()
        old_paths = list(self._playlist.paths)
        sorted_paths = sort_paths(self._raw_paths, strategy)
        self._remap_play_queue(old_paths, sorted_paths)
        self._playlist.reorder(sorted_paths, keep_path=current)
        self._song_list.set_songs(
            self._playlist.paths,
            current_index=self._playlist.index,
            clear_search=False,
        )
        self._update_queue_display()

    def _refresh_song_list(self) -> None:
        if self._folder is None:
            return

        current = self._playlist.current()
        old_paths = list(self._playlist.paths)
        paths = scan_videos(self._folder)
        if not paths:
            QMessageBox.information(
                self,
                "No Videos Found",
                f"No supported video files found in:\n{self._folder}",
            )
            return

        self._raw_paths = paths
        sorted_paths = sort_paths(self._raw_paths, self._sort_strategy)
        self._remap_play_queue(old_paths, sorted_paths)
        self._playlist.reorder(sorted_paths, keep_path=current)
        if self._playlist.current() is None and sorted_paths:
            self._playlist.go_to(0)

        self._song_list.set_songs(
            self._playlist.paths,
            current_index=self._playlist.index,
            clear_search=False,
        )
        self._update_queue_display()

        if self._vlc is None:
            return
        if current is not None and self._playlist.current() == current and not self._stopped:
            self._song_list.set_current_index(self._playlist.index)
            return
        if self._playlist.current() is not None:
            self._play_current()
        else:
            self._show_end_of_playlist()

    def _show_overlay(self) -> None:
        current = self._playlist.current()
        if current is None:
            return
        text = f"{self._playlist.position} / {self._playlist.count} — {display_name(current)}"
        if self._play_queue:
            text += f"  ·  {len(self._play_queue)} queued"
        self._overlay.setText(text)
        self._overlay.show()
        self._overlay.raise_()
        self._reposition_overlay()
        self._overlay_timer.start(OVERLAY_HIDE_MS)

    def _hide_overlay(self) -> None:
        self._overlay.hide()

    def _show_ready_to_play(self) -> None:
        self._show_status_message("Select a song to play")

    def _show_end_of_playlist(self) -> None:
        if self._vlc is not None:
            self._vlc.stop()
        self._stopped = True
        self._show_status_message("End of playlist")
        self._show_controls()

    def _on_end_reached(self) -> None:
        self._advance_to_next_track()

    def _on_playback_error(self, message: str) -> None:
        logger.warning("Playback error: %s", message)
        if self._advance_to_next_track():
            return
        QMessageBox.warning(
            self,
            "Playback Error",
            f"{message}\n\nNo more tracks in the playlist.",
        )

    def _advance_to_next_track(self) -> bool:
        """Play the next queued song or the next playlist track. Returns False if nothing to play."""
        queued = self._play_queue.dequeue()
        if queued is not None:
            self._playlist.go_to(queued)
            self._update_queue_display()
            self._play_current()
            return True
        if self._playlist.has_next():
            self._playlist.next()
            self._play_current()
            return True
        self._show_end_of_playlist()
        return False

    def _on_play_next_requested(self, index: int) -> None:
        if index < 0 or index >= self._playlist.count:
            return
        if not self._stopped and index == self._playlist.index:
            return
        if self._play_queue.enqueue(index):
            self._update_queue_display()

    def _on_remove_from_queue(self, index: int) -> None:
        self._play_queue.remove(index)
        self._update_queue_display()

    def _on_clear_queue(self) -> None:
        self._play_queue.clear()
        self._update_queue_display()

    def _update_queue_display(self) -> None:
        self._song_list.set_queue_indices(self._play_queue.indices())
        self._save_folder_state()

    def _restore_folder_current(self, playlist_paths: list[Path]) -> int | None:
        if self._folder is None:
            return None
        saved_path = self._folder_queues.get_current(self._folder)
        if saved_path is None:
            return None
        try:
            resolved = saved_path.resolve()
        except OSError:
            resolved = None
        by_path = {path.resolve(): index for index, path in enumerate(playlist_paths)}
        if resolved is None or not resolved.is_file():
            self._folder_queues.set(
                self._folder,
                queue=self._folder_queues.get_queue(self._folder),
                current=None,
            )
            return None
        index = by_path.get(resolved)
        if index is None:
            self._folder_queues.set(
                self._folder,
                queue=self._folder_queues.get_queue(self._folder),
                current=None,
            )
            return None
        return index

    def _restore_folder_queue(self, playlist_paths: list[Path]) -> None:
        if self._folder is None:
            return
        saved_paths = self._folder_queues.get(self._folder)
        by_path = {path.resolve(): index for index, path in enumerate(playlist_paths)}
        self._play_queue.clear()
        valid_paths: list[Path] = []
        for saved_path in saved_paths:
            try:
                resolved = saved_path.resolve()
            except OSError:
                continue
            if not resolved.is_file():
                continue
            index = by_path.get(resolved)
            if index is None:
                continue
            self._play_queue.enqueue(index)
            valid_paths.append(resolved)
        if not _same_paths(valid_paths, saved_paths):
            self._folder_queues.set(
                self._folder,
                queue=valid_paths,
                current=self._folder_queues.get_current(self._folder),
            )

    def _save_folder_state(self) -> None:
        if self._folder is None:
            return
        queue = [
            self._playlist.paths[index]
            for index in self._play_queue.indices()
            if 0 <= index < len(self._playlist.paths)
        ]
        current: Path | None = None
        playing_index = self._song_list.playing_index()
        if playing_index is not None and 0 <= playing_index < len(self._playlist.paths):
            current = self._playlist.paths[playing_index]
        self._folder_queues.set(self._folder, queue=queue, current=current)

    def _remap_play_queue(self, old_paths: list[Path], new_paths: list[Path]) -> None:
        queued_paths = [
            old_paths[i] for i in self._play_queue.indices() if 0 <= i < len(old_paths)
        ]
        self._play_queue.clear()
        for path in queued_paths:
            if path in new_paths:
                self._play_queue.enqueue(new_paths.index(path))

    def _on_play(self) -> None:
        if self._vlc is None:
            return
        if self._stopped or self._playlist.current() is None:
            if (
                self._stopped
                and self._play_queue
                and self._song_list.playing_index() is None
            ):
                self._advance_to_next_track()
            else:
                self._play_current()
        else:
            self._vlc.resume()
        self._show_overlay()

    def _on_pause(self) -> None:
        if self._vlc is not None:
            self._vlc.pause()
        self._show_overlay()

    def _on_stop(self) -> None:
        if self._vlc is not None:
            self._vlc.stop()
        self._stopped = True
        self._save_folder_state()
        self._show_controls()

    def _on_rewind(self) -> None:
        if self._vlc is not None and not self._stopped:
            self._vlc.seek_relative(-SEEK_STEP_MS)
        self._show_overlay()

    def _on_forward(self) -> None:
        if self._vlc is not None and not self._stopped:
            self._vlc.seek_relative(SEEK_STEP_MS)
        self._show_overlay()

    def _on_volume_changed(self, volume: int) -> None:
        self._settings.volume = volume
        if volume > 0 and self._settings.muted:
            self._settings.muted = False
        self._settings.save()
        if self._vlc is not None:
            self._vlc.set_volume(volume)
            if not self._settings.muted:
                self._vlc.set_mute(False)
        self._controls.set_volume(volume)
        self._controls.set_muted(self._settings.muted)

    def _on_mute_toggled(self) -> None:
        if self._vlc is None:
            return
        self._settings.muted = not self._settings.muted
        self._settings.save()
        self._vlc.set_mute(self._settings.muted)
        self._controls.set_muted(self._settings.muted)

    def _next_track(self) -> None:
        self._advance_to_next_track()

    def _previous_track(self) -> None:
        if self._playlist.has_previous():
            self._playlist.previous()
            self._play_current()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()

        if key == Qt.Key.Key_S:
            self._on_stop()
            return

        if key in (Qt.Key.Key_Right, Qt.Key.Key_N):
            self._next_track()
            return

        if key in (Qt.Key.Key_Left, Qt.Key.Key_P):
            self._previous_track()
            return

        if key in (Qt.Key.Key_BracketLeft, Qt.Key.Key_Comma):
            self._on_rewind()
            return

        if key in (Qt.Key.Key_BracketRight, Qt.Key.Key_Period):
            self._on_forward()
            return

        if key == Qt.Key.Key_M:
            self._on_mute_toggled()
            return

        if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal, Qt.Key.Key_Up):
            volume = self._controls.adjust_volume(5)
            self._on_volume_changed(volume)
            return

        if key in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore, Qt.Key.Key_Down):
            volume = self._controls.adjust_volume(-5)
            self._on_volume_changed(volume)
            return

        if key == Qt.Key.Key_O:
            self._open_folder_dialog()
            return

        if key == Qt.Key.Key_L:
            self._toggle_song_list()
            return

        if key == Qt.Key.Key_P:
            pinned = not self._controls.is_pinned()
            self._controls.set_pinned(pinned)
            self._on_controls_pin_toggled(pinned)
            return

        if key in (Qt.Key.Key_F, Qt.Key.Key_F11):
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            return

        if key == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.close()
            return

        if key == Qt.Key.Key_Q:
            self.close()
            return

        super().keyPressEvent(event)
