"""Download progress and status display for the YouTube sidebar."""

from __future__ import annotations

import html
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

_DISMISS_BTN_STYLE = (
    "QPushButton { background: transparent; color: #aaa; border: none;"
    " font-size: 16px; border-radius: 4px; }"
    "QPushButton:hover { background: rgba(255,255,255,30); color: white; }"
)

_SUCCESS_LINK_STYLE = "color: #7ee787; font-size: 11px; text-decoration: underline;"


class YouTubeDownloadStatus(QWidget):
    """Shows download progress, success, or failure in the YouTube panel."""

    cancel_requested = pyqtSignal()
    open_saved_requested = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_downloading = False
        self._saved_path: Path | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        header_row = QHBoxLayout()
        header_row.setSpacing(4)
        self._title_label = QLabel("")
        self._title_label.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
        self._title_label.setWordWrap(True)
        header_row.addWidget(self._title_label, 1)

        self._close_btn = QPushButton("×")
        self._close_btn.setToolTip("Cancel download")
        self._close_btn.setFixedSize(24, 24)
        self._close_btn.setStyleSheet(_DISMISS_BTN_STYLE)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self._on_close_clicked)
        self._close_btn.hide()
        header_row.addWidget(self._close_btn)
        layout.addLayout(header_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setTextVisible(True)
        self._progress.setStyleSheet(
            "QProgressBar {"
            " background-color: #2d2d42; border: 1px solid #5a5a72;"
            " border-radius: 4px; color: white; font-size: 11px; text-align: center;"
            "}"
            "QProgressBar::chunk { background-color: #e94560; border-radius: 3px; }"
        )
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #aaa; font-size: 11px;")
        self._status_label.setWordWrap(True)
        self._status_label.setOpenExternalLinks(False)
        self._status_label.linkActivated.connect(self._on_status_link_activated)
        layout.addWidget(self._status_label)

        self.hide()

    def show_downloading(self, title: str, *, percent: float = 0.0, status: str = "Downloading…") -> None:
        self._is_downloading = True
        self._saved_path = None
        self._title_label.setText(title)
        self._title_label.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
        self._close_btn.setToolTip("Cancel download")
        self._close_btn.show()
        self._progress.setValue(int(percent))
        self._progress.show()
        self._status_label.setTextFormat(Qt.TextFormat.PlainText)
        self._status_label.setText(status)
        self._status_label.setStyleSheet("color: #aaa; font-size: 11px;")
        self._status_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.show()

    def update_progress(self, title: str, percent: float, status: str) -> None:
        self._title_label.setText(title)
        self._progress.setValue(int(percent))
        self._status_label.setText(status)

    def show_cancelling(self) -> None:
        self._status_label.setText("Cancelling…")

    def show_success(
        self,
        title: str,
        *,
        message: str = "Download complete",
        path: Path | None = None,
    ) -> None:
        self._is_downloading = False
        self._saved_path = path
        self._title_label.setText(title)
        self._title_label.setStyleSheet("color: #7ee787; font-size: 12px; font-weight: bold;")
        self._progress.hide()
        if path is not None:
            safe_message = html.escape(message)
            self._status_label.setTextFormat(Qt.TextFormat.RichText)
            self._status_label.setText(
                f'<a href="open" style="{_SUCCESS_LINK_STYLE}">{safe_message}</a>'
            )
            self._status_label.setToolTip("Show in local library")
            self._status_label.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self._status_label.setTextFormat(Qt.TextFormat.PlainText)
            self._status_label.setText(message)
            self._status_label.setToolTip("")
            self._status_label.setCursor(Qt.CursorShape.ArrowCursor)
        self._status_label.setStyleSheet("color: #7ee787; font-size: 11px;")
        self._close_btn.setToolTip("Dismiss")
        self._close_btn.show()
        self.show()

    def show_error(self, title: str, message: str) -> None:
        self._is_downloading = False
        self._saved_path = None
        self._title_label.setText(title)
        self._title_label.setStyleSheet("color: #ff6b81; font-size: 12px; font-weight: bold;")
        self._progress.hide()
        self._status_label.setTextFormat(Qt.TextFormat.PlainText)
        self._status_label.setText(message)
        self._status_label.setStyleSheet("color: #ff6b81; font-size: 11px;")
        self._status_label.setToolTip("")
        self._status_label.setCursor(Qt.CursorShape.ArrowCursor)
        self._close_btn.setToolTip("Dismiss")
        self._close_btn.show()
        self.show()

    def _on_status_link_activated(self, _link: str) -> None:
        if self._saved_path is not None:
            self.open_saved_requested.emit(self._saved_path)

    def _on_close_clicked(self) -> None:
        if self._is_downloading:
            self.cancel_requested.emit()
            return
        self.reset()

    def reset(self) -> None:
        self._is_downloading = False
        self._saved_path = None
        self._title_label.clear()
        self._progress.setValue(0)
        self._progress.show()
        self._status_label.clear()
        self._status_label.setTextFormat(Qt.TextFormat.PlainText)
        self._status_label.setStyleSheet("color: #aaa; font-size: 11px;")
        self._status_label.setToolTip("")
        self._status_label.setCursor(Qt.CursorShape.ArrowCursor)
        self._close_btn.hide()
        self.hide()
