"""Line edit with optional trimming of leading and trailing spaces."""

from __future__ import annotations

from PyQt6.QtWidgets import QLineEdit


class VisibleSpaceLineEdit(QLineEdit):
    """QLineEdit that can strip leading and trailing spaces when editing finishes."""

    def __init__(self, *, trim_edges: bool = True, parent=None) -> None:
        super().__init__(parent)
        self._trim_edges = trim_edges
        if trim_edges:
            self.editingFinished.connect(self._trim_edges_on_finish)

    def _trim_edges_on_finish(self) -> None:
        if not self._trim_edges:
            return
        trimmed = self.text().strip()
        if trimmed != self.text():
            self.setText(trimmed)
