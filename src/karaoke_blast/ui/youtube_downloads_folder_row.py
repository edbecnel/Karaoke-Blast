"""Row showing the YouTube downloads folder with a change button."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy, QWidget

from karaoke_blast.ui.context_menu_style import CONTEXT_MENU_STYLE

_LABEL_STYLE = "color: #aaa; font-size: 11px;"
_PATH_STYLE = "color: #ccc; font-size: 11px;"
_BTN_STYLE = (
    "QPushButton { background-color: #2d2d42; color: white; border: 1px solid #5a5a72;"
    " border-radius: 4px; padding: 4px 10px; font-size: 11px; }"
    "QPushButton:hover { background-color: #3a3a52; border-color: #7a7a92; }"
    "QPushButton::menu-indicator { image: none; width: 0px; }"
)


class YouTubeDownloadsFolderRow(QWidget):
    """Displays the current download folder and emits when the user wants to change it."""

    browse_clicked = pyqtSignal()
    use_current_folder_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None, *, sidebar: bool = True) -> None:
        super().__init__(parent)
        self._current_library_folder: Path | None = None
        self._download_folder: Path | None = None

        layout = QHBoxLayout(self)
        if sidebar:
            layout.setContentsMargins(12, 4, 12, 8)
        else:
            layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        label = QLabel("Download folder:")
        label.setStyleSheet(_LABEL_STYLE)
        layout.addWidget(label)

        self._path_label = QLabel("")
        self._path_label.setStyleSheet(_PATH_STYLE)
        self._path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._path_label.setMinimumWidth(0)
        layout.addWidget(self._path_label, 1)

        self._change_menu = QMenu(self)
        self._change_menu.setStyleSheet(CONTEXT_MENU_STYLE)
        self._use_current_action = QAction("Use current folder", self)
        self._browse_action = QAction("Browse…", self)
        self._change_menu.addAction(self._use_current_action)
        self._change_menu.addSeparator()
        self._change_menu.addAction(self._browse_action)
        self._change_menu.aboutToShow.connect(self._refresh_change_menu)
        self._use_current_action.triggered.connect(self.use_current_folder_clicked.emit)
        self._browse_action.triggered.connect(self.browse_clicked.emit)

        change_btn = QPushButton("Change…")
        change_btn.setStyleSheet(_BTN_STYLE)
        change_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        change_btn.setMenu(self._change_menu)
        layout.addWidget(change_btn)

    def set_folder(self, path: Path) -> None:
        self._download_folder = path.resolve()
        resolved = str(self._download_folder)
        self._path_label.setToolTip(resolved)
        metrics = self._path_label.fontMetrics()
        available = max(self._path_label.width(), 160)
        self._path_label.setText(
            metrics.elidedText(resolved, Qt.TextElideMode.ElideMiddle, available)
        )

    def set_current_library_folder(self, folder: Path | None) -> None:
        self._current_library_folder = folder.resolve() if folder is not None else None

    def _refresh_change_menu(self) -> None:
        folder = self._current_library_folder
        if folder is None:
            self._use_current_action.setEnabled(False)
            self._use_current_action.setText("Use current folder")
            self._use_current_action.setStatusTip("")
            return
        if self._download_folder is not None and folder == self._download_folder:
            self._use_current_action.setEnabled(False)
            self._use_current_action.setText("Use current folder (already selected)")
            self._use_current_action.setStatusTip(str(folder))
            return
        self._use_current_action.setEnabled(True)
        self._use_current_action.setText("Use current folder")
        self._use_current_action.setStatusTip(str(folder))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        tooltip = self._path_label.toolTip()
        if tooltip:
            metrics = self._path_label.fontMetrics()
            available = max(self._path_label.width(), 1)
            self._path_label.setText(
                metrics.elidedText(tooltip, Qt.TextElideMode.ElideMiddle, available)
            )
