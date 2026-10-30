"""Background FLV remux for macOS compatibility mode."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal, pyqtSlot

from karaoke_blast.services.flv_compat import (
    FlvCompatCancelled,
    FlvCompatError,
    FlvCompatProbeError,
    FlvCompatRemuxError,
    FlvCompatUnsupported,
    remux_flv_to_cache,
)
from karaoke_blast.utils.runtime_deps import configure_runtime_dependencies

logger = logging.getLogger(__name__)


class FlvPrepareWorker(QObject):
    """Remux one FLV off the UI thread."""

    finished = pyqtSignal(object, object)
    failed = pyqtSignal(object, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._source = None
        self._cancel_requested = False

    def prepare(self, source) -> None:
        self._source = source
        self._cancel_requested = False

    @pyqtSlot()
    def request_cancel(self) -> None:
        self._cancel_requested = True

    @pyqtSlot()
    def run(self) -> None:
        source = self._source
        if source is None:
            return
        try:
            configure_runtime_dependencies()
            playback_path = remux_flv_to_cache(
                source,
                is_cancelled=lambda: self._cancel_requested,
            )
        except FlvCompatCancelled:
            return
        except FlvCompatUnsupported as exc:
            self.failed.emit(source, str(exc))
            return
        except FlvCompatProbeError as exc:
            self.failed.emit(source, str(exc))
            return
        except FlvCompatRemuxError as exc:
            self.failed.emit(source, str(exc))
            return
        except FlvCompatError as exc:
            logger.warning("FLV prepare failed for %s: %s", source, exc)
            self.failed.emit(source, str(exc))
            return
        except OSError as exc:
            logger.warning("FLV prepare failed for %s: %s", source, exc)
            self.failed.emit(source, f"Could not prepare FLV: {exc}")
            return
        self.finished.emit(playback_path, source)


def start_flv_prepare(
    *,
    source,
    on_finished,
    on_failed,
    parent: QObject | None = None,
) -> tuple[QThread, FlvPrepareWorker]:
    thread = QThread(parent)
    worker = FlvPrepareWorker()
    worker.prepare(source)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(on_finished, Qt.ConnectionType.QueuedConnection)
    worker.failed.connect(on_failed, Qt.ConnectionType.QueuedConnection)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    worker.failed.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread, worker
