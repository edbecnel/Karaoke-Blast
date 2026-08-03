"""Main application window."""

import logging
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, QThread, QTimer
from PyQt6.QtGui import QCloseEvent, QKeyEvent, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.models.media_source import MediaSourceMode
from karaoke_blast.models.path_queue import PathQueue
from karaoke_blast.models.play_queue import PlayQueue
from karaoke_blast.models.playlist import Playlist
from karaoke_blast.models.sort_strategy import SortStrategy, sort_paths
from karaoke_blast.models.youtube_queue import YouTubeQueue
from karaoke_blast.models.youtube_video import YouTubeVideo
from karaoke_blast.player.controls_bar import ControlsBar
from karaoke_blast.player.seek_bar import SeekBar
from karaoke_blast.player.video_widget import VideoWidget
from karaoke_blast.player.vlc_player import SEEK_STEP_MS, VlcPlayer
from karaoke_blast.player.youtube_player import YouTubePlayer
from karaoke_blast.player.youtube_widget import YouTubeWidget
from karaoke_blast.services.youtube_download import downloaded_file_for, start_download
from karaoke_blast.storage.folder_history import FolderHistory
from karaoke_blast.storage.folder_queues import FolderQueues
from karaoke_blast.storage.local_play_history import LocalPlayHistory
from karaoke_blast.storage.paths import downloads_dir
from karaoke_blast.storage.settings import Settings
from karaoke_blast.storage.youtube_play_history import YouTubePlayHistory
from karaoke_blast.ui.opening_screen import OpeningScreen
from karaoke_blast.ui.panel_splitter import PanelSplitter
from karaoke_blast.ui.recent_folders_panel import RecentFoldersPanel
from karaoke_blast.ui.song_list_panel import (
    PANEL_DEFAULT_WIDTH,
    PANEL_MAX_WIDTH,
    PANEL_MIN_WIDTH,
    SongListPanel,
)
from karaoke_blast.ui.youtube_panel import YouTubePanel
from karaoke_blast.utils.display import display_name
from karaoke_blast.utils.resources import logo_default_window_size
from karaoke_blast.utils.video_scanner import scan_videos

logger = logging.getLogger(__name__)

OVERLAY_HIDE_MS = 4000
CONTROLS_HIDE_MS = 3000
LAUNCH_WINDOW_MIN = 480


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
        self._path_queue = PathQueue()
        self._youtube_queue = YouTubeQueue()
        self._local_history = LocalPlayHistory()
        self._youtube_history = YouTubePlayHistory()
        self._media_mode = MediaSourceMode.LOCAL
        self._current_youtube: YouTubeVideo | None = None
        self._youtube_stopped = True
        self._external_path: Path | None = None
        self._folder_history = FolderHistory()
        self._folder_queues = FolderQueues()
        self._settings = Settings()
        self._download_thread: QThread | None = None
        self._downloading_video_id: str | None = None
        self._downloading_video: YouTubeVideo | None = None

        self._stack = QStackedWidget()
        self._empty_state = self._build_empty_state()
        self._player_page = self._build_player_page()

        self._stack.addWidget(self._empty_state)
        self._stack.addWidget(self._player_page)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

        self._vlc: VlcPlayer | None = None
        self._youtube_player: YouTubePlayer | None = None
        self._setup_shortcuts()

        self._overlay_timer = QTimer(self)
        self._overlay_timer.setSingleShot(True)
        self._overlay_timer.timeout.connect(self._hide_overlay)

        self._controls_timer = QTimer(self)
        self._controls_timer.setSingleShot(True)
        self._controls_timer.timeout.connect(self._hide_controls)

        self._seek_timer = QTimer(self)
        self._seek_timer.setInterval(250)
        self._seek_timer.timeout.connect(self._update_seek_position)

        self._launch_geometry_timer = QTimer(self)
        self._launch_geometry_timer.setSingleShot(True)
        self._launch_geometry_timer.timeout.connect(self._save_launch_window_geometry)

        if initial_folder is not None:
            QTimer.singleShot(0, lambda: self._load_folder(initial_folder))
        else:
            self._apply_launch_window_geometry()

    def _ensure_youtube(self) -> bool:
        if self._youtube_player is not None:
            return True
        self._youtube_player = YouTubePlayer(self._youtube_widget)
        self._youtube_player.end_reached.connect(
            self._on_youtube_end_reached, Qt.ConnectionType.QueuedConnection
        )
        self._youtube_player.playback_error.connect(
            self._on_youtube_playback_error, Qt.ConnectionType.QueuedConnection
        )
        return True

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

    def _apply_youtube_audio(self) -> None:
        if self._youtube_player is None:
            return
        self._youtube_player.set_volume(self._settings.volume)
        self._youtube_player.set_mute(self._settings.muted)
        self._controls.set_volume(self._settings.volume)
        self._controls.set_muted(self._settings.muted)

    def _is_launch_screen(self) -> bool:
        return self._stack.currentWidget() == self._empty_state and not self.isFullScreen()

    def _launch_window_size(self) -> tuple[int, int]:
        width = self._settings.launch_window_width
        height = self._settings.launch_window_height
        if (
            width is not None
            and height is not None
            and width >= LAUNCH_WINDOW_MIN
            and height >= LAUNCH_WINDOW_MIN
        ):
            return width, height
        return logo_default_window_size()

    def _apply_launch_window_geometry(self) -> None:
        width, height = self._launch_window_size()
        self.setMinimumSize(LAUNCH_WINDOW_MIN, LAUNCH_WINDOW_MIN)
        self.resize(width, height)
        self._center_on_screen()

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def _save_launch_window_geometry(self) -> None:
        if not self._is_launch_screen():
            return
        self._settings.launch_window_width = self.width()
        self._settings.launch_window_height = self.height()
        self._settings.save()

    def _build_empty_state(self) -> QWidget:
        page = OpeningScreen()
        layout = page.content_layout()

        subtitle = QLabel("Open a folder to start playing")
        subtitle.setStyleSheet(
            "color: white; font-size: 18px; font-weight: 600; background: transparent;"
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        open_btn = QPushButton("Open Folder")
        open_btn.setFixedSize(180, 48)
        open_btn.setStyleSheet(
            "QPushButton { background: #e94560; color: white; border: none;"
            " border-radius: 8px; font-size: 16px; font-weight: bold; }"
            "QPushButton:hover { background: #ff6b81; }"
        )
        open_btn.clicked.connect(self._open_folder_dialog)

        youtube_btn = QPushButton("Search YouTube")
        youtube_btn.setFixedSize(180, 48)
        youtube_btn.setStyleSheet(
            "QPushButton { background: #2d2d42; color: white; border: 1px solid #5a5a72;"
            " border-radius: 8px; font-size: 16px; font-weight: bold; }"
            "QPushButton:hover { background: #3a3a52; border-color: #7a7a92; }"
        )
        youtube_btn.clicked.connect(self._enter_youtube_mode)

        layout.addWidget(subtitle)
        layout.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(youtube_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._recent_folders = RecentFoldersPanel()
        self._recent_folders.folder_selected.connect(self._on_start_menu_folder_selected)
        layout.addSpacing(8)
        layout.addWidget(self._recent_folders, alignment=Qt.AlignmentFlag.AlignCenter)
        self._refresh_recent_folders()

        return page

    def _refresh_recent_folders(self) -> None:
        downloads = downloads_dir()
        recent = [
            folder
            for folder in self._folder_history.folders()
            if folder.resolve() != downloads.resolve()
        ]
        self._recent_folders.set_folders(recent, pinned=[downloads])

    def _on_start_menu_folder_selected(self, folder: Path) -> None:
        allow_empty = folder.resolve() == downloads_dir().resolve()
        self._load_folder(folder, allow_empty=allow_empty)

    def _build_player_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: black;")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = PanelSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(True)
        self._splitter.splitterMoved.connect(self._on_splitter_moved)

        self._song_list = SongListPanel()
        self._song_list.hide()
        self._song_list.song_selected.connect(self._on_song_selected)
        self._song_list.play_next_requested.connect(self._on_play_next_requested)
        self._song_list.remove_from_queue_requested.connect(self._on_remove_from_queue)
        self._song_list.clear_queue_requested.connect(self._on_clear_queue)
        self._song_list.queue_reordered.connect(self._on_queue_reordered)
        self._song_list.sort_changed.connect(self._on_sort_changed)
        self._song_list.close_requested.connect(self._hide_song_list)
        self._song_list.refresh_requested.connect(self._refresh_song_list)
        self._song_list.resize_dragged.connect(self._on_panel_resize_drag)
        self._song_list.queue_split_changed.connect(self._on_queue_split_changed)
        self._song_list.set_queue_section_ratio(self._settings.queue_section_ratio)
        self._song_list.history_play_requested.connect(self._on_history_play_requested)
        self._song_list.history_queue_requested.connect(self._on_history_queue_requested)
        self._song_list.history_remove_requested.connect(self._on_history_remove_requested)
        self._song_list.history_clear_requested.connect(self._on_history_clear_requested)

        self._youtube_panel = YouTubePanel()
        self._youtube_panel.hide()
        self._youtube_panel.configure_search(
            backend_name=self._settings.youtube_search_backend,
            api_key=self._settings.youtube_api_key,
        )
        self._youtube_panel.play_requested.connect(self._on_youtube_play_requested)
        self._youtube_panel.queue_requested.connect(self._on_youtube_queue_requested)
        self._youtube_panel.remove_from_queue_requested.connect(
            self._on_youtube_remove_from_queue
        )
        self._youtube_panel.clear_queue_requested.connect(self._on_youtube_clear_queue)
        self._youtube_panel.close_requested.connect(self._hide_side_panel)
        self._youtube_panel.resize_dragged.connect(self._on_panel_resize_drag)
        self._youtube_panel.search_backend_fallback.connect(self._show_toast)
        self._youtube_panel.history_remove_requested.connect(self._on_youtube_history_remove)
        self._youtube_panel.history_clear_requested.connect(self._on_youtube_history_clear)
        self._youtube_panel.download_requested.connect(self._on_youtube_download_requested)

        self._left_panel_stack = QStackedWidget()
        self._left_panel_stack.addWidget(self._song_list)
        self._left_panel_stack.addWidget(self._youtube_panel)

        self._video_container = QWidget()
        self._video_container.setStyleSheet("background-color: black;")
        self._video_container.setMouseTracking(True)
        self._video_container.installEventFilter(self)

        self._canvas_stack = QStackedWidget(self._video_container)
        self._video_widget = VideoWidget(self._canvas_stack)
        self._youtube_widget = YouTubeWidget(self._canvas_stack)
        self._canvas_stack.addWidget(self._video_widget)
        self._canvas_stack.addWidget(self._youtube_widget)
        self._canvas_stack.setCurrentIndex(0)

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

        self._splitter.addWidget(self._left_panel_stack)
        self._splitter.addWidget(self._video_container)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([0, 800])

        self._controls = ControlsBar()
        self._controls.set_volume(self._settings.volume)
        self._controls.set_muted(self._settings.muted)
        self._controls.installEventFilter(self)
        self._controls.set_pinned(not self._settings.controls_auto_hide)
        self._controls.set_media_mode(self._media_mode)
        if self._settings.controls_auto_hide:
            self._controls.hide()
        self._wire_controls()

        self._seek_bar = SeekBar()
        self._seek_bar.installEventFilter(self)
        self._seek_bar.seek_requested.connect(self._on_seek_requested)
        self._seek_bar.interaction_started.connect(self._show_controls)
        if self._settings.controls_auto_hide:
            self._seek_bar.hide()

        layout.addWidget(self._splitter, 1)
        layout.addWidget(self._seek_bar)
        layout.addWidget(self._controls)
        return page

    def _wire_controls(self) -> None:
        self._controls.play_pause_clicked.connect(self._toggle_play_pause)
        self._controls.stop_clicked.connect(self._on_stop)
        self._controls.previous_clicked.connect(self._previous_track)
        self._controls.next_clicked.connect(self._next_track)
        self._controls.rewind_clicked.connect(self._on_rewind)
        self._controls.forward_clicked.connect(self._on_forward)
        self._controls.volume_changed.connect(self._on_volume_changed)
        self._controls.mute_toggled.connect(self._on_mute_toggled)
        self._controls.list_toggled.connect(self._toggle_song_list)
        self._controls.pin_toggled.connect(self._on_controls_pin_toggled)
        self._controls.fullscreen_toggled.connect(self._toggle_fullscreen)
        self._controls.home_clicked.connect(self._go_to_start_menu)

    def _go_to_start_menu(self) -> None:
        if self._stack.currentWidget() != self._player_page:
            return
        self._save_folder_state()
        if self._media_mode == MediaSourceMode.LOCAL:
            self._freeze_local_playback()
        elif self._media_mode == MediaSourceMode.YOUTUBE:
            if self._youtube_player is not None:
                self._youtube_player.stop()
            self._current_youtube = None
            self._youtube_stopped = True
            self._controls.set_playing(False)
            self._update_youtube_queue_display()
            self._youtube_panel.clear_messages()
        self._hide_side_panel()
        self._overlay.hide()
        self._status_label.hide()
        self._update_local_history_display()
        self._update_youtube_history_display()
        self._stack.setCurrentWidget(self._empty_state)
        if self.isFullScreen():
            self.showNormal()
        self._apply_launch_window_geometry()
        self._sync_fullscreen_control()

    def eventFilter(self, obj, event) -> bool:
        if (
            event.type() == QEvent.Type.MouseMove
            and obj in (self._video_container, self._controls, self._seek_bar)
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
        if self._is_launch_screen():
            self._launch_geometry_timer.start(300)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        # macOS fullscreen transitions often leave the divider under VLC's
        # native view until layout/z-order is re-armed.
        if (
            event.type() == QEvent.Type.WindowStateChange
            and hasattr(self, "_song_list")
            and self._list_visible
        ):
            QTimer.singleShot(0, self._rearm_panel_resize)
            QTimer.singleShot(100, self._rearm_panel_resize)
        if (
            event.type() == QEvent.Type.WindowStateChange
            and hasattr(self, "_youtube_panel")
            and self._list_visible
            and self._media_mode == MediaSourceMode.YOUTUBE
        ):
            QTimer.singleShot(0, self._rearm_panel_resize)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "_controls"):
            self._sync_fullscreen_control()

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        self._sync_fullscreen_control()

    def _sync_fullscreen_control(self) -> None:
        if hasattr(self, "_controls"):
            self._controls.set_fullscreen(self.isFullScreen())

    def _on_panel_resize_drag(self, delta: int) -> None:
        sizes = self._splitter.sizes()
        total = sum(sizes)
        if total <= 0:
            return
        min_video = 320
        new_left = sizes[0] + delta
        new_left = max(PANEL_MIN_WIDTH, min(PANEL_MAX_WIDTH, new_left))
        new_left = min(new_left, max(PANEL_MIN_WIDTH, total - min_video))
        self._splitter.setSizes([new_left, total - new_left])

    def _rearm_panel_resize(self) -> None:
        panel = self._active_side_panel()
        if not self._list_visible or not panel.isVisible():
            return
        if self._media_mode == MediaSourceMode.YOUTUBE:
            self._youtube_panel.raise_edge_grip()
        else:
            self._song_list.raise_edge_grip()
        handle = self._splitter.handle(1)
        handle.raise_()
        handle.setCursor(Qt.CursorShape.SizeHorCursor)
        self._reposition_video_ui()
        if self._vlc is not None and self._media_mode == MediaSourceMode.LOCAL:
            self._vlc.bind_output()

    def _on_queue_split_changed(self, ratio: float) -> None:
        self._settings.queue_section_ratio = ratio
        self._settings.save()

    def _on_splitter_moved(self, _pos: int, _index: int) -> None:
        sizes = self._splitter.sizes()
        panel = self._active_side_panel()
        self._list_visible = sizes[0] > 0 and panel.isVisible()
        self._reposition_video_ui()
        if self._vlc is not None and self._media_mode == MediaSourceMode.LOCAL:
            QTimer.singleShot(0, self._vlc.bind_output)

    def _reposition_video_ui(self) -> None:
        w = self._video_container.width()
        h = self._video_container.height()
        # Keep VLC's native view a few pixels off the divider so it cannot
        # swallow hover on the panel grip / splitter in fullscreen.
        left = 4 if self._list_visible else 0
        width = max(0, w - left)
        self._canvas_stack.setGeometry(left, 0, width, h)
        self._video_widget.setGeometry(0, 0, width, h)
        self._youtube_widget.setGeometry(0, 0, width, h)
        self._reposition_status_label()
        self._reposition_overlay()
        if self._list_visible:
            if self._media_mode == MediaSourceMode.YOUTUBE:
                self._youtube_panel.raise_edge_grip()
            else:
                self._song_list.raise_edge_grip()

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

    def _active_side_panel(self) -> QWidget:
        if self._media_mode == MediaSourceMode.YOUTUBE:
            return self._youtube_panel
        return self._song_list

    def _show_side_panel(self) -> None:
        panel = self._active_side_panel()
        self._list_visible = True
        panel.show()
        total = max(self._splitter.width(), PANEL_DEFAULT_WIDTH + 400)
        if self._saved_splitter_sizes and self._saved_splitter_sizes[0] > 0:
            self._splitter.setSizes(self._saved_splitter_sizes)
        else:
            self._splitter.setSizes([PANEL_DEFAULT_WIDTH, total - PANEL_DEFAULT_WIDTH])
        handle = self._splitter.handle(1)
        handle.raise_()
        handle.setCursor(Qt.CursorShape.SizeHorCursor)
        if self._media_mode == MediaSourceMode.LOCAL and self._playlist.paths:
            self._song_list.set_current_index(self._playlist.index)
        if self._media_mode == MediaSourceMode.YOUTUBE:
            self._youtube_panel.raise_edge_grip()
        else:
            self._song_list.raise_edge_grip()

    def _show_song_list(self) -> None:
        if self._media_mode != MediaSourceMode.LOCAL:
            return
        self._show_side_panel()

    def _toggle_song_list(self) -> None:
        if self._stack.currentWidget() != self._player_page:
            return
        if self._media_mode == MediaSourceMode.YOUTUBE:
            if self._list_visible:
                self._hide_side_panel()
            else:
                self._show_side_panel()
            return
        if not self._playlist.paths:
            return
        if self._list_visible:
            self._hide_side_panel()
        else:
            self._show_side_panel()

    def _hide_side_panel(self) -> None:
        panel = self._active_side_panel()
        sizes = self._splitter.sizes()
        if sizes[0] <= 0 and not panel.isVisible():
            return
        if sizes[0] > 0:
            self._saved_splitter_sizes = sizes
        self._list_visible = False
        total = sum(sizes) or self._splitter.width()
        self._splitter.setSizes([0, total])
        panel.hide()

    def _hide_song_list(self) -> None:
        if self._media_mode != MediaSourceMode.LOCAL:
            return
        self._hide_side_panel()

    def _hide_controls(self) -> None:
        if not self._settings.controls_auto_hide:
            return
        if self._seek_bar.is_scrubbing():
            self._controls_timer.start(CONTROLS_HIDE_MS)
            return
        self._seek_bar.hide()
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
        if self._media_mode == MediaSourceMode.YOUTUBE:
            self._seek_bar.hide()
        else:
            self._seek_bar.show()
        self._controls.show()
        self._reposition_video_ui()
        if self._settings.controls_auto_hide:
            self._controls_timer.start(CONTROLS_HIDE_MS)
        else:
            self._controls_timer.stop()

    def _start_seek_updates(self) -> None:
        self._update_seek_position()
        self._seek_timer.start()

    def _stop_seek_updates(self) -> None:
        self._seek_timer.stop()

    def _update_seek_position(self) -> None:
        if self._vlc is None or self._stopped or self._seek_bar.is_scrubbing():
            return
        length = self._vlc.get_length()
        if length > 0:
            self._seek_bar.set_duration(length)
            position = self._vlc.get_time()
            if position >= 0:
                self._seek_bar.set_position(position)

    def _on_seek_requested(self, position_ms: int) -> None:
        if self._vlc is None or self._stopped:
            return
        self._vlc.set_time(position_ms)
        self._seek_bar.set_position(position_ms)
        self._show_overlay()

    def _open_folder_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open Video Folder")
        if folder:
            self._load_folder(Path(folder))

    def _load_folder(self, folder: Path, *, allow_empty: bool = False) -> None:
        folder = folder.resolve()
        if not folder.is_dir():
            QMessageBox.warning(self, "Invalid Folder", f"Not a directory:\n{folder}")
            return

        paths = scan_videos(folder)
        if not paths and not allow_empty:
            QMessageBox.information(
                self,
                "No Videos Found",
                f"No supported video files found in:\n{folder}\n\n"
                "Supported formats: .mp4, .mkv, .avi, .mov, .webm, .m4v",
            )
            return

        self._switch_to_local_mode(clear_youtube_queue=True)

        self._folder = folder
        self._raw_paths = paths
        self._folder_history.add(folder)
        self._refresh_recent_folders()
        self._sort_strategy = SortStrategy.NAME_ASC
        sorted_paths = sort_paths(self._raw_paths, self._sort_strategy)
        restored_index = self._restore_folder_current(sorted_paths) if sorted_paths else None
        self._playlist = Playlist(
            paths=sorted_paths,
            index=restored_index if restored_index is not None else 0,
        )
        self._stopped = True
        self._overlay.hide()
        self._status_label.hide()
        self._stack.setCurrentWidget(self._player_page)
        self.showFullScreen()
        self._sync_fullscreen_control()
        QApplication.processEvents()
        if not self._ensure_vlc():
            self._stack.setCurrentWidget(self._empty_state)
            self.showNormal()
            return
        self._vlc.stop()
        self._controls.set_playing(False)
        self._song_list.set_sort_strategy(self._sort_strategy)
        self._restore_folder_queue(sorted_paths)
        self._song_list.set_songs(sorted_paths, current_index=restored_index)
        self._update_queue_display()
        self._update_local_history_display()
        self._show_song_list()
        self._show_controls()
        self._reposition_video_ui()
        if sorted_paths:
            QTimer.singleShot(0, self._show_ready_to_play)
        else:
            QTimer.singleShot(
                0,
                lambda: self._show_status_message(
                    "No downloads yet — use YouTube mode to download videos"
                ),
            )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._vlc is not None:
            self._vlc.bind_output()
        if hasattr(self, "_status_label") and self._status_label.isVisible():
            QTimer.singleShot(0, self._reposition_status_label)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_launch_window_geometry()
        self._save_folder_state()
        super().closeEvent(event)

    def _show_toast(self, message: str, duration_ms: int = 4000) -> None:
        """Show a temporary overlay message."""
        self._overlay.setText(message)
        self._overlay.show()
        self._overlay.raise_()
        self._reposition_overlay()
        self._overlay_timer.start(duration_ms)

    def _freeze_local_playback(self) -> None:
        if self._vlc is not None:
            self._vlc.stop()
        self._stopped = True
        self._controls.set_playing(False)
        self._stop_seek_updates()
        self._seek_bar.reset()

    def _switch_to_local_mode(self, *, clear_youtube_queue: bool = False) -> None:
        if self._youtube_player is not None:
            self._youtube_player.stop()
        if clear_youtube_queue:
            self._youtube_queue.clear()
        self._current_youtube = None
        self._youtube_stopped = True
        self._media_mode = MediaSourceMode.LOCAL
        self._youtube_panel.clear_messages()
        self._left_panel_stack.setCurrentIndex(0)
        self._canvas_stack.setCurrentIndex(0)
        self._controls.set_media_mode(MediaSourceMode.LOCAL)
        self._update_youtube_queue_display()
        self._update_youtube_history_display()
        if self._vlc is not None:
            self._vlc.bind_output()
        self._reposition_video_ui()

    def _enter_youtube_mode(self) -> None:
        self._freeze_local_playback()
        self._media_mode = MediaSourceMode.YOUTUBE
        self._left_panel_stack.setCurrentIndex(1)
        self._canvas_stack.setCurrentIndex(1)
        self._controls.set_media_mode(MediaSourceMode.YOUTUBE)
        self._stack.setCurrentWidget(self._player_page)
        self.showFullScreen()
        self._sync_fullscreen_control()
        if not self._ensure_youtube():
            self._stack.setCurrentWidget(self._empty_state)
            self.showNormal()
            return
        self._show_side_panel()
        self._show_controls()
        self._apply_youtube_audio()
        self._update_youtube_history_display()
        self._reposition_video_ui()
        self._youtube_panel.focus_search()
        self._show_status_message("Search for a karaoke song to play")

    def _play_youtube(self, video: YouTubeVideo) -> None:
        if not self._ensure_youtube():
            return
        if self._media_mode != MediaSourceMode.YOUTUBE:
            self._freeze_local_playback()
            self._media_mode = MediaSourceMode.YOUTUBE
            self._left_panel_stack.setCurrentIndex(1)
            self._canvas_stack.setCurrentIndex(1)
            self._controls.set_media_mode(MediaSourceMode.YOUTUBE)
            self._stack.setCurrentWidget(self._player_page)
            self.showFullScreen()
            self._sync_fullscreen_control()
            self._show_side_panel()
        self._current_youtube = video
        self._youtube_stopped = False
        self._status_label.hide()
        if self._youtube_queue.contains(video.video_id):
            self._youtube_queue.remove(video.video_id)
        self._youtube_player.play(
            video,
            volume=self._settings.volume,
            muted=self._settings.muted,
        )
        self._youtube_history.add(video)
        self._update_youtube_history_display()
        self._controls.set_playing(True)
        self._stop_seek_updates()
        self._update_youtube_queue_display()
        self._show_youtube_overlay()
        self._show_controls()
        self._raise_ui_layers()

    def _queue_youtube(self, video: YouTubeVideo) -> None:
        if self._youtube_queue.contains(video.video_id):
            self._show_toast("That video is already queued.")
            return
        if (
            self._current_youtube is not None
            and self._current_youtube.video_id == video.video_id
        ):
            self._show_toast("That video is already playing.")
            return
        if self._youtube_stopped and self._current_youtube is None:
            self._play_youtube(video)
            return
        if self._youtube_queue.enqueue(video):
            self._update_youtube_queue_display()
            self._show_toast(f'Queued "{video.title}"')

    def _update_youtube_queue_display(self) -> None:
        queued = [
            video
            for video in self._youtube_queue.items()
            if self._current_youtube is None
            or video.video_id != self._current_youtube.video_id
        ]
        self._youtube_panel.set_queue_state(
            current=None if self._youtube_stopped else self._current_youtube,
            queued=queued,
        )

    def _show_youtube_overlay(self) -> None:
        if self._current_youtube is None:
            return
        text = self._current_youtube.title
        if self._youtube_queue:
            text += f"  ·  {len(self._youtube_queue)} queued"
        self._overlay.setText(text)
        self._overlay.show()
        self._overlay.raise_()
        self._reposition_overlay()
        self._overlay_timer.start(OVERLAY_HIDE_MS)

    def _advance_youtube_queue(self) -> bool:
        next_video = self._youtube_queue.dequeue()
        if next_video is None:
            return False
        self._play_youtube(next_video)
        return True

    def _on_youtube_play_requested(self, video: YouTubeVideo) -> None:
        self._play_youtube(video)

    def _on_youtube_queue_requested(self, video: YouTubeVideo) -> None:
        self._queue_youtube(video)

    def _on_youtube_remove_from_queue(self, video_id: str) -> None:
        removing_now_playing = (
            not self._youtube_stopped
            and self._current_youtube is not None
            and self._current_youtube.video_id == video_id
        )
        self._youtube_queue.remove(video_id)
        if removing_now_playing:
            self._on_stop()
            return
        self._update_youtube_queue_display()

    def _on_youtube_clear_queue(self) -> None:
        self._youtube_queue.clear()
        if not self._youtube_stopped:
            self._on_stop()
        else:
            self._update_youtube_queue_display()

    def _on_youtube_end_reached(self) -> None:
        QTimer.singleShot(50, self._finish_youtube_playback)

    def _finish_youtube_playback(self) -> None:
        if not self._advance_youtube_queue():
            self._youtube_stopped = True
            self._controls.set_playing(False)
            self._update_youtube_queue_display()
            self._update_youtube_history_display()
            self._show_status_message("Search for another song")

    def _on_youtube_playback_error(self, message: str) -> None:
        logger.warning("YouTube playback error: %s", message)
        self._show_toast(message, duration_ms=5000)

    def _play_current(self) -> None:
        if self._media_mode != MediaSourceMode.LOCAL:
            return
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
        self._external_path = None
        self._status_label.hide()
        self._show_overlay()
        self._show_controls()
        self._vlc.play(current)
        self._controls.set_playing(True)
        self._local_history.add(current)
        self._update_local_history_display()
        self._apply_saved_audio()
        self._song_list.set_current_index(self._playlist.index)
        self._update_queue_display(include_now_playing=True)
        if not queue_changed:
            self._save_folder_state()
        self._start_seek_updates()
        self._raise_ui_layers()

    def _play_local_path(self, path: Path) -> None:
        if self._media_mode != MediaSourceMode.LOCAL:
            self._switch_to_local_mode(clear_youtube_queue=False)
        if not self._ensure_vlc():
            return
        if not path.exists():
            self._show_toast(f'"{display_name(path)}" not found', duration_ms=5000)
            return
        if path in self._playlist.paths:
            self._playlist.go_to(self._playlist.paths.index(path))
            self._play_current()
            return
        self._stopped = False
        self._external_path = path
        self._status_label.hide()
        self._show_overlay_for_path(path)
        self._show_controls()
        self._vlc.play(path)
        self._controls.set_playing(True)
        self._local_history.add(path)
        self._update_local_history_display()
        self._apply_saved_audio()
        if path in self._playlist.paths:
            self._song_list.set_current_index(self._playlist.paths.index(path))
        self._update_queue_display(include_now_playing=True)
        self._start_seek_updates()
        self._raise_ui_layers()

    def _show_overlay_for_path(self, path: Path) -> None:
        text = display_name(path)
        if self._play_queue or self._path_queue:
            queued = len(self._play_queue) + len(self._path_queue)
            text += f"  ·  {queued} queued"
        self._overlay.setText(text)
        self._overlay.show()
        self._overlay.raise_()
        self._reposition_overlay()
        self._overlay_timer.start(OVERLAY_HIDE_MS)

    def _update_local_history_display(self) -> None:
        current = None
        if not self._stopped and self._media_mode == MediaSourceMode.LOCAL:
            current = self._external_path or self._playlist.current()
        self._song_list.set_history(self._local_history.paths(), current=current)

    def _update_youtube_history_display(self) -> None:
        current = None if self._youtube_stopped else self._current_youtube
        self._youtube_panel.set_history(self._youtube_history.videos(), current=current)

    def _on_history_play_requested(self, path: Path) -> None:
        self._play_local_path(path)

    def _on_history_queue_requested(self, path: Path) -> None:
        if path in self._playlist.paths:
            self._on_play_next_requested(self._playlist.paths.index(path))
            return
        if self._path_queue.enqueue(path):
            self._show_toast(f'Queued "{display_name(path)}"')

    def _on_history_remove_requested(self, path: Path) -> None:
        self._local_history.remove(path)
        self._update_local_history_display()

    def _on_history_clear_requested(self) -> None:
        self._local_history.clear()
        self._update_local_history_display()

    def _on_youtube_history_remove(self, video_id: str) -> None:
        self._youtube_history.remove(video_id)
        self._update_youtube_history_display()

    def _on_youtube_history_clear(self) -> None:
        self._youtube_history.clear()
        self._update_youtube_history_display()

    def _on_youtube_download_requested(self, video: YouTubeVideo) -> None:
        if self._download_thread is not None and self._download_thread.isRunning():
            if self._downloading_video_id == video.video_id:
                return
            self._show_toast("A download is already in progress.", duration_ms=4000)
            return

        downloads_dir().mkdir(parents=True, exist_ok=True)
        existing = downloaded_file_for(video.video_id)
        if existing is not None:
            self._youtube_panel.show_download_success(
                video.title,
                message=f"Already downloaded: {existing.name}",
            )
            self._offer_open_downloads()
            return

        self._downloading_video_id = video.video_id
        self._downloading_video = video
        self._youtube_panel.show_downloading(video.title)
        self._download_thread, _worker = start_download(
            video=video,
            on_progress=self._on_youtube_download_progress,
            on_finished=self._on_youtube_download_finished,
            on_failed=self._on_youtube_download_failed,
            parent=self,
        )
        self._download_thread.finished.connect(self._on_youtube_download_thread_finished)

    def _on_youtube_download_progress(self, title: str, percent: float, status: str) -> None:
        self._youtube_panel.update_download_progress(title, percent, status)

    def _on_youtube_download_finished(self, path: Path, video: YouTubeVideo) -> None:
        self._folder_history.add(downloads_dir())
        self._refresh_recent_folders()
        self._youtube_panel.show_download_success(
            video.title,
            message=f"Saved: {path.name}",
        )
        self._offer_open_downloads()

    def _on_youtube_download_failed(self, video_id: str, message: str) -> None:
        title = self._downloading_video.title if self._downloading_video else video_id
        self._youtube_panel.show_download_error(title, message)
        self._show_toast(f"Download failed: {message}", duration_ms=6000)

    def _on_youtube_download_thread_finished(self) -> None:
        self._download_thread = None
        self._downloading_video_id = None
        self._downloading_video = None

    def _offer_open_downloads(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Download Complete")
        box.setText("Video saved to your YouTube downloads folder.")
        open_btn = box.addButton("Open Downloads", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Dismiss", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() == open_btn:
            self._load_folder(downloads_dir(), allow_empty=True)

    def _on_song_selected(self, index: int) -> None:
        if self._media_mode != MediaSourceMode.LOCAL:
            self._switch_to_local_mode(clear_youtube_queue=True)
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
        self._controls.set_playing(False)
        self._stop_seek_updates()
        self._seek_bar.reset()
        self._show_status_message("End of playlist")
        self._show_controls()

    def _on_end_reached(self) -> None:
        # Defer so libvlc can finish tearing down the previous media before set_media().
        QTimer.singleShot(50, self._advance_to_next_track)

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
        path = self._path_queue.dequeue()
        if path is not None:
            self._play_local_path(path)
            return True
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
        removing_now_playing = not self._stopped and index == self._playlist.index
        self._play_queue.remove(index)
        if removing_now_playing:
            self._on_stop()
            self._update_queue_display(include_now_playing=False)
            return
        self._update_queue_display()

    def _on_clear_queue(self) -> None:
        self._play_queue.clear()
        if not self._stopped:
            self._on_stop()
        self._update_queue_display(include_now_playing=False)

    def _on_queue_reordered(self, indices: list[int]) -> None:
        self._play_queue.set_order(indices)
        self._update_queue_display()

    def _update_queue_display(self, *, include_now_playing: bool | None = None) -> None:
        self._song_list.set_queue_indices(
            self._play_queue.indices(),
            include_now_playing=include_now_playing,
        )
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
        if self._media_mode == MediaSourceMode.YOUTUBE:
            return
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
            self._controls.set_playing(True)
        self._show_overlay()

    def _on_pause(self) -> None:
        if self._media_mode == MediaSourceMode.YOUTUBE:
            return
        if self._vlc is not None:
            self._vlc.pause()
        self._controls.set_playing(False)
        self._show_overlay()

    def _toggle_play_pause(self) -> None:
        if self._media_mode == MediaSourceMode.YOUTUBE:
            return
        if self._vlc is not None and self._vlc.is_playing():
            self._on_pause()
        else:
            self._on_play()

    def _setup_shortcuts(self) -> None:
        # Window-level so Space works even when a child (list/button) has focus.
        space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        space.setContext(Qt.ShortcutContext.WindowShortcut)
        space.activated.connect(self._on_space_shortcut)

    def _on_space_shortcut(self) -> None:
        focus = QApplication.focusWidget()
        if isinstance(focus, QLineEdit):
            focus.insert(" ")
            return
        self._toggle_play_pause()

    def _on_stop(self) -> None:
        if self._media_mode == MediaSourceMode.YOUTUBE:
            if self._youtube_player is not None:
                self._youtube_player.stop()
            self._current_youtube = None
            self._youtube_stopped = True
            self._controls.set_playing(False)
            self._update_youtube_queue_display()
            self._update_youtube_history_display()
            self._show_status_message("Search for a karaoke song to play")
            self._show_controls()
            return
        if self._vlc is not None:
            self._vlc.stop()
        self._stopped = True
        self._external_path = None
        self._controls.set_playing(False)
        self._stop_seek_updates()
        self._seek_bar.reset()
        self._save_folder_state()
        self._update_local_history_display()
        self._show_controls()

    def _on_rewind(self) -> None:
        if self._media_mode == MediaSourceMode.YOUTUBE:
            return
        if self._vlc is not None and not self._stopped:
            self._vlc.seek_relative(-SEEK_STEP_MS)
        self._show_overlay()

    def _on_forward(self) -> None:
        if self._media_mode == MediaSourceMode.YOUTUBE:
            return
        if self._vlc is not None and not self._stopped:
            self._vlc.seek_relative(SEEK_STEP_MS)
        self._show_overlay()

    def _on_volume_changed(self, volume: int) -> None:
        self._settings.volume = volume
        if volume > 0 and self._settings.muted:
            self._settings.muted = False
        self._settings.save()
        if self._media_mode == MediaSourceMode.YOUTUBE:
            if self._youtube_player is not None:
                self._youtube_player.set_volume(volume)
                if not self._settings.muted:
                    self._youtube_player.set_mute(False)
        elif self._vlc is not None:
            self._vlc.set_volume(volume)
            if not self._settings.muted:
                self._vlc.set_mute(False)
        self._controls.set_volume(volume)
        self._controls.set_muted(self._settings.muted)

    def _on_mute_toggled(self) -> None:
        self._settings.muted = not self._settings.muted
        self._settings.save()
        if self._media_mode == MediaSourceMode.YOUTUBE:
            if self._youtube_player is not None:
                self._youtube_player.set_mute(self._settings.muted)
        elif self._vlc is not None:
            self._vlc.set_mute(self._settings.muted)
        self._controls.set_muted(self._settings.muted)

    def _next_track(self) -> None:
        if self._media_mode == MediaSourceMode.YOUTUBE:
            self._advance_youtube_queue()
            return
        self._advance_to_next_track()

    def _previous_track(self) -> None:
        if self._media_mode == MediaSourceMode.YOUTUBE:
            return
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

        if key == Qt.Key.Key_Y:
            if self._stack.currentWidget() == self._player_page:
                if self._media_mode == MediaSourceMode.YOUTUBE:
                    self._youtube_panel.focus_search()
                else:
                    self._enter_youtube_mode()
            else:
                self._enter_youtube_mode()
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
            self._toggle_fullscreen()
            return

        if key == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
                self._sync_fullscreen_control()
            else:
                self.close()
            return

        if key == Qt.Key.Key_Q:
            self.close()
            return

        super().keyPressEvent(event)
