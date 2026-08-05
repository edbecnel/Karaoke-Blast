"""Visual editor for filename format configuration."""

from __future__ import annotations

from PyQt6 import sip
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.ui.checkbox_style import CHECKBOX_STYLE_WHITE_LABEL
from karaoke_blast.utils.filename_rename import (
    DEFAULT_KARAOKE_FORMAT,
    SLOT_KIND_ADDITIONAL,
    SLOT_KIND_ARTIST,
    SLOT_KIND_SONG,
    SONG_ARTIST_FORMAT,
    FilenameFormat,
    format_preview,
)

_FIELD_STYLE = """
QLineEdit {
    background-color: #2d2d42;
    color: #ffffff;
    border: 1px solid #5a5a72;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
"""

_BUTTON_STYLE = """
QPushButton {
    background-color: #2d2d42;
    color: white;
    border: 1px solid #5a5a72;
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #3a3a52;
    border-color: #7a7a92;
}
QPushButton:disabled {
    color: #666;
    border-color: #3a3a52;
}
"""

_BADGE_STYLE = "color: #aaa; font-size: 11px; background: transparent;"
_LABEL_STYLE = "color: white; font-size: 12px; font-weight: 600; background: transparent;"
_PREVIEW_STYLE = "color: #7ee787; font-size: 12px; background: transparent;"
_SEP_LABEL_STYLE = "color: #888; font-size: 11px; background: transparent;"


def _kind_label(kind: str) -> str:
    if kind == SLOT_KIND_SONG:
        return "Song"
    if kind == SLOT_KIND_ARTIST:
        return "Artist"
    return "Additional"


class FormatConfigWidget(QWidget):
    """Configure four reorderable slots and separators for filename composition."""

    format_changed = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._format = DEFAULT_KARAOKE_FORMAT.copy()
        self._building = False
        self._slot_rows_layout = QVBoxLayout()
        self._slot_rows_layout.setSpacing(4)
        self._separator_fields: list[QLineEdit] = []
        self._label_fields: dict[int, QLineEdit] = {}
        self._hint_fields: dict[int, QLineEdit] = {}
        self._hint_fixed_boxes: dict[int, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Format")
        title.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        layout.addWidget(title)

        layout.addLayout(self._slot_rows_layout)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        karaoke_btn = QPushButton("Karaoke standard")
        karaoke_btn.setStyleSheet(_BUTTON_STYLE)
        karaoke_btn.clicked.connect(self._apply_karaoke_preset)
        preset_row.addWidget(karaoke_btn)

        song_artist_btn = QPushButton("Song + Artist only")
        song_artist_btn.setStyleSheet(_BUTTON_STYLE)
        song_artist_btn.clicked.connect(self._apply_song_artist_preset)
        preset_row.addWidget(song_artist_btn)
        preset_row.addStretch()
        layout.addLayout(preset_row)

        self._preview_label = QLabel()
        self._preview_label.setStyleSheet(_PREVIEW_STYLE)
        self._preview_label.setWordWrap(True)
        layout.addWidget(self._preview_label)

        self.set_format(self._format)

    def format(self) -> FilenameFormat:
        self._sync_from_fields()
        return self._format.copy()

    def set_format(self, fmt: FilenameFormat) -> None:
        self._building = True
        self._format = fmt.copy()
        self._rebuild_rows()
        self._update_preview()
        self._building = False

    def _clear_layout(self, box_layout: QVBoxLayout) -> None:
        while box_layout.count():
            item = box_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                sip.delete(widget)

    def _rebuild_rows(self) -> None:
        self._clear_layout(self._slot_rows_layout)
        self._separator_fields.clear()
        self._label_fields.clear()
        self._hint_fields.clear()
        self._hint_fixed_boxes.clear()

        for index, slot in enumerate(self._format.slots):
            if index > 0:
                sep_row = QHBoxLayout()
                sep_label = QLabel("Separator")
                sep_label.setStyleSheet(_SEP_LABEL_STYLE)
                sep_field = QLineEdit()
                sep_field.setFixedHeight(28)
                sep_field.setMaximumWidth(120)
                sep_field.setStyleSheet(_FIELD_STYLE)
                sep_field.setText(self._format.separators[index - 1])
                sep_field.textChanged.connect(self._on_field_changed)
                sep_row.addWidget(sep_label)
                sep_row.addWidget(sep_field)
                sep_row.addStretch()
                sep_container = QWidget()
                sep_container.setLayout(sep_row)
                self._slot_rows_layout.addWidget(sep_container)
                self._separator_fields.append(sep_field)

            row = QHBoxLayout()
            row.setSpacing(8)

            enabled_box = QCheckBox()
            enabled_box.setStyleSheet(CHECKBOX_STYLE_WHITE_LABEL)
            enabled_box.setChecked(slot.enabled)
            enabled_box.setEnabled(slot.kind != SLOT_KIND_SONG)
            enabled_box.setToolTip("Include this slot in the format")
            enabled_box.toggled.connect(
                lambda checked, slot_index=index: self._on_slot_enabled(slot_index, checked)
            )
            row.addWidget(enabled_box)

            badge = QLabel(_kind_label(slot.kind))
            badge.setFixedWidth(72)
            badge.setStyleSheet(_BADGE_STYLE)
            row.addWidget(badge)

            if slot.kind == SLOT_KIND_ADDITIONAL:
                label_field = QLineEdit(slot.label)
                label_field.setStyleSheet(_FIELD_STYLE)
                label_field.setPlaceholderText("Slot label")
                label_field.textChanged.connect(self._on_field_changed)
                self._label_fields[index] = label_field
                row.addWidget(label_field, 1)

                hint_field = QLineEdit(slot.hint)
                hint_field.setStyleSheet(_FIELD_STYLE)
                hint_field.setPlaceholderText("Hint or default value")
                hint_field.textChanged.connect(self._on_field_changed)
                self._hint_fields[index] = hint_field
                row.addWidget(hint_field, 1)

                fixed_box = QCheckBox("Fixed")
                fixed_box.setStyleSheet(CHECKBOX_STYLE_WHITE_LABEL)
                fixed_box.setChecked(slot.hint_fixed)
                fixed_box.setToolTip("Pre-fill this value when renaming; it can still be changed per file")
                fixed_box.toggled.connect(self._on_field_changed)
                self._hint_fixed_boxes[index] = fixed_box
                row.addWidget(fixed_box)
            else:
                fixed_label = QLabel(slot.label)
                fixed_label.setStyleSheet(_LABEL_STYLE)
                row.addWidget(fixed_label, 1)

            up_btn = QPushButton("↑")
            up_btn.setFixedSize(28, 28)
            up_btn.setStyleSheet(_BUTTON_STYLE)
            up_btn.setEnabled(index > 0)
            up_btn.setToolTip("Move slot up")
            up_btn.clicked.connect(lambda _checked=False, slot_index=index: self._move_slot(slot_index, -1))
            row.addWidget(up_btn)

            down_btn = QPushButton("↓")
            down_btn.setFixedSize(28, 28)
            down_btn.setStyleSheet(_BUTTON_STYLE)
            down_btn.setEnabled(index < len(self._format.slots) - 1)
            down_btn.setToolTip("Move slot down")
            down_btn.clicked.connect(lambda _checked=False, slot_index=index: self._move_slot(slot_index, 1))
            row.addWidget(down_btn)

            container = QWidget()
            container.setLayout(row)
            self._slot_rows_layout.addWidget(container)

    def _on_slot_enabled(self, index: int, checked: bool) -> None:
        if self._building:
            return
        self._sync_from_fields()
        slot = self._format.slots[index]
        if slot.kind != SLOT_KIND_SONG:
            slot.enabled = checked
        self._rebuild_rows()
        self._update_preview()
        self.format_changed.emit(self.format())

    def _move_slot(self, index: int, direction: int) -> None:
        new_index = index + direction
        if not (0 <= new_index < len(self._format.slots)):
            return
        self._sync_from_fields()
        slots = self._format.slots
        slots[index], slots[new_index] = slots[new_index], slots[index]
        self._rebuild_rows()
        self._update_preview()
        self.format_changed.emit(self.format())

    def _apply_karaoke_preset(self) -> None:
        self.set_format(DEFAULT_KARAOKE_FORMAT.copy())
        self.format_changed.emit(self.format())

    def _apply_song_artist_preset(self) -> None:
        self.set_format(SONG_ARTIST_FORMAT.copy())
        self.format_changed.emit(self.format())

    def _on_field_changed(self, *_args) -> None:
        if self._building:
            return
        self._sync_from_fields()
        self._update_preview()
        self.format_changed.emit(self.format())

    def _sync_from_fields(self) -> None:
        for index, sep_field in enumerate(self._separator_fields):
            if index < len(self._format.separators):
                self._format.separators[index] = sep_field.text()

        for index, label_field in self._label_fields.items():
            self._format.slots[index].label = label_field.text().strip() or "Additional"

        for index, hint_field in self._hint_fields.items():
            self._format.slots[index].hint = hint_field.text().strip()

        for index, fixed_box in self._hint_fixed_boxes.items():
            self._format.slots[index].hint_fixed = fixed_box.isChecked()

    def _update_preview(self) -> None:
        self._preview_label.setText(f"Pattern: {format_preview(self._format)}")
