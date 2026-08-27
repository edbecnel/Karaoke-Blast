"""Row showing the YouTube downloads folder with a change button."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy, QWidget

from karaoke_blast.ui.context_menu_style import CONTEXT_MENU_STYLE, copy_text_to_clipboard
from karaoke_blast.ui.library_folder_menu import (
    HistoryFolderMenu,
    populate_downloads_folder_menu,
)

_LABEL_STYLE = "color: #aaa; font-size: 12px;"
_FOLDER_BTN_STYLE = """
QPushButton {
    background: transparent;
    color: #ccc;
    border: none;
    font-size: 12px;
    font-weight: normal;
    text-align: left;
    padding: 0 22px 0 0;
    border-radius: 4px;
}
QPushButton:hover {
    background: rgba(255, 255, 255, 30);
}
QPushButton::menu-indicator {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 12px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #ccc;
    margin-right: 4px;
}
"""


class YouTubeDownloadsFolderRow(QWidget):
    """Displays the current download folder and emits when the user wants to change it."""

    browse_clicked = pyqtSignal()
    use_current_folder_clicked = pyqtSignal()
    downloads_folder_selected = pyqtSignal(object)
    downloads_folder_remove_requested = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None, *, sidebar: bool = True) -> None:
        super().__init__(parent)
        self._current_library_folder: Path | None = None
        self._download_folder: Path | None = None
        self._folder_name = ""
        self._downloads_history: list[Path] = []

        layout = QHBoxLayout(self)
        if sidebar:
            layout.setContentsMargins(12, 4, 12, 8)
        else:
            layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        label = QLabel("Download folder: ")
        label.setStyleSheet(_LABEL_STYLE)
        layout.addWidget(label)

        self._folder_btn = QPushButton("")
        self._folder_btn.setStyleSheet(_FOLDER_BTN_STYLE)
        self._folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._folder_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._change_menu = HistoryFolderMenu(self)
        self._change_menu.setStyleSheet(CONTEXT_MENU_STYLE)
        self._change_menu.folder_remove_requested.connect(
            self.downloads_folder_remove_requested.emit
        )
        self._change_menu.aboutToShow.connect(self._populate_change_menu)
        self._folder_btn.setMenu(self._change_menu)
        self._folder_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._folder_btn.customContextMenuRequested.connect(self._show_copy_path_menu)
        layout.addWidget(self._folder_btn, 1)

    def set_downloads_history(self, folders: list[Path]) -> None:
        self._downloads_history = list(folders)

    def set_folder(self, path: Path) -> None:
        self._download_folder = path.resolve()
        resolved = str(self._download_folder)
        self._folder_name = self._download_folder.name or resolved
        self._folder_btn.setToolTip(resolved)
        self._update_folder_btn_text()

    def set_current_library_folder(self, folder: Path | None) -> None:
        self._current_library_folder = folder.resolve() if folder is not None else None

    def _update_folder_btn_text(self) -> None:
        if not self._folder_name:
            self._folder_btn.setText("")
            return
        metrics = self._folder_btn.fontMetrics()
        available = max(self._folder_btn.width(), 1)
        self._folder_btn.setText(
            metrics.elidedText(self._folder_name, Qt.TextElideMode.ElideMiddle, available)
        )

    def _show_copy_path_menu(self, pos) -> None:
        if self._download_folder is None:
            return
        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)
        copy_path = QAction("Copy path to clipboard", self)
        copy_path.triggered.connect(self._copy_download_folder_path)
        menu.addAction(copy_path)
        menu.exec(self._folder_btn.mapToGlobal(pos))

    def _copy_download_folder_path(self) -> None:
        if self._download_folder is None:
            return
        copy_text_to_clipboard(str(self._download_folder))

    def _use_current_label(self) -> tuple[str, bool]:
        folder = self._current_library_folder
        if folder is None:
            return "Use current folder", False
        if self._download_folder is not None and folder == self._download_folder:
            return "Use current folder (already selected)", False
        return "Use current folder", True

    def _populate_change_menu(self) -> None:
        label, enabled = self._use_current_label()
        populate_downloads_folder_menu(
            self._change_menu,
            current=self._download_folder,
            history_folders=self._downloads_history,
            on_folder_selected=self.downloads_folder_selected.emit,
            on_use_current=self.use_current_folder_clicked.emit,
            on_browse=self.browse_clicked.emit,
            use_current_enabled=enabled,
            use_current_label=label,
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._folder_name:
            self._update_folder_btn_text()
