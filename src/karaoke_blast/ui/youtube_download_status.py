"""Download progress and status display for the YouTube sidebar."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class YouTubeDownloadStatus(QWidget):
    """Shows download progress, success, or failure in the YouTube panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        self._title_label = QLabel("")
        self._title_label.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
        self._title_label.setWordWrap(True)
        layout.addWidget(self._title_label)

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
        layout.addWidget(self._status_label)

        self.hide()

    def show_downloading(self, title: str, *, percent: float = 0.0, status: str = "Downloading…") -> None:
        self._title_label.setText(title)
        self._title_label.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
        self._progress.setValue(int(percent))
        self._progress.show()
        self._status_label.setText(status)
        self._status_label.setStyleSheet("color: #aaa; font-size: 11px;")
        self.show()

    def update_progress(self, title: str, percent: float, status: str) -> None:
        self._title_label.setText(title)
        self._progress.setValue(int(percent))
        self._status_label.setText(status)

    def show_success(self, title: str, *, message: str = "Download complete") -> None:
        self._title_label.setText(title)
        self._title_label.setStyleSheet("color: #7ee787; font-size: 12px; font-weight: bold;")
        self._progress.hide()
        self._status_label.setText(message)
        self._status_label.setStyleSheet("color: #7ee787; font-size: 11px;")
        self.show()

    def show_error(self, title: str, message: str) -> None:
        self._title_label.setText(title)
        self._title_label.setStyleSheet("color: #ff6b81; font-size: 12px; font-weight: bold;")
        self._progress.hide()
        self._status_label.setText(message)
        self._status_label.setStyleSheet("color: #ff6b81; font-size: 11px;")
        self.show()

    def reset(self) -> None:
        self._title_label.clear()
        self._progress.setValue(0)
        self._progress.show()
        self._status_label.clear()
        self.hide()
