"""Recent folders list on the startup screen."""

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.ui.context_menu_style import CONTEXT_MENU_STYLE, copy_text_to_clipboard
from karaoke_blast.ui.list_style import RECENT_FOLDERS_LIST_STYLE
from karaoke_blast.utils.file_manager import open_folder_in_file_manager

PINNED_LABEL = "YouTube Downloads"

_ROLE_FOLDER = Qt.ItemDataRole.UserRole
_ROLE_PINNED = Qt.ItemDataRole.UserRole + 1


class RecentFoldersPanel(QWidget):
    """Shows pinned and recently opened folders for quick selection."""

    folder_selected = pyqtSignal(object)
    folder_remove_requested = pyqtSignal(object)

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
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._list, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_folders(
        self,
        folders: list[Path],
        *,
        pinned: list[Path] | None = None,
        pinned_label: str | None = None,
    ) -> None:
        self._list.clear()
        pinned_paths = pinned or []
        pinned_resolved = {path.resolve() for path in pinned_paths}
        recent = [folder for folder in folders if folder.resolve() not in pinned_resolved]
        label = pinned_label or PINNED_LABEL

        if not pinned_paths and not recent:
            self.hide()
            return

        for folder in pinned_paths:
            item = QListWidgetItem(label)
            item.setData(_ROLE_FOLDER, folder)
            item.setData(_ROLE_PINNED, True)
            item.setToolTip(str(folder))
            self._list.addItem(item)

        for folder in recent:
            item = QListWidgetItem(folder.name)
            item.setData(_ROLE_FOLDER, folder)
            item.setData(_ROLE_PINNED, False)
            item.setToolTip(str(folder))
            self._list.addItem(item)

        self.show()

    def _folder_from_item(self, item: QListWidgetItem | None) -> Path | None:
        if item is None:
            return None
        folder = item.data(_ROLE_FOLDER)
        return folder if isinstance(folder, Path) else None

    def _is_pinned_item(self, item: QListWidgetItem) -> bool:
        return bool(item.data(_ROLE_PINNED))

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        folder = self._folder_from_item(item)
        if folder is not None:
            self.folder_selected.emit(folder)

    def _open_folder_in_file_manager(self, folder: Path) -> None:
        if not open_folder_in_file_manager(folder):
            QMessageBox.warning(
                self,
                "Folder Not Found",
                f"The folder no longer exists:\n{folder}",
            )

    def _show_context_menu(self, pos) -> None:
        item = self._list.itemAt(pos)
        folder = self._folder_from_item(item)
        if folder is None:
            return

        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

        browse_folder = QAction("Browse folder", self)
        browse_folder.triggered.connect(
            lambda _checked=False, selected=folder: self._open_folder_in_file_manager(
                selected
            )
        )
        menu.addAction(browse_folder)

        copy_path = QAction("Copy path to clipboard", self)
        copy_path.triggered.connect(
            lambda _checked=False, selected=folder: copy_text_to_clipboard(str(selected))
        )
        menu.addAction(copy_path)

        if not self._is_pinned_item(item):
            menu.addSeparator()
            remove = QAction("Remove from List", self)
            remove.triggered.connect(
                lambda _checked=False, selected=folder: self.folder_remove_requested.emit(
                    selected
                )
            )
            menu.addAction(remove)

        menu.exec(self._list.mapToGlobal(pos))
