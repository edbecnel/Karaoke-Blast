"""Compact folder history list for use inside QMenu dropdowns."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QMenu

from karaoke_blast.ui.context_menu_style import CONTEXT_MENU_STYLE
from karaoke_blast.ui.list_style import LIST_ITEM_INTERACTION_STYLE

_ROLE_FOLDER = Qt.ItemDataRole.UserRole

_LIST_STYLE = (
    """
QListWidget {
    background-color: #1e1e2e;
    color: #ffffff;
    border: none;
    font-size: 12px;
    outline: none;
}
QListWidget::item {
    padding: 6px 12px;
}
"""
    + LIST_ITEM_INTERACTION_STYLE
)

_ROW_HEIGHT = 28
_MAX_VISIBLE_ROWS = 10
_MIN_WIDTH = 240


class FolderHistoryListWidget(QListWidget):
    """Folder history rows with right-click remove, safe inside QMenu popups."""

    folder_selected = pyqtSignal(object)
    folder_remove_requested = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet(_LIST_STYLE)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemClicked.connect(self._on_item_clicked)

    def set_folders(
        self,
        folders: list[Path],
        *,
        current: Path | None = None,
    ) -> None:
        self.clear()
        current_resolved = current.resolve() if current is not None else None
        for folder in folders:
            item = QListWidgetItem(folder.name)
            item.setData(_ROLE_FOLDER, str(folder.resolve()))
            item.setToolTip(str(folder.resolve()))
            if current_resolved is not None and folder.resolve() == current_resolved:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.addItem(item)

        visible_rows = max(1, min(len(folders), _MAX_VISIBLE_ROWS))
        self.setFixedHeight(visible_rows * _ROW_HEIGHT + 4)
        self.setMinimumWidth(_MIN_WIDTH)

    def _folder_from_item(self, item: QListWidgetItem | None) -> Path | None:
        if item is None:
            return None
        value = item.data(_ROLE_FOLDER)
        if not isinstance(value, str) or not value:
            return None
        return Path(value)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        folder = self._folder_from_item(item)
        if folder is None:
            return
        self.folder_selected.emit(folder)

    def _show_context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        folder = self._folder_from_item(item)
        if folder is None:
            return
        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)
        remove = QAction("Remove from history", menu)
        remove.triggered.connect(
            lambda _checked=False, selected=folder: self.folder_remove_requested.emit(
                selected
            )
        )
        menu.addAction(remove)
        menu.exec(self.mapToGlobal(pos))
