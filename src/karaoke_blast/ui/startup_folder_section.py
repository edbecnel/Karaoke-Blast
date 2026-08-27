"""Open and browse controls for the startup screen folder."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

_OPEN_BTN_STYLE = (
    "QPushButton { background: #e94560; color: white; border: none;"
    " border-radius: 8px; font-size: 16px; font-weight: bold; }"
    "QPushButton:hover { background: #ff6b81; }"
)

_PATH_FIELD_STYLE = (
    "QLabel { background-color: #2d2d42; color: #ffffff; border: 1px solid #5a5a72;"
    " border-radius: 4px; padding: 6px 10px; font-size: 16px; min-height: 20px; }"
)
_PATH_FIELD_MUTED_STYLE = (
    "QLabel { background-color: #2d2d42; color: #888; border: 1px solid #5a5a72;"
    " border-radius: 4px; padding: 6px 10px; font-size: 16px; min-height: 20px; }"
)
_BROWSE_BTN_STYLE = (
    "QPushButton { background-color: #2d2d42; color: white; border: 1px solid #5a5a72;"
    " border-radius: 4px; padding: 6px 10px; font-size: 16px; min-height: 20px; }"
    "QPushButton:hover { background-color: #3a3a52; border-color: #7a7a92; }"
)


class StartupFolderSection(QWidget):
    """Open button and folder path row for the startup screen."""

    open_clicked = pyqtSignal()
    browse_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._folder: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._open_btn = QPushButton("Open")
        self._open_btn.setFixedSize(180, 48)
        self._open_btn.setStyleSheet(_OPEN_BTN_STYLE)
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.clicked.connect(self.open_clicked.emit)
        layout.addWidget(self._open_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(8)

        self._path_label = QLabel("")
        self._path_label.setStyleSheet(_PATH_FIELD_STYLE)
        self._path_label.setMinimumWidth(360)
        self._path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        path_row.addWidget(self._path_label, 1)

        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.setStyleSheet(_BROWSE_BTN_STYLE)
        self._browse_btn.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self._browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._browse_btn.clicked.connect(self.browse_clicked.emit)
        path_row.addWidget(self._browse_btn)

        layout.addLayout(path_row)

    def set_folder(self, folder: Path | None) -> None:
        self._folder = folder.resolve() if folder is not None else None
        if self._folder is None:
            self._path_label.setText("Not set")
            self._path_label.setToolTip("")
            self._path_label.setStyleSheet(_PATH_FIELD_MUTED_STYLE)
            self._open_btn.setEnabled(False)
            return

        resolved = str(self._folder)
        self._path_label.setToolTip(resolved)
        metrics = self._path_label.fontMetrics()
        available = max(self._path_label.width(), 360)
        self._path_label.setText(
            metrics.elidedText(resolved, Qt.TextElideMode.ElideMiddle, available)
        )
        exists = self._folder.is_dir()
        self._open_btn.setEnabled(exists)
        self._path_label.setStyleSheet(
            _PATH_FIELD_STYLE if exists else _PATH_FIELD_MUTED_STYLE
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
