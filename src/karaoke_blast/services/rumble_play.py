"""Prepare Rumble videos for embed playback off the UI thread."""

from __future__ import annotations

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal, pyqtSlot

from karaoke_blast.models.rumble_video import RumbleVideo
from karaoke_blast.services.rumble_metadata import enrich_rumble_video
from karaoke_blast.utils.runtime_deps import configure_runtime_dependencies


class RumblePrepareWorker(QObject):
    ready = pyqtSignal(object, object)
    failed = pyqtSignal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._video: RumbleVideo | None = None

    def prepare(self, video: RumbleVideo) -> None:
        self._video = video

    @pyqtSlot()
    def run(self) -> None:
        video = self._video
        if video is None:
            return
        try:
            configure_runtime_dependencies()
            enriched = enrich_rumble_video(video)
        except Exception as exc:
            self.failed.emit(video.page_url, str(exc))
            return
        self.ready.emit(enriched, video)


def start_rumble_prepare(
    *,
    video: RumbleVideo,
    on_ready,
    on_failed,
    parent: QObject | None = None,
) -> tuple[QThread, RumblePrepareWorker]:
    thread = QThread(parent)
    worker = RumblePrepareWorker()
    worker.prepare(video)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.ready.connect(on_ready, Qt.ConnectionType.QueuedConnection)
    worker.failed.connect(on_failed, Qt.ConnectionType.QueuedConnection)
    worker.ready.connect(thread.quit)
    worker.failed.connect(thread.quit)
    worker.ready.connect(worker.deleteLater)
    worker.failed.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread, worker
