"""Recent folders list on the startup screen."""

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.ui.list_style import RECENT_FOLDERS_LIST_STYLE

PINNED_LABEL = "YouTube Downloads"


class RecentFoldersPanel(QWidget):
    """Shows pinned and recently opened folders for quick selection."""

    folder_selected = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._heading = QLabel("Folders")
        self._heading.setStyleSheet("color: #ccc; font-size: 14px; font-weight: bold;")
        self._heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._heading)

        self._list = QListWidget()
        self._list.setStyleSheet(RECENT_FOLDERS_LIST_STYLE)
        self._list.setMaximumWidth(520)
        self._list.setMinimumHeight(120)
        self._list.setMaximumHeight(280)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_folders(
        self,
        folders: list[Path],
        *,
        pinned: list[Path] | None = None,
    ) -> None:
        self._list.clear()
        pinned_paths = pinned or []
        pinned_resolved = {path.resolve() for path in pinned_paths}
        recent = [folder for folder in folders if folder.resolve() not in pinned_resolved]

        if not pinned_paths and not recent:
            self.hide()
            return

        for folder in pinned_paths:
            item = QListWidgetItem(PINNED_LABEL)
            item.setData(Qt.ItemDataRole.UserRole, folder)
            item.setToolTip(str(folder))
            self._list.addItem(item)

        for folder in recent:
            item = QListWidgetItem(folder.name)
            item.setData(Qt.ItemDataRole.UserRole, folder)
            item.setToolTip(str(folder))
            self._list.addItem(item)

        self.show()

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        folder = item.data(Qt.ItemDataRole.UserRole)
        if folder is not None:
            self.folder_selected.emit(folder)
