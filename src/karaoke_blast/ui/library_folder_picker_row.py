"""Row widget for picking a library folder from pinned/recent lists."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMenu, QPushButton, QWidget

from karaoke_blast.ui.context_menu_style import CONTEXT_MENU_STYLE
from karaoke_blast.ui.library_folder_menu import populate_library_folder_menu
from karaoke_blast.ui.visible_space_field import VisibleSpaceLineEdit

_FIELD_STYLE = """
QLineEdit {
    background-color: #2d2d42;
    color: #ffffff;
    border: 1px solid #5a5a72;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
}
QLineEdit:disabled {
    color: #ccc;
    background-color: #252536;
}
"""

_BUTTON_STYLE = """
QPushButton {
    background-color: #2d2d42;
    color: white;
    border: 1px solid #5a5a72;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #3a3a52;
    border-color: #7a7a92;
}
"""


class LibraryFolderPickerRow(QWidget):
    """Read-only path field with a Choose menu for library folders."""

    folder_changed = pyqtSignal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        recent_folders: list[Path] | None = None,
        pinned_folders: list[Path] | None = None,
        pinned_folder_label: str | None = None,
        on_folder_browsed: Callable[[Path], None] | None = None,
        initial_folder: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._recent_folders = list(recent_folders or [])
        self._pinned_folders = list(pinned_folders or [])
        self._pinned_folder_label = pinned_folder_label
        self._on_folder_browsed = on_folder_browsed
        self._folder: Path | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._path_field = VisibleSpaceLineEdit()
        self._path_field.setReadOnly(True)
        self._path_field.setStyleSheet(_FIELD_STYLE)
        self._path_field.setPlaceholderText("Not set")
        layout.addWidget(self._path_field, 1)

        self._choose_btn = QPushButton("Choose…")
        self._choose_btn.setStyleSheet(_BUTTON_STYLE)
        self._choose_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._choose_btn.clicked.connect(self._show_folder_menu)
        layout.addWidget(self._choose_btn)

        self.set_folder(initial_folder)

    def set_folder_lists(
        self,
        *,
        recent_folders: list[Path],
        pinned_folders: list[Path],
        pinned_folder_label: str | None,
    ) -> None:
        self._recent_folders = list(recent_folders)
        self._pinned_folders = list(pinned_folders)
        self._pinned_folder_label = pinned_folder_label

    def folder(self) -> Path | None:
        return self._folder

    def set_folder(self, folder: Path | None) -> None:
        self._folder = folder.resolve() if folder is not None else None
        if self._folder is None:
            self._path_field.clear()
            self._path_field.setToolTip("")
            return
        resolved = str(self._folder)
        self._path_field.setText(resolved)
        self._path_field.setToolTip(resolved)

    def _show_folder_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)
        populate_library_folder_menu(
            menu,
            current=self._folder,
            recent_folders=self._recent_folders,
            pinned_folders=self._pinned_folders,
            pinned_folder_label=self._pinned_folder_label,
            on_folder_selected=self._select_folder,
            on_browse=self._browse_folder,
        )
        menu.exec(
            self._choose_btn.mapToGlobal(self._choose_btn.rect().bottomLeft())
        )

    def _select_folder(self, folder: Path) -> None:
        self.set_folder(folder)
        self.folder_changed.emit(folder)

    def _browse_folder(self) -> None:
        start_dir = str(self._folder) if self._folder is not None else str(Path.home())
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Library Folder",
            start_dir,
        )
        if not selected:
            return
        folder = Path(selected)
        if not folder.is_dir():
            return
        if self._on_folder_browsed is not None:
            self._on_folder_browsed(folder)
        self._select_folder(folder)
