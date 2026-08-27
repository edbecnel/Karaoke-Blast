"""Row showing a media type's default library folder with an open action."""

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
    "QPushButton:disabled { color: #666; border-color: #3a3a52; }"
)


class MediaTypeLibraryFolderRow(QWidget):
    """Displays the active media type's default library folder."""

    open_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._folder: Path | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        self._label = QLabel("Library folder:")
        self._label.setStyleSheet(_LABEL_STYLE)
        layout.addWidget(self._label)

        self._path_label = QLabel("")
        self._path_label.setStyleSheet(_PATH_STYLE)
        self._path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._path_label.setMinimumWidth(0)
        layout.addWidget(self._path_label, 1)

        self._open_btn = QPushButton("Open")
        self._open_btn.setStyleSheet(_BTN_STYLE)
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.clicked.connect(self.open_clicked.emit)
        layout.addWidget(self._open_btn)

    def set_media_type_name(self, name: str) -> None:
        self._label.setText(f"{name} folder:")

    def set_folder(self, folder: Path | None) -> None:
        self._folder = folder.resolve() if folder is not None else None
        if self._folder is None:
            self._path_label.setText("Not set yet")
            self._path_label.setToolTip("")
            self._open_btn.setEnabled(False)
            self.hide()
            return

        resolved = str(self._folder)
        self._path_label.setToolTip(resolved)
        metrics = self._path_label.fontMetrics()
        available = max(self._path_label.width(), 160)
        self._path_label.setText(
            metrics.elidedText(resolved, Qt.TextElideMode.ElideMiddle, available)
        )
        exists = self._folder.is_dir()
        self._open_btn.setEnabled(exists)
        self._path_label.setStyleSheet(
            _PATH_STYLE if exists else "color: #888; font-size: 11px;"
        )
        self.show()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        tooltip = self._path_label.toolTip()
        if tooltip:
            metrics = self._path_label.fontMetrics()
            available = max(self._path_label.width(), 1)
            self._path_label.setText(
                metrics.elidedText(tooltip, Qt.TextElideMode.ElideMiddle, available)
            )
