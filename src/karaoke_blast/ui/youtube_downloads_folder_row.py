"""Row showing the YouTube downloads folder with a change button."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

_LABEL_STYLE = "color: #aaa; font-size: 11px;"
_PATH_STYLE = "color: #ccc; font-size: 11px;"
_BTN_STYLE = (
    "QPushButton { background-color: #2d2d42; color: white; border: 1px solid #5a5a72;"
    " border-radius: 4px; padding: 4px 10px; font-size: 11px; }"
    "QPushButton:hover { background-color: #3a3a52; border-color: #7a7a92; }"
)


class YouTubeDownloadsFolderRow(QWidget):
    """Displays the current download folder and emits when the user wants to change it."""

    browse_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None, *, sidebar: bool = True) -> None:
        super().__init__(parent)
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

        change_btn = QPushButton("Change…")
        change_btn.setStyleSheet(_BTN_STYLE)
        change_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        change_btn.clicked.connect(self.browse_clicked.emit)
        layout.addWidget(change_btn)

    def set_folder(self, path: Path) -> None:
        resolved = str(path.resolve())
        self._path_label.setToolTip(resolved)
        metrics = self._path_label.fontMetrics()
        available = max(self._path_label.width(), 160)
        self._path_label.setText(
            metrics.elidedText(resolved, Qt.TextElideMode.ElideMiddle, available)
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        tooltip = self._path_label.toolTip()
        if tooltip:
            metrics = self._path_label.fontMetrics()
            available = max(self._path_label.width(), 1)
            self._path_label.setText(
                metrics.elidedText(tooltip, Qt.TextElideMode.ElideMiddle, available)
            )
