"""Main application window."""

import logging
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, QThread, QTimer
from PyQt6.QtGui import QCloseEvent, QCursor, QKeyEvent, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
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
from karaoke_blast.models.playlist import Playlist
from karaoke_blast.models.play_history_entry import PlayHistoryEntry
from karaoke_blast.models.queue_item import MixedQueue, QueueItem
from karaoke_blast.models.sort_strategy import SortStrategy, sort_paths
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
from karaoke_blast.storage.play_history import PlayHistory
from karaoke_blast.storage.settings import Settings
from karaoke_blast.ui.opening_screen import OpeningScreen
from karaoke_blast.ui.batch_metadata_dialog import BatchMetadataDialog
from karaoke_blast.ui.batch_rename_dialog import BatchRenameDialog
from karaoke_blast.ui.edit_metadata_dialog import EditMetadataDialog
from karaoke_blast.ui.panel_splitter import PanelSplitter
from karaoke_blast.ui.rename_file_dialog import RenameFileDialog, RenameResult
from karaoke_blast.ui.recent_folders_panel import RecentFoldersPanel
from karaoke_blast.ui.video_type_selector import VideoTypeSelectorWidget
from karaoke_blast.ui.video_types_manager_dialog import VideoTypesManagerDialog
from karaoke_blast.ui.youtube_downloads_folder_row import YouTubeDownloadsFolderRow
from karaoke_blast.utils.video_types import BUILTIN_SONGS_ID, VideoTypeProfile
from karaoke_blast.ui.library_panel import (
    PANEL_DEFAULT_WIDTH,
    PANEL_MAX_WIDTH,
    PANEL_MIN_WIDTH,
    LibraryPanel,
)
from karaoke_blast.utils.display import display_name
from karaoke_blast.utils.resources import logo_default_window_size
from karaoke_blast.utils.song_display import (
    DisplayFormat,
    display_field_labels_from_mapping,
    song_matches_query,
)
from karaoke_blast.utils.video_scanner import (
    MEDIA_EXTENSIONS,
    child_folders_with_videos,
    folder_has_videos,
    is_audio_file,
    scan_videos,
)

logger = logging.getLogger(__name__)

OVERLAY_HIDE_MS = 4000
CONTROLS_HIDE_MS = 3000
# Bottom edge hit area for revealing auto-hidden controls. Polled via cursor
# position so VLC's native view cannot swallow the hover, and so we do not
# need to reserve layout space under the video.
CONTROLS_REVEAL_HIT_HEIGHT = 96
CONTROLS_REVEAL_POLL_MS = 50
LAUNCH_WINDOW_MIN = 480


def _same_paths(left: list[Path], right: list[Path]) -> bool:
    if len(left) != len(right):
        return False
    return all(a.resolve() == b.resolve() for a, b in zip(left, right, strict=True))


def _resolved_path(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


def _is_playable_file(path: Path) -> bool:
    """Return True if *path* is an existing regular file (OS errors treated as missing)."""
    try:
        return path.is_file()
    except OSError:
        return False


class MainWindow(QWidget):
    """Full-screen karaoke player with folder-based playlist."""

    def __init__(self, initial_folder: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Karaoke Blast")
        self.setMinimumSize(800, 450)
        self.setMouseTracking(True)

        self._playlist = Playlist()
        self._folder: Path | None = None  # library root
        self._browse_folder: Path | None = None
        self._recursive_list_mode = False
        self._raw_paths: list[Path] = []
        self._library_paths: list[Path] = []
        self._sort_strategy = SortStrategy.NAME_ASC
        self._list_visible = False
        self._stopped = False
        self._saved_splitter_sizes: list[int] | None = None
        self._mixed_queue = MixedQueue()
        self._play_history = PlayHistory()
        self._media_mode = MediaSourceMode.LOCAL
        self._current_youtube: YouTubeVideo | None = None
        self._current_queue_item: QueueItem | None = None
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
        self._refresh_recent_folders()

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

        self._controls_reveal_timer = QTimer(self)
        self._controls_reveal_timer.setInterval(CONTROLS_REVEAL_POLL_MS)
        self._controls_reveal_timer.timeout.connect(self._poll_controls_reveal)

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

        rename_btn = QPushButton("Rename Downloads")
        rename_btn.setFixedSize(180, 48)
        rename_btn.setStyleSheet(
            "QPushButton { background: #2d2d42; color: white; border: 1px solid #5a5a72;"
            " border-radius: 8px; font-size: 16px; font-weight: bold; }"
            "QPushButton:hover { background: #3a3a52; border-color: #7a7a92; }"
        )
        rename_btn.clicked.connect(self._open_batch_rename_dialog)

        metadata_btn = QPushButton("Tag Metadata")
        metadata_btn.setFixedSize(180, 48)
        metadata_btn.setStyleSheet(
            "QPushButton { background: #2d2d42; color: white; border: 1px solid #5a5a72;"
            " border-radius: 8px; font-size: 16px; font-weight: bold; }"
            "QPushButton:hover { background: #3a3a52; border-color: #7a7a92; }"
        )
        metadata_btn.clicked.connect(self._open_batch_metadata_dialog)

        layout.addWidget(subtitle)
        layout.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(youtube_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._startup_video_type_selector = VideoTypeSelectorWidget(
            video_types=self._settings.video_types,
            active_id=self._settings.active_video_type_id,
        )
        self._startup_video_type_selector.setMaximumWidth(520)
        self._startup_video_type_selector.type_changed.connect(
            self._on_startup_video_type_changed
        )
        self._startup_video_type_selector.types_changed.connect(
            self._on_startup_video_types_changed
        )
        layout.addWidget(
            self._startup_video_type_selector,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        layout.addWidget(rename_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(metadata_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._recent_folders = RecentFoldersPanel()
        self._recent_folders.folder_selected.connect(self._on_start_menu_folder_selected)
        self._recent_folders.folder_remove_requested.connect(
            self._on_recent_folder_remove_requested
        )
        layout.addSpacing(8)
        layout.addWidget(self._recent_folders, alignment=Qt.AlignmentFlag.AlignCenter)

        self._startup_downloads_folder_row = YouTubeDownloadsFolderRow(sidebar=False)
        self._startup_downloads_folder_row.setMaximumWidth(520)
        self._startup_downloads_folder_row.browse_clicked.connect(
            self._browse_youtube_downloads_folder
        )
        layout.addWidget(self._startup_downloads_folder_row, alignment=Qt.AlignmentFlag.AlignCenter)
        self._update_downloads_folder_display()
        self._refresh_recent_folders()

        return page

    def _youtube_downloads_path(self) -> Path:
        return self._settings.resolved_youtube_downloads_dir()

    def _update_downloads_folder_display(self) -> None:
        path = self._youtube_downloads_path()
        self._startup_downloads_folder_row.set_folder(path)
        if hasattr(self, "_library_panel"):
            self._library_panel.set_downloads_folder(path)

    def _browse_youtube_downloads_folder(self) -> None:
        current = self._youtube_downloads_path()
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select YouTube Download Folder",
            str(current),
        )
        if not folder:
            return
        self._settings.set_youtube_downloads_dir(Path(folder))
        self._update_downloads_folder_display()
        self._refresh_recent_folders()

    def _refresh_recent_folders(self) -> None:
        downloads = self._youtube_downloads_path()
        recent = [
            folder
            for folder in self._folder_history.folders()
            if folder.resolve() != downloads.resolve()
        ]
        self._recent_folders.set_folders(recent, pinned=[downloads])
        if hasattr(self, "_library_panel"):
            self._library_panel.set_recent_folders(recent, pinned=[downloads])

    def _on_start_menu_folder_selected(self, folder: Path) -> None:
        allow_empty = folder.resolve() == self._youtube_downloads_path().resolve()
        self._load_folder(folder, allow_empty=allow_empty)

    def _on_recent_folder_remove_requested(self, folder: Path) -> None:
        self._folder_history.remove(folder)
        self._refresh_recent_folders()

    def _build_player_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: black;")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = PanelSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(True)
        self._splitter.splitterMoved.connect(self._on_splitter_moved)

        self._library_panel = LibraryPanel()
        self._library_panel.hide()
        self._library_panel.configure_search(
            backend_name=self._settings.youtube_search_backend,
            api_key=self._settings.youtube_api_key,
        )
        self._library_panel.set_append_karaoke(self._settings.youtube_append_karaoke)
        self._library_panel.append_karaoke_changed.connect(self._on_append_karaoke_changed)
        self._library_panel.song_selected.connect(self._on_song_selected)
        self._library_panel.play_next_requested.connect(self._on_play_next_requested)
        self._library_panel.play_path_requested.connect(self._play_local_path)
        self._library_panel.sort_changed.connect(self._on_sort_changed)
        self._library_panel.close_requested.connect(self._hide_side_panel)
        self._library_panel.refresh_requested.connect(self._refresh_song_list)
        self._library_panel.resize_dragged.connect(self._on_panel_resize_drag)
        self._library_panel.local_search_changed.connect(self._on_local_search_changed)
        self._library_panel.display_mode_changed.connect(self._on_song_display_mode_changed)
        self._library_panel.display_format_changed.connect(
            self._on_song_display_format_changed
        )
        self._library_panel.history_play_requested.connect(self._on_history_play_requested)
        self._library_panel.history_queue_requested.connect(self._on_history_queue_requested)
        self._library_panel.history_remove_requested.connect(self._on_history_remove_requested)
        self._library_panel.history_clear_requested.connect(self._on_history_clear_requested)
        self._library_panel.rename_requested.connect(self._on_rename_requested)
        self._library_panel.edit_metadata_requested.connect(self._on_edit_metadata_requested)
        self._library_panel.folder_selected.connect(self._on_start_menu_folder_selected)
        self._library_panel.browse_folder_requested.connect(self._open_folder_dialog)
        self._library_panel.folder_entered.connect(self._on_folder_entered)
        self._library_panel.navigate_up_requested.connect(self._on_navigate_up)
        self._library_panel.play_all_requested.connect(self._on_play_all_requested)
        self._library_panel.queue_all_requested.connect(self._on_queue_all_requested)
        self._library_panel.play_all_folder_requested.connect(self._on_play_all_folder_requested)
        self._library_panel.queue_all_folder_requested.connect(self._on_queue_all_folder_requested)
        self._library_panel.back_to_folders_requested.connect(self._on_back_to_folders)
        self._library_panel.play_requested.connect(self._on_queue_item_play_requested)
        self._library_panel.queue_requested.connect(self._on_queue_item_queue_requested)
        self._library_panel.youtube_play_requested.connect(self._on_youtube_play_requested)
        self._library_panel.youtube_queue_requested.connect(self._on_youtube_queue_requested)
        self._library_panel.remove_from_queue_requested.connect(self._on_remove_queue_item)
        self._library_panel.clear_queue_requested.connect(self._on_clear_queue)
        self._library_panel.queue_reordered.connect(self._on_queue_reordered)
        self._library_panel.search_backend_fallback.connect(self._show_toast)
        self._library_panel.download_requested.connect(self._on_youtube_download_requested)
        self._library_panel.browse_downloads_folder_requested.connect(
            self._browse_youtube_downloads_folder
        )
        self._library_panel.video_types_settings_requested.connect(
            self._open_video_types_manager
        )
        self._library_panel.set_downloads_folder(self._youtube_downloads_path())
        self._library_panel.set_display_mode(self._settings.song_display_mode)
        self._sync_library_display_format()
        self._sync_library_video_type_label()
        self._sync_library_list_count_labels()

        self._video_container = QWidget()
        self._video_container.setStyleSheet("background-color: black;")
        self._video_container.setMouseTracking(True)
        self._video_container.installEventFilter(self)

        self._canvas_stack = QStackedWidget(self._video_container)
        self._video_widget = VideoWidget(self._canvas_stack)
        self._youtube_widget = YouTubeWidget(self._canvas_stack)
        self._message_page = QWidget(self._canvas_stack)
        self._message_page.setStyleSheet("background-color: #000000;")
        self._message_page.setMouseTracking(True)
        message_layout = QVBoxLayout(self._message_page)
        message_layout.setContentsMargins(24, 24, 24, 24)
        self._message_label = QLabel(self._message_page)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message_label.setWordWrap(True)
        self._message_label.setStyleSheet(
            "color: white; font-size: 24px; background-color: #000000;"
        )
        message_layout.addWidget(self._message_label)
        self._canvas_stack.addWidget(self._video_widget)
        self._canvas_stack.addWidget(self._youtube_widget)
        self._canvas_stack.addWidget(self._message_page)
        self._canvas_stack.setCurrentWidget(self._video_widget)

        self._overlay = QLabel(self._video_container)
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._overlay.setStyleSheet(
            "background-color: rgba(0, 0, 0, 160); color: white;"
            " padding: 8px 16px; border-radius: 4px; font-size: 14px;"
        )
        self._overlay.hide()
        self._overlay_corner = "bottom-center"

        self._splitter.addWidget(self._library_panel)
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
            self._current_queue_item = None
            self._youtube_stopped = True
            self._controls.set_playing(False)
            self._update_queue_display()
            self._library_panel.clear_messages()
        self._hide_side_panel()
        self._overlay.hide()
        self._hide_status_message()
        self._update_history_display()
        self._stack.setCurrentWidget(self._empty_state)
        if self.isFullScreen():
            self.showNormal()
        self._apply_launch_window_geometry()
        self._sync_fullscreen_control()
        self._sync_controls_reveal_polling()

    def eventFilter(self, obj, event) -> bool:
        if (
            event.type() == QEvent.Type.Resize
            and obj is getattr(self, "_video_container", None)
        ):
            self._reposition_video_ui()
            if self._vlc is not None and self._media_mode == MediaSourceMode.LOCAL:
                QTimer.singleShot(0, self._vlc.bind_output)
        if (
            event.type() == QEvent.Type.MouseMove
            and obj
            in (
                self._video_container,
                self._controls,
                self._seek_bar,
            )
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
            and hasattr(self, "_library_panel")
            and self._list_visible
        ):
            QTimer.singleShot(0, self._rearm_panel_resize)
            QTimer.singleShot(100, self._rearm_panel_resize)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "_controls"):
            self._sync_fullscreen_control()
            if self._stack.currentWidget() == self._player_page:
                QTimer.singleShot(0, self._rearm_panel_resize)
                QTimer.singleShot(100, self._rearm_panel_resize)

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
        if self._list_visible and self._library_panel.isVisible():
            self._library_panel.raise_edge_grip()
            handle = self._splitter.handle(1)
            handle.raise_()
            handle.setCursor(Qt.CursorShape.SizeHorCursor)
        self._reposition_video_ui()
        if self._vlc is not None and self._media_mode == MediaSourceMode.LOCAL:
            self._vlc.bind_output()

    def _on_queue_split_changed(self, ratio: float) -> None:
        self._settings.queue_section_ratio = ratio
        self._settings.save()

    def _on_song_display_mode_changed(self, mode: str) -> None:
        self._settings.song_display_mode = mode
        self._settings.save()
        self._resort_by_display_name()

    def _on_song_display_format_changed(self, fmt: DisplayFormat) -> None:
        profile = self._settings.get_active_video_type()
        updated = profile.copy()
        updated.display_format = fmt.copy()
        self._settings.update_video_type(updated)
        self._settings.song_display_format = fmt.copy()
        self._settings.save()
        self._resort_by_display_name()

    def _on_append_karaoke_changed(self, checked: bool) -> None:
        self._settings.youtube_append_karaoke = checked
        self._settings.save()

    def _on_splitter_moved(self, _pos: int, _index: int) -> None:
        sizes = self._splitter.sizes()
        self._list_visible = sizes[0] > 0 and self._library_panel.isVisible()
        self._reposition_video_ui()
        if self._vlc is not None and self._media_mode == MediaSourceMode.LOCAL:
            QTimer.singleShot(0, self._vlc.bind_output)

    def _should_poll_controls_reveal(self) -> bool:
        return (
            self._settings.controls_auto_hide
            and not self._controls.isVisible()
            and self._stack.currentWidget() == self._player_page
        )

    def _sync_controls_reveal_polling(self) -> None:
        if self._should_poll_controls_reveal():
            self._controls_reveal_timer.start()
        else:
            self._controls_reveal_timer.stop()

    def _poll_controls_reveal(self) -> None:
        if not self._should_poll_controls_reveal():
            self._controls_reveal_timer.stop()
            return
        local = self.mapFromGlobal(QCursor.pos())
        if not self.rect().contains(local):
            return
        if local.y() >= self.height() - CONTROLS_REVEAL_HIT_HEIGHT:
            self._show_controls()

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
        self._message_page.setGeometry(0, 0, width, h)
        self._reposition_overlay()
        if self._list_visible:
            self._library_panel.raise_edge_grip()

    def _show_status_message(self, message: str) -> None:
        # Use a dedicated stack page (not an overlay on the native VLC HWND).
        # Windows cannot reliably composite/erase sibling text over VideoWidget.
        self._message_label.setText(message)
        self._canvas_stack.setCurrentWidget(self._message_page)

    def _hide_status_message(self) -> None:
        self._message_label.clear()
        if self._media_mode == MediaSourceMode.YOUTUBE:
            self._canvas_stack.setCurrentWidget(self._youtube_widget)
        else:
            self._canvas_stack.setCurrentWidget(self._video_widget)
            if (
                self._vlc is not None
                and self._stack.currentWidget() == self._player_page
            ):
                QTimer.singleShot(0, self._vlc.bind_output)

    def _show_audio_title(self, path: Path) -> None:
        """Show a persistent centered title while an audio file plays."""
        self._show_status_message(display_name(path))

    def _clear_audio_title(self) -> None:
        self._hide_status_message()

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
        if self._overlay_corner == "top-right":
            x = w - self._overlay.width() - margin
            y = margin
        else:
            x = (w - self._overlay.width()) // 2
            y = h - self._overlay.height() - margin
        self._overlay.move(max(margin, x), max(margin, y))

    def _reposition_controls(self) -> None:
        self._reposition_video_ui()

    def _active_side_panel(self) -> QWidget:
        return self._library_panel

    def _show_side_panel(self) -> None:
        self._list_visible = True
        self._library_panel.show()
        total = max(self._splitter.width(), PANEL_DEFAULT_WIDTH + 400)
        if self._saved_splitter_sizes and self._saved_splitter_sizes[0] > 0:
            self._splitter.setSizes(self._saved_splitter_sizes)
        else:
            self._splitter.setSizes([PANEL_DEFAULT_WIDTH, total - PANEL_DEFAULT_WIDTH])
        handle = self._splitter.handle(1)
        handle.raise_()
        handle.setCursor(Qt.CursorShape.SizeHorCursor)
        if self._media_mode == MediaSourceMode.LOCAL and self._playlist.paths:
            self._library_panel.set_current_index(self._playlist.index)
        self._library_panel.raise_edge_grip()

    def _show_song_list(self) -> None:
        self._show_side_panel()

    def _toggle_song_list(self) -> None:
        if self._stack.currentWidget() != self._player_page:
            return
        if self._list_visible:
            self._hide_side_panel()
        else:
            self._show_side_panel()

    def _hide_side_panel(self) -> None:
        sizes = self._splitter.sizes()
        if sizes[0] <= 0 and not self._library_panel.isVisible():
            return
        if sizes[0] > 0:
            self._saved_splitter_sizes = sizes
        self._list_visible = False
        total = sum(sizes) or self._splitter.width()
        self._splitter.setSizes([0, total])
        self._library_panel.hide()

    def _hide_song_list(self) -> None:
        self._hide_side_panel()

    def _hide_controls(self) -> None:
        if not self._settings.controls_auto_hide:
            return
        if self._seek_bar.is_scrubbing():
            self._controls_timer.start(CONTROLS_HIDE_MS)
            return
        self._seek_bar.hide()
        self._controls.hide()
        self._sync_controls_reveal_polling()
        self._reposition_video_ui()
        if self._vlc is not None and self._media_mode == MediaSourceMode.LOCAL:
            QTimer.singleShot(0, self._vlc.bind_output)

    def _on_controls_pin_toggled(self, pinned: bool) -> None:
        self._settings.controls_auto_hide = not pinned
        self._settings.save()
        if pinned:
            self._controls_timer.stop()
            self._show_controls()
        else:
            self._controls_timer.start(CONTROLS_HIDE_MS)

    def _raise_ui_layers(self) -> None:
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
        self._sync_controls_reveal_polling()
        self._reposition_video_ui()
        if self._vlc is not None and self._media_mode == MediaSourceMode.LOCAL:
            QTimer.singleShot(0, self._vlc.bind_output)
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
        start_dir = ""
        if self._browse_folder is not None:
            start_dir = str(self._browse_folder)
        elif self._folder is not None:
            start_dir = str(self._folder)
        folder = QFileDialog.getExistingDirectory(
            self, "Open Video Folder", start_dir
        )
        if folder:
            self._load_folder(Path(folder))

    def _load_folder(self, folder: Path, *, allow_empty: bool = False) -> None:
        folder = folder.resolve()
        if not folder.is_dir():
            QMessageBox.warning(self, "Invalid Folder", f"Not a directory:\n{folder}")
            return

        if not allow_empty and not folder_has_videos(folder):
            formats = ", ".join(MEDIA_EXTENSIONS)
            QMessageBox.information(
                self,
                "No Media Found",
                f"No supported media files found in:\n{folder}\n\n"
                f"Supported formats: {formats}",
            )
            return

        self._save_folder_state()
        youtube_active = (
            self._media_mode == MediaSourceMode.YOUTUBE
            and not self._youtube_stopped
            and self._current_youtube is not None
        )
        if not youtube_active:
            self._prepare_local_playback(stop_youtube=False)

        self._folder = folder
        self._browse_folder = folder
        self._recursive_list_mode = False
        self._folder_history.add(folder)
        self._refresh_recent_folders()
        self._library_panel.set_folder(folder)
        self._library_panel.set_library_root(folder)
        self._sort_strategy = SortStrategy.NAME_ASC

        paths = scan_videos(folder)
        self._library_paths = scan_videos(folder, recursive=True)
        subfolders = child_folders_with_videos(folder)
        self._raw_paths = paths
        sorted_paths = self._sort_paths(self._raw_paths)
        restored_index = self._restore_folder_current(sorted_paths) if sorted_paths else None
        self._playlist = Playlist(
            paths=sorted_paths,
            index=restored_index if restored_index is not None else 0,
        )
        if not youtube_active:
            self._stopped = True
            self._current_queue_item = None
            self._overlay.hide()
            self._hide_status_message()
        self._enter_player_page(tab="local")
        if not youtube_active:
            if not self._ensure_vlc():
                self._stack.setCurrentWidget(self._empty_state)
                self.showNormal()
                return
            self._vlc.stop()
            self._controls.set_playing(False)
        self._library_panel.set_sort_strategy(self._sort_strategy)
        self._restore_folder_queue(sorted_paths)
        self._library_panel.set_songs(
            sorted_paths,
            current_index=restored_index,
            subfolders=subfolders,
            can_navigate_up=False,
            recursive_list_mode=False,
        )
        self._update_queue_display()
        self._update_history_display()
        if not youtube_active:
            self._library_panel.set_active_tab("local")
        self._show_side_panel()
        self._show_controls()
        self._reposition_video_ui()
        if youtube_active:
            return
        if sorted_paths:
            QTimer.singleShot(0, self._show_ready_to_play)
        elif subfolders:
            QTimer.singleShot(
                0,
                lambda: self._show_status_message(
                    "Open a subfolder to find songs"
                ),
            )
        else:
            QTimer.singleShot(
                0,
                lambda: self._show_status_message(
                    "No downloads yet — use YouTube mode to download videos"
                ),
            )

    def _is_under_library_root(self, folder: Path) -> bool:
        if self._folder is None:
            return False
        try:
            folder.resolve().relative_to(self._folder.resolve())
            return True
        except (OSError, ValueError):
            return False

    def _can_navigate_up(self) -> bool:
        if self._folder is None or self._browse_folder is None:
            return False
        if self._recursive_list_mode:
            return False
        return self._browse_folder.resolve() != self._folder.resolve()

    def _apply_browse_contents(
        self,
        *,
        restore_queue: bool = False,
        clear_search: bool = True,
        keep_playback: bool = True,
    ) -> None:
        if self._browse_folder is None:
            return

        playing_path: Path | None = None
        if keep_playback and not self._stopped:
            playing_path = self._external_path or self._playlist.current()

        if self._recursive_list_mode:
            paths = scan_videos(self._browse_folder, recursive=True)
            subfolders: list[Path] = []
            can_up = False
        else:
            paths = scan_videos(self._browse_folder, recursive=False)
            subfolders = child_folders_with_videos(self._browse_folder)
            can_up = self._can_navigate_up()

        self._raw_paths = paths
        sorted_paths = self._sort_paths(self._raw_paths)
        old_paths = list(self._playlist.paths)

        if restore_queue:
            restored_index = (
                self._restore_folder_current(sorted_paths) if sorted_paths else None
            )
            self._playlist = Playlist(
                paths=sorted_paths,
                index=restored_index if restored_index is not None else 0,
            )
            self._restore_folder_queue(sorted_paths)
            current_index = restored_index
        else:
            keep_path = playing_path
            self._playlist.reorder(sorted_paths, keep_path=keep_path)
            if self._playlist.current() is None and sorted_paths:
                self._playlist.go_to(0)
            current_index = self._playlist.index if sorted_paths else None
            if playing_path is not None and not self._stopped:
                playing_index = self._playlist_index_for_path(playing_path)
                if playing_index is None:
                    self._external_path = playing_path
                    current_index = None
                else:
                    self._external_path = None
                    current_index = playing_index
                    self._playlist.go_to(playing_index)

        self._library_panel.set_folder(self._browse_folder)
        self._library_panel.set_songs(
            self._playlist.paths,
            current_index=current_index if self._external_path is None else None,
            clear_search=clear_search,
            subfolders=subfolders,
            can_navigate_up=can_up,
            recursive_list_mode=self._recursive_list_mode,
            label_root=self._browse_folder if self._recursive_list_mode else None,
        )
        self._update_queue_display()

    def _on_folder_entered(self, folder: Path) -> None:
        folder = folder.resolve()
        if not folder.is_dir() or not self._is_under_library_root(folder):
            return
        if not folder_has_videos(folder):
            self._show_toast("No videos in that folder")
            return
        self._browse_folder = folder
        self._recursive_list_mode = False
        self._apply_browse_contents(clear_search=True, keep_playback=True)

    def _on_navigate_up(self) -> None:
        if not self._can_navigate_up() or self._browse_folder is None:
            return
        parent = self._browse_folder.parent
        if not self._is_under_library_root(parent):
            return
        self._browse_folder = parent.resolve()
        self._recursive_list_mode = False
        self._apply_browse_contents(clear_search=True, keep_playback=True)

    def _on_play_all_requested(self) -> None:
        if self._browse_folder is None:
            return
        self._play_all_under(self._browse_folder)

    def _on_play_all_folder_requested(self, folder: Path) -> None:
        folder = folder.resolve()
        if not self._is_under_library_root(folder):
            return
        self._browse_folder = folder
        self._play_all_under(folder)

    def _play_all_under(self, folder: Path) -> None:
        paths = scan_videos(folder, recursive=True)
        if not paths:
            self._show_toast("No videos under that folder")
            return
        self._recursive_list_mode = True
        self._browse_folder = folder.resolve()
        self._raw_paths = paths
        sorted_paths = self._sort_paths(self._raw_paths)
        self._playlist = Playlist(paths=sorted_paths, index=0)
        self._library_panel.set_folder(self._browse_folder)
        self._library_panel.set_songs(
            sorted_paths,
            current_index=0,
            subfolders=[],
            can_navigate_up=False,
            recursive_list_mode=True,
            label_root=self._browse_folder,
        )
        self._update_queue_display(include_now_playing=False)
        if not self._ensure_vlc():
            return
        self._play_current(interrupt=True)

    def _on_queue_all_requested(self) -> None:
        if self._browse_folder is None:
            return
        self._queue_all_under(self._browse_folder)

    def _on_queue_all_folder_requested(self, folder: Path) -> None:
        self._queue_all_under(folder.resolve())

    def _queue_all_under(self, folder: Path) -> None:
        folder = folder.resolve()
        if not self._is_under_library_root(folder):
            return
        paths = self._sort_paths(scan_videos(folder, recursive=True))
        if not paths:
            self._show_toast("No videos under that folder")
            return
        queued = 0
        played_first = False
        for path in paths:
            item = QueueItem(kind="local", path=path)
            if self._is_idle() and not played_first:
                self._play_queue_item(item)
                played_first = True
                continue
            current = self._current_playing_queue_item()
            if current is not None and current.key() == item.key():
                continue
            if self._mixed_queue.contains(item):
                continue
            if self._mixed_queue.enqueue(item):
                queued += 1
        self._update_queue_display()
        if played_first and queued == 0:
            self._show_toast(f'Playing all under "{folder.name}"')
        elif queued:
            self._show_toast(
                f'Queued {queued} song{"s" if queued != 1 else ""} from "{folder.name}"'
            )
        else:
            self._show_toast("Those songs are already queued or playing")

    def _on_back_to_folders(self) -> None:
        if self._browse_folder is None:
            return
        self._recursive_list_mode = False
        self._apply_browse_contents(clear_search=True, keep_playback=True)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._vlc is not None:
            self._vlc.bind_output()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_launch_window_geometry()
        self._save_folder_state()
        super().closeEvent(event)

    def _show_toast(
        self,
        message: str,
        duration_ms: int = 4000,
        *,
        corner: str = "bottom-center",
    ) -> None:
        """Show a temporary overlay message."""
        self._overlay_corner = corner
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
        self._clear_audio_title()

    def _enter_player_page(self, *, tab: str = "local") -> None:
        self._stack.setCurrentWidget(self._player_page)
        self.showFullScreen()
        self._sync_fullscreen_control()
        QApplication.processEvents()
        self._library_panel.set_active_tab(tab)

    def _prepare_local_playback(self, *, stop_youtube: bool) -> None:
        if stop_youtube and self._youtube_player is not None:
            self._youtube_player.stop()
            self._current_youtube = None
            self._youtube_stopped = True
        self._media_mode = MediaSourceMode.LOCAL
        self._canvas_stack.setCurrentWidget(self._video_widget)
        self._controls.set_media_mode(MediaSourceMode.LOCAL)
        self._stack.setCurrentWidget(self._player_page)
        self.showFullScreen()
        self._sync_fullscreen_control()
        if self._vlc is not None:
            self._vlc.bind_output()
        self._reposition_video_ui()

    def _prepare_youtube_playback(self) -> None:
        self._freeze_local_playback()
        self._media_mode = MediaSourceMode.YOUTUBE
        self._canvas_stack.setCurrentWidget(self._youtube_widget)
        self._controls.set_media_mode(MediaSourceMode.YOUTUBE)
        self._stack.setCurrentWidget(self._player_page)
        self.showFullScreen()
        self._sync_fullscreen_control()

    def _enter_youtube_mode(self) -> None:
        self._prepare_youtube_playback()
        if not self._ensure_youtube():
            self._stack.setCurrentWidget(self._empty_state)
            self.showNormal()
            return
        self._show_side_panel()
        self._show_controls()
        self._apply_youtube_audio()
        self._update_history_display()
        self._reposition_video_ui()
        self._library_panel.focus_search(tab="youtube")
        self._show_status_message("Search for a karaoke song to play")

    def _current_playing_queue_item(self) -> QueueItem | None:
        if self._media_mode == MediaSourceMode.YOUTUBE:
            if not self._youtube_stopped and self._current_youtube is not None:
                return QueueItem(kind="youtube", video=self._current_youtube)
            return None
        if not self._stopped:
            path = self._external_path or self._playlist.current()
            if path is not None:
                return QueueItem(kind="local", path=path)
        return None

    def _update_history_display(self) -> None:
        current_local = None
        current_video_id = None
        if not self._stopped and self._media_mode == MediaSourceMode.LOCAL:
            current_local = self._external_path or self._playlist.current()
        elif not self._youtube_stopped and self._current_youtube is not None:
            current_video_id = self._current_youtube.video_id
        self._library_panel.set_history(
            self._play_history.entries(),
            current_local=current_local,
            current_video_id=current_video_id,
        )

    def _is_idle(self) -> bool:
        if self._media_mode == MediaSourceMode.YOUTUBE:
            return self._youtube_stopped and self._current_youtube is None
        return self._stopped and self._external_path is None

    def _enqueue_interrupted_playback(self, incoming: QueueItem) -> None:
        current = self._current_playing_queue_item()
        if current is not None and current.key() != incoming.key():
            if not self._mixed_queue.contains(current):
                self._mixed_queue.prepend(current)
        self._mixed_queue.remove(incoming)

    def _play_queue_item(self, item: QueueItem, *, interrupt: bool = False) -> None:
        if interrupt:
            self._enqueue_interrupted_playback(item)
        if item.kind == "youtube" and item.video is not None:
            self._play_youtube(item.video, interrupt=False)
            return
        if item.kind == "local" and item.path is not None:
            self._play_local_path(item.path, interrupt=False)

    def _queue_item(self, item: QueueItem) -> None:
        if self._mixed_queue.contains(item):
            self._show_toast("That item is already queued.")
            return
        current = self._current_playing_queue_item()
        if current is not None and current.key() == item.key():
            self._show_toast("That item is already playing.")
            return
        if self._is_idle():
            self._play_queue_item(item)
            return
        if self._mixed_queue.enqueue(item):
            self._update_queue_display()
            label = self._queue_item_label(item)
            self._show_toast(f'Queued "{label}"')

    def _queue_item_label(self, item: QueueItem) -> str:
        if item.kind == "youtube" and item.video is not None:
            return item.video.title
        if item.kind == "local" and item.path is not None:
            return display_name(item.path)
        return "item"

    def _on_queue_item_play_requested(self, item: QueueItem) -> None:
        self._play_queue_item(item, interrupt=True)

    def _on_queue_item_queue_requested(self, item: QueueItem) -> None:
        self._queue_item(item)

    def _on_remove_queue_item(self, item: QueueItem) -> None:
        current = self._current_playing_queue_item()
        removing_now_playing = current is not None and current.key() == item.key()
        self._mixed_queue.remove(item)
        if removing_now_playing:
            next_item = self._mixed_queue.dequeue()
            if next_item is not None:
                self._play_queue_item(next_item)
                return
            self._on_stop()
        self._update_queue_display()

    def _on_local_search_changed(self, query: str) -> None:
        if self._folder is None:
            return
        text = query.strip()
        if not text:
            self._apply_browse_contents(clear_search=True, keep_playback=True)
            return
        filtered = [
            path
            for path in self._library_paths
            if song_matches_query(
                path,
                text,
                mode=self._settings.song_display_mode,
                fmt=self._settings.song_display_format,
            )
        ]
        sorted_paths = self._sort_paths(filtered)
        self._library_panel.set_songs(
            sorted_paths,
            current_index=self._playlist.index if self._external_path is None else None,
            clear_search=False,
            subfolders=[],
            can_navigate_up=False,
            recursive_list_mode=True,
            label_root=self._folder,
        )

    def _play_youtube(self, video: YouTubeVideo, *, interrupt: bool = True) -> None:
        if not self._ensure_youtube():
            return
        incoming = QueueItem(kind="youtube", video=video)
        if interrupt:
            self._enqueue_interrupted_playback(incoming)
        self._prepare_youtube_playback()
        self._show_side_panel()
        self._current_youtube = video
        self._current_queue_item = QueueItem(kind="youtube", video=video)
        self._youtube_stopped = False
        self._message_label.clear()
        if self._mixed_queue.contains(self._current_queue_item):
            self._mixed_queue.remove(self._current_queue_item)
        self._youtube_player.play(
            video,
            volume=self._settings.volume,
            muted=self._settings.muted,
        )
        self._play_history.add_youtube(video)
        self._update_history_display()
        self._controls.set_playing(True)
        self._stop_seek_updates()
        self._update_queue_display()
        self._show_youtube_overlay()
        self._show_controls()
        self._raise_ui_layers()

    def _on_youtube_play_requested(self, video: YouTubeVideo) -> None:
        self._play_youtube(video)

    def _on_youtube_queue_requested(self, video: YouTubeVideo) -> None:
        self._queue_item(QueueItem(kind="youtube", video=video))

    def _show_youtube_overlay(self) -> None:
        if self._current_youtube is None:
            return
        text = self._current_youtube.title
        if self._mixed_queue:
            text += f"  ·  {len(self._mixed_queue)} queued"
        self._overlay_corner = "bottom-center"
        self._overlay.setText(text)
        self._overlay.show()
        self._overlay.raise_()
        self._reposition_overlay()
        self._overlay_timer.start(OVERLAY_HIDE_MS)

    def _advance_playback(self) -> bool:
        item = self._mixed_queue.dequeue()
        if item is not None:
            self._play_queue_item(item)
            return True
        if self._media_mode == MediaSourceMode.LOCAL and self._playlist.has_next():
            self._playlist.next()
            self._play_current()
            return True
        return False

    def _finish_youtube_playback(self) -> None:
        if self._youtube_stopped:
            return
        if not self._advance_playback():
            self._youtube_stopped = True
            self._current_youtube = None
            self._current_queue_item = None
            self._controls.set_playing(False)
            self._update_queue_display()
            self._update_history_display()
            self._show_status_message("Search for another song")

    def _on_youtube_end_reached(self) -> None:
        QTimer.singleShot(50, self._finish_youtube_playback)

    def _on_youtube_playback_error(self, message: str) -> None:
        logger.warning("YouTube playback error: %s", message)
        self._show_toast(message, duration_ms=5000)

    def _play_current(self, *, interrupt: bool = False) -> None:
        if self._vlc is None:
            return
        current = self._playlist.current()
        if current is None:
            self._show_end_of_playlist()
            return
        if interrupt:
            self._enqueue_interrupted_playback(QueueItem(kind="local", path=current))
        if not _is_playable_file(current):
            logger.warning("File not found, skipping: %s", current)
            self._show_toast(
                f'"{display_name(current)}" not found — try refreshing the song list',
                duration_ms=5000,
            )
            self._play_history.remove_local(current)
            self._update_history_display()
            QTimer.singleShot(0, self._advance_to_next_track)
            return
        self._prepare_local_playback(stop_youtube=True)
        self._stopped = False
        self._external_path = None
        self._current_youtube = None
        self._youtube_stopped = True
        self._current_queue_item = QueueItem(kind="local", path=current)
        if is_audio_file(current):
            self._show_audio_title(current)
        else:
            self._clear_audio_title()
        self._show_overlay()
        self._show_controls()
        self._vlc.play(current)
        self._controls.set_playing(True)
        self._play_history.add_local(current)
        self._update_history_display()
        self._apply_saved_audio()
        self._library_panel.set_current_index(self._playlist.index)
        self._update_queue_display()
        self._save_folder_state()
        self._start_seek_updates()
        self._raise_ui_layers()

    def _play_local_path(self, path: Path, *, interrupt: bool = True) -> None:
        if not self._ensure_vlc():
            return
        if not _is_playable_file(path):
            self._handle_missing_local_path(path)
            return
        incoming = QueueItem(kind="local", path=path)
        if interrupt:
            self._enqueue_interrupted_playback(incoming)
        self._prepare_local_playback(stop_youtube=True)
        index = self._playlist_index_for_path(path)
        if index is not None:
            self._playlist.go_to(index)
            self._play_current(interrupt=False)
            return
        self._stopped = False
        self._external_path = path
        self._current_youtube = None
        self._youtube_stopped = True
        self._current_queue_item = QueueItem(kind="local", path=path)
        if is_audio_file(path):
            self._show_audio_title(path)
        else:
            self._clear_audio_title()
        self._show_overlay_for_path(path)
        self._show_controls()
        self._vlc.play(path)
        self._controls.set_playing(True)
        self._play_history.add_local(path)
        self._update_history_display()
        self._apply_saved_audio()
        self._library_panel.clear_current_index()
        self._update_queue_display()
        self._start_seek_updates()
        self._raise_ui_layers()

    def _handle_missing_local_path(self, path: Path) -> None:
        self._show_toast(
            f'"{display_name(path)}" not found — removed from history',
            duration_ms=5000,
        )
        self._mixed_queue.remove_local(path)
        self._play_history.remove_local(path)
        self._update_history_display()
        self._update_queue_display()

    def _playlist_index_for_path(self, path: Path) -> int | None:
        resolved = _resolved_path(path)
        for index, playlist_path in enumerate(self._playlist.paths):
            if _resolved_path(playlist_path) == resolved:
                return index
        return None

    def _show_overlay_for_path(self, path: Path) -> None:
        text = display_name(path)
        if self._mixed_queue:
            text += f"  ·  {len(self._mixed_queue)} queued"
        self._overlay_corner = "bottom-center"
        self._overlay.setText(text)
        self._overlay.show()
        self._overlay.raise_()
        self._reposition_overlay()
        self._overlay_timer.start(OVERLAY_HIDE_MS)

    def _on_history_play_requested(self, entry: PlayHistoryEntry) -> None:
        if entry.kind == "local" and entry.path is not None:
            if not _is_playable_file(entry.path):
                self._handle_missing_local_path(entry.path)
                return
            self._play_local_path(entry.path)
            return
        if entry.kind == "youtube" and entry.video is not None:
            self._play_youtube(entry.video)

    def _on_history_queue_requested(self, entry: PlayHistoryEntry) -> None:
        if entry.kind == "local" and entry.path is not None:
            if not _is_playable_file(entry.path):
                self._handle_missing_local_path(entry.path)
                return
            self._queue_item(QueueItem(kind="local", path=entry.path))
            return
        if entry.kind == "youtube" and entry.video is not None:
            self._queue_item(QueueItem(kind="youtube", video=entry.video))

    def _on_play_next_requested(self, index: int) -> None:
        if index < 0 or index >= self._playlist.count:
            return
        path = self._playlist.paths[index]
        self._queue_item(QueueItem(kind="local", path=path))

    def _on_history_remove_requested(self, entry: PlayHistoryEntry) -> None:
        self._play_history.remove(entry)
        self._update_history_display()

    def _on_history_clear_requested(self) -> None:
        self._play_history.clear()
        self._update_history_display()

    def _on_youtube_download_requested(self, video: YouTubeVideo) -> None:
        if self._download_thread is not None and self._download_thread.isRunning():
            if self._downloading_video_id == video.video_id:
                return
            self._show_toast("A download is already in progress.", duration_ms=4000)
            return

        output_dir = self._youtube_downloads_path()
        output_dir.mkdir(parents=True, exist_ok=True)
        existing = downloaded_file_for(video.video_id, output_dir)
        if existing is not None:
            self._library_panel.show_download_success(
                video.title,
                message=f"Already downloaded: {existing.name}",
            )
            self._show_toast(
                f"Downloaded: {existing.name}",
                duration_ms=5000,
                corner="top-right",
            )
            return

        self._downloading_video_id = video.video_id
        self._downloading_video = video
        self._library_panel.show_downloading(video.title)
        self._download_thread, _worker = start_download(
            video=video,
            output_dir=output_dir,
            on_progress=self._on_youtube_download_progress,
            on_finished=self._on_youtube_download_finished,
            on_failed=self._on_youtube_download_failed,
            parent=self,
        )
        self._download_thread.finished.connect(self._on_youtube_download_thread_finished)

    def _on_youtube_download_progress(self, title: str, percent: float, status: str) -> None:
        self._library_panel.update_download_progress(title, percent, status)

    def _on_youtube_download_finished(self, path: Path, video: YouTubeVideo) -> None:
        self._folder_history.add(self._youtube_downloads_path())
        self._refresh_recent_folders()
        self._library_panel.show_download_success(
            video.title,
            message=f"Saved: {path.name}",
        )
        self._show_toast(
            f"Downloaded: {path.name}",
            duration_ms=5000,
            corner="top-right",
        )

    def _on_youtube_download_failed(self, video_id: str, message: str) -> None:
        title = self._downloading_video.title if self._downloading_video else video_id
        self._library_panel.show_download_error(title, message)
        self._show_toast(f"Download failed: {message}", duration_ms=6000)

    def _on_youtube_download_thread_finished(self) -> None:
        self._download_thread = None
        self._downloading_video_id = None
        self._downloading_video = None

    def _on_song_selected(self, index: int) -> None:
        if not self._ensure_vlc():
            return
        self._playlist.go_to(index)
        self._play_current(interrupt=True)

    def _on_startup_video_type_changed(self, profile: object) -> None:
        if not isinstance(profile, VideoTypeProfile):
            return
        self._settings.set_active_video_type_id(profile.id)
        self._settings.save()
        self._sync_library_video_type_label()
        self._sync_library_list_count_labels()
        self._sync_library_display_format()
        self._sync_ready_to_play_prompt()

    def _on_startup_video_types_changed(self, profiles: object) -> None:
        if not isinstance(profiles, list):
            return
        parsed = [item for item in profiles if isinstance(item, VideoTypeProfile)]
        if not parsed:
            return
        self._settings.video_types = parsed
        self._settings.set_active_video_type_id(
            self._startup_video_type_selector.active_id()
        )
        self._settings.save()
        self._sync_library_video_type_label()
        self._sync_library_list_count_labels()
        self._sync_library_display_format()
        self._sync_ready_to_play_prompt()

    def _sync_library_video_type_label(self) -> None:
        if not hasattr(self, "_library_panel"):
            return
        self._library_panel.set_active_video_type(
            self._settings.get_active_video_type().name
        )

    def _sync_library_display_format(self) -> None:
        if not hasattr(self, "_library_panel"):
            return
        profile = self._settings.get_active_video_type()
        self._library_panel.set_media_display_context(
            media_type_name=profile.name,
            field_labels=display_field_labels_from_mapping(
                profile.resolved_metadata_mapping(),
                rename_format=profile.rename_format,
            ),
            fmt=profile.resolved_display_format(),
        )

    def _sync_library_list_count_labels(self) -> None:
        if not hasattr(self, "_library_panel"):
            return
        self._library_panel.set_use_song_count_label(
            self._settings.active_video_type_id == BUILTIN_SONGS_ID
        )

    def _sync_startup_video_type_selector(self) -> None:
        if not hasattr(self, "_startup_video_type_selector"):
            return
        self._startup_video_type_selector.set_video_types(
            self._settings.video_types,
            active_id=self._settings.active_video_type_id,
        )

    def _apply_video_type_settings(
        self,
        *,
        video_types: list[VideoTypeProfile],
        active_video_type_id: str,
        rename_format=None,
        comment_slot_indices: list[int] | None = None,
    ) -> None:
        if not video_types:
            return
        self._settings.video_types = video_types
        self._settings.set_active_video_type_id(active_video_type_id)
        profile = self._settings.get_active_video_type()
        if rename_format is not None:
            profile.rename_format = rename_format
        if comment_slot_indices is not None:
            profile.metadata_comment_slot_indices = list(comment_slot_indices)
        self._settings.update_video_type(profile)
        self._sync_startup_video_type_selector()
        self._sync_library_video_type_label()
        self._sync_library_list_count_labels()
        self._sync_library_display_format()
        self._sync_ready_to_play_prompt()
        self._settings.save()

    def _open_video_types_manager(self) -> None:
        dialog = VideoTypesManagerDialog(
            video_types=self._settings.video_types,
            active_id=self._settings.active_video_type_id,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._apply_video_type_settings(
            video_types=dialog.video_types(),
            active_video_type_id=dialog.active_id(),
        )

    def _open_batch_rename_dialog(self) -> None:
        dialog = BatchRenameDialog(
            initial_folder=self._youtube_downloads_path(),
            video_types=self._settings.video_types,
            active_video_type_id=self._settings.active_video_type_id,
            skip_canonical=self._settings.filename_rename_skip_canonical,
            auto_fill_slots=self._settings.filename_rename_auto_fill_slots,
            parent=self,
        )
        dialog.file_renamed.connect(self._on_file_renamed)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_video_type_settings(
                video_types=dialog.video_types(),
                active_video_type_id=dialog.active_video_type_id(),
                rename_format=dialog.format(),
            )
            self._settings.filename_rename_skip_canonical = dialog.skip_canonical()
            self._settings.filename_rename_auto_fill_slots = dialog.auto_fill_slots()
            self._settings.save()

    def _open_batch_metadata_dialog(self) -> None:
        downloads = self._youtube_downloads_path()
        recent = [
            folder
            for folder in self._folder_history.folders()
            if folder.resolve() != downloads.resolve()
        ]
        dialog = BatchMetadataDialog(
            initial_folder=downloads,
            recent_folders=recent,
            pinned_folders=[downloads],
            video_types=self._settings.video_types,
            active_video_type_id=self._settings.active_video_type_id,
            skip_tagged=self._settings.metadata_skip_tagged,
            auto_fill_slots=self._settings.metadata_auto_fill_slots,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_video_type_settings(
                video_types=dialog.video_types(),
                active_video_type_id=dialog.active_video_type_id(),
                rename_format=dialog.format(),
            )
            self._settings.metadata_skip_tagged = dialog.skip_tagged()
            self._settings.metadata_auto_fill_slots = dialog.auto_fill_slots()
            self._settings.save()

    def _on_rename_requested(self, index: int) -> None:
        if index < 0 or index >= len(self._playlist.paths):
            return
        path = self._playlist.paths[index]
        dialog = RenameFileDialog(
            path,
            fmt=self._settings.filename_rename_format,
            show_format_config=True,
            rename_button_label="Rename",
            video_types=self._settings.video_types,
            active_video_type_id=self._settings.active_video_type_id,
            parent=self,
        )
        self.raise_()
        self.activateWindow()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_types = dialog.video_types()
            active_id = dialog.active_video_type_id()
            if updated_types is not None and active_id is not None:
                self._apply_video_type_settings(
                    video_types=updated_types,
                    active_video_type_id=active_id,
                    rename_format=dialog.format(),
                )
            else:
                self._settings.filename_rename_format = dialog.format()
                self._settings.save()
            if dialog.result_value() == RenameResult.RENAMED:
                new_path = dialog.new_path()
                if new_path is not None:
                    self._on_file_renamed(path, new_path)

    def _on_edit_metadata_requested(self, path: object) -> None:
        if not isinstance(path, Path):
            return
        profile = self._settings.get_active_video_type()
        dialog = EditMetadataDialog(
            path,
            fmt=profile.rename_format,
            metadata_field_mapping=profile.resolved_metadata_mapping(),
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._library_panel.refresh_display_labels()

    def _on_file_renamed(self, old_path: Path, new_path: Path) -> None:
        old_resolved = _resolved_path(old_path)

        def matches_old(path: Path) -> bool:
            return _resolved_path(path) == old_resolved

        def remap(path: Path) -> Path:
            return new_path if matches_old(path) else path

        self._raw_paths = [remap(path) for path in self._raw_paths]
        self._library_paths = [remap(path) for path in self._library_paths]

        if self._folder is not None:
            queue = self._folder_queues.get_queue(self._folder)
            current = self._folder_queues.get_current(self._folder)
            updated_queue = [remap(path) for path in queue]
            updated_current = (
                new_path
                if current is not None and matches_old(current)
                else current
            )
            self._folder_queues.set(
                self._folder,
                queue=updated_queue,
                current=updated_current,
            )

        self._mixed_queue.rename_local(old_path, new_path)

        if self._external_path is not None and matches_old(self._external_path):
            self._external_path = new_path

        if (
            self._current_queue_item is not None
            and self._current_queue_item.kind == "local"
            and self._current_queue_item.path is not None
            and matches_old(self._current_queue_item.path)
        ):
            self._current_queue_item = QueueItem(kind="local", path=new_path)

        self._play_history.rename_local(old_path, new_path)

        playlist_updated = any(matches_old(path) for path in self._playlist.paths)
        if playlist_updated:
            current = self._playlist.current()
            keep_path = (
                new_path
                if current is not None and matches_old(current)
                else current
            )
            updated_paths = [remap(path) for path in self._playlist.paths]
            sorted_paths = self._sort_paths(updated_paths)
            self._playlist.reorder(sorted_paths, keep_path=keep_path)
            subfolders = (
                []
                if self._recursive_list_mode or self._browse_folder is None
                else child_folders_with_videos(self._browse_folder)
            )
            self._library_panel.set_songs(
                self._playlist.paths,
                current_index=self._playlist.index,
                clear_search=False,
                subfolders=subfolders,
                can_navigate_up=self._can_navigate_up(),
                recursive_list_mode=self._recursive_list_mode,
                label_root=self._browse_folder if self._recursive_list_mode else None,
            )

        search_text = self._library_panel.local_search_text().strip()
        if search_text:
            self._on_local_search_changed(search_text)
        elif (
            not playlist_updated
            and self._recursive_list_mode
            and self._browse_folder is not None
            and any(matches_old(path) for path in self._raw_paths)
        ):
            sorted_paths = self._sort_paths(self._raw_paths)
            self._library_panel.set_songs(
                sorted_paths,
                current_index=self._playlist.index if self._external_path is None else None,
                clear_search=False,
                subfolders=[],
                can_navigate_up=False,
                recursive_list_mode=True,
                label_root=self._browse_folder,
            )

        self._update_queue_display()
        self._update_history_display()

        if not self._stopped and self._media_mode == MediaSourceMode.LOCAL:
            playing = self._external_path or self._playlist.current()
            if playing is not None and _resolved_path(playing) == _resolved_path(new_path):
                if self._external_path is not None:
                    self._show_overlay_for_path(new_path)
                else:
                    self._show_overlay()

    def _sort_paths(
        self,
        paths: list[Path],
        strategy: SortStrategy | None = None,
    ) -> list[Path]:
        return sort_paths(
            paths,
            strategy if strategy is not None else self._sort_strategy,
            name_key=self._library_panel.display_sort_key,
        )

    def _resort_by_display_name(self) -> None:
        if self._sort_strategy not in {SortStrategy.NAME_ASC, SortStrategy.NAME_DESC}:
            return
        self._apply_current_sort()

    def _apply_current_sort(self) -> None:
        query = self._library_panel.local_search_text()
        if query:
            self._on_local_search_changed(query)
            return
        if not self._raw_paths:
            return
        current = self._playlist.current()
        sorted_paths = self._sort_paths(self._raw_paths)
        self._playlist.reorder(sorted_paths, keep_path=current)
        subfolders = (
            []
            if self._recursive_list_mode or self._browse_folder is None
            else child_folders_with_videos(self._browse_folder)
        )
        self._library_panel.set_songs(
            self._playlist.paths,
            current_index=self._playlist.index,
            clear_search=False,
            subfolders=subfolders,
            can_navigate_up=self._can_navigate_up(),
            recursive_list_mode=self._recursive_list_mode,
            label_root=self._browse_folder if self._recursive_list_mode else None,
        )
        self._update_queue_display()

    def _on_sort_changed(self, strategy: SortStrategy) -> None:
        self._sort_strategy = strategy
        self._apply_current_sort()

    def _refresh_song_list(self) -> None:
        if self._browse_folder is None:
            return

        keep_path = self._external_path or self._playlist.current()
        if self._recursive_list_mode:
            paths = scan_videos(self._browse_folder, recursive=True)
            subfolders: list[Path] = []
        else:
            paths = scan_videos(self._browse_folder, recursive=False)
            subfolders = child_folders_with_videos(self._browse_folder)

        if not paths and not subfolders:
            QMessageBox.information(
                self,
                "No Videos Found",
                f"No supported video files found in:\n{self._browse_folder}",
            )
            return

        if self._folder is not None:
            self._library_paths = scan_videos(self._folder, recursive=True)
        self._raw_paths = paths
        sorted_paths = self._sort_paths(self._raw_paths)
        self._playlist.reorder(sorted_paths, keep_path=keep_path)

        highlight: int | None = None
        if not self._stopped:
            if self._external_path is not None:
                highlight = self._playlist_index_for_path(self._external_path)
            else:
                highlight = self._playlist.index

        self._library_panel.set_songs(
            self._playlist.paths,
            current_index=highlight,
            clear_search=False,
            subfolders=subfolders,
            can_navigate_up=self._can_navigate_up(),
            recursive_list_mode=self._recursive_list_mode,
            label_root=self._browse_folder if self._recursive_list_mode else None,
        )
        self._update_queue_display()

    def _show_overlay(self) -> None:
        current = self._playlist.current()
        if current is None:
            return
        text = f"{self._playlist.position} / {self._playlist.count} — {display_name(current)}"
        if self._mixed_queue:
            text += f"  ·  {len(self._mixed_queue)} queued"
        self._overlay_corner = "bottom-center"
        self._overlay.setText(text)
        self._overlay.show()
        self._overlay.raise_()
        self._reposition_overlay()
        self._overlay_timer.start(OVERLAY_HIDE_MS)

    def _hide_overlay(self) -> None:
        self._overlay.hide()

    def _show_ready_to_play(self) -> None:
        if self._settings.active_video_type_id == BUILTIN_SONGS_ID:
            message = "Select a song to play"
        else:
            message = "Select a video or audio to play"
        self._show_status_message(message)

    def _sync_ready_to_play_prompt(self) -> None:
        """Refresh the idle prompt when the active media type changes."""
        if not self._is_idle():
            return
        if self._media_mode != MediaSourceMode.LOCAL:
            return
        if self._canvas_stack.currentWidget() != self._message_page:
            return
        current = self._message_label.text().strip()
        ready_messages = {
            "Select a song to play",
            "Select a video or audio to play",
        }
        if current not in ready_messages:
            return
        self._show_ready_to_play()

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

    def _advance_to_next_track(self) -> bool:
        """Play the next queued item or the next playlist track."""
        if self._stopped:
            return False
        if self._advance_playback():
            return True
        self._show_end_of_playlist()
        return False

    def _on_playback_error(self, message: str) -> None:
        logger.warning("Playback error: %s", message)
        if self._advance_to_next_track():
            return
        QMessageBox.warning(
            self,
            "Playback Error",
            f"{message}\n\nNo more tracks in the playlist.",
        )

    def _on_clear_queue(self) -> None:
        self._mixed_queue.clear()
        self._current_queue_item = None
        if not self._stopped or not self._youtube_stopped:
            self._on_stop()
        self._library_panel.clear_current_index()
        self._update_queue_display()

    def _on_queue_reordered(self, items: list[QueueItem]) -> None:
        self._mixed_queue.set_order(items)
        self._update_queue_display()

    def _update_queue_display(self, *, include_now_playing: bool | None = None) -> None:
        del include_now_playing
        current = self._current_playing_queue_item()
        queued = list(self._mixed_queue.items())
        self._library_panel.set_queue_state(current=current, queued=queued)
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
        valid_paths: list[Path] = []
        for saved_path in saved_paths:
            try:
                resolved = saved_path.resolve()
            except OSError:
                continue
            if resolved.is_file():
                valid_paths.append(resolved)
        self._mixed_queue.clear()
        for path in valid_paths:
            self._mixed_queue.enqueue_local(path)
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
            item.path
            for item in self._mixed_queue.items()
            if item.kind == "local" and item.path is not None
        ]
        current: Path | None = None
        playing_index = self._library_panel.playing_index()
        if playing_index is not None and 0 <= playing_index < len(self._playlist.paths):
            current = self._playlist.paths[playing_index]
        elif self._external_path is not None:
            current = self._external_path
        self._folder_queues.set(self._folder, queue=queue, current=current)

    def _on_play(self) -> None:
        if self._media_mode == MediaSourceMode.YOUTUBE:
            return
        if self._vlc is None:
            return
        if self._stopped or self._playlist.current() is None:
            if self._stopped and self._mixed_queue:
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
            self._youtube_stopped = True
            self._current_youtube = None
            self._current_queue_item = None
            if self._youtube_player is not None:
                self._youtube_player.stop()
            self._controls.set_playing(False)
            self._update_queue_display()
            self._update_history_display()
            self._show_status_message("Search for another song")
            self._show_controls()
            return
        self._stopped = True
        self._external_path = None
        self._current_queue_item = None
        if self._vlc is not None:
            self._vlc.stop()
        self._controls.set_playing(False)
        self._stop_seek_updates()
        self._seek_bar.reset()
        self._clear_audio_title()
        self._update_queue_display()
        self._update_history_display()
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
            if not self._advance_playback():
                self._finish_youtube_playback()
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
                self._library_panel.focus_search(tab="youtube")
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
            app = QApplication.instance()
            if app is not None and (
                app.activeModalWidget() is not None or app.activePopupWidget() is not None
            ):
                super().keyPressEvent(event)
                return
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
