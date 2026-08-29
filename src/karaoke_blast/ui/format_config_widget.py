"""Visual editor for filename format configuration."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.ui.checkbox_style import CHECKBOX_STYLE_WHITE_LABEL
from karaoke_blast.ui.visible_space_field import VisibleSpaceLineEdit
from karaoke_blast.utils.filename_rename import (
    CASING_MODES,
    CASING_NONE,
    CASING_TITLE,
    CASING_UPPER,
    SLOT_KIND_ADDITIONAL,
    SLOT_KIND_ARTIST,
    SLOT_KIND_SONG,
    SLOT_KINDS,
    DEFAULT_KARAOKE_FORMAT,
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

_PREVIEW_STYLE = "color: #7ee787; font-size: 12px; background: transparent;"
_SEP_LABEL_STYLE = "color: #888; font-size: 11px; background: transparent;"
_CASING_LABEL_STYLE = "color: #888; font-size: 11px; background: transparent;"

_COMBO_STYLE = """
QComboBox {
    background-color: #2d2d42;
    color: #ffffff;
    border: 1px solid #5a5a72;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
QComboBox:hover {
    border-color: #7a7a92;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #ffffff;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    color: #ffffff;
    border: 1px solid #5a5a72;
    selection-background-color: #e94560;
    selection-color: #ffffff;
    outline: none;
}
"""

_CASING_OPTIONS: tuple[tuple[str, str], ...] = (
    (CASING_NONE, "None"),
    (CASING_TITLE, "Title Case"),
    (CASING_UPPER, "ALL CAPS"),
)


class FormatConfigWidget(QWidget):
    """Configure four reorderable slots and separators for filename composition."""

    format_changed = pyqtSignal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        external_options: bool = False,
    ) -> None:
        super().__init__(parent)
        self._external_options = external_options
        self._format = DEFAULT_KARAOKE_FORMAT.copy()
        self._building = False
        self._slot_rows_layout = QVBoxLayout()
        self._slot_rows_layout.setSpacing(4)
        self._separator_fields: list[VisibleSpaceLineEdit] = []
        self._label_fields: dict[int, VisibleSpaceLineEdit] = {}
        self._hint_fields: dict[int, VisibleSpaceLineEdit] = {}
        self._hint_fixed_boxes: dict[int, QCheckBox] = {}
        self._casing_combos: dict[str, QComboBox] = {}
        self._casing_kind_labels: dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Format")
        title.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        layout.addWidget(title)

        layout.addLayout(self._slot_rows_layout)

        self._options_section = QWidget()
        options_layout = QVBoxLayout(self._options_section)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(8)

        casing_title = QLabel("Casing")
        casing_title.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        options_layout.addWidget(casing_title)

        casing_row = QHBoxLayout()
        casing_row.setSpacing(12)
        for kind in SLOT_KINDS:
            kind_col = QHBoxLayout()
            kind_col.setSpacing(6)
            kind_label = QLabel()
            kind_label.setStyleSheet(_CASING_LABEL_STYLE)
            self._casing_kind_labels[kind] = kind_label
            kind_col.addWidget(kind_label)
            combo = QComboBox()
            combo.setStyleSheet(_COMBO_STYLE)
            combo.setFixedWidth(120)
            for mode, label in _CASING_OPTIONS:
                combo.addItem(label, mode)
            combo.activated.connect(self._on_field_changed)
            self._casing_combos[kind] = combo
            kind_col.addWidget(combo)
            casing_row.addLayout(kind_col)
        casing_row.addStretch()
        options_layout.addLayout(casing_row)

        self._preview_label = QLabel()
        self._preview_label.setStyleSheet(_PREVIEW_STYLE)
        self._preview_label.setWordWrap(True)
        options_layout.addWidget(self._preview_label)

        if not external_options:
            layout.addWidget(self._options_section)

        self.set_format(self._format)

    def options_section(self) -> QWidget:
        """Casing controls and preview, for embedding in a parent scroll area."""
        return self._options_section

    def format(self) -> FilenameFormat:
        self._sync_from_fields()
        return self._format.copy()

    def set_format(self, fmt: FilenameFormat) -> None:
        self._building = True
        self._format = fmt.copy()
        self._sync_casing_combos()
        self._rebuild_rows()
        self._update_casing_labels()
        self._update_preview()
        self._building = False

    def _sync_casing_combos(self) -> None:
        for kind, combo in self._casing_combos.items():
            mode = self._format.casing.get(kind, CASING_NONE)
            index = combo.findData(mode)
            combo.setCurrentIndex(index if index >= 0 else 0)

    def _clear_layout(self, box_layout: QVBoxLayout) -> None:
        while box_layout.count():
            item = box_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _schedule_rebuild(self) -> None:
        QTimer.singleShot(0, self._finish_rebuild)

    def _finish_rebuild(self) -> None:
        self._rebuild_rows()
        self._update_casing_labels()
        self._update_preview()
        self.format_changed.emit(self.format())

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
                sep_field = VisibleSpaceLineEdit(trim_edges=False)
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

            label_field = VisibleSpaceLineEdit()
            label_field.setText(slot.label)
            label_field.setStyleSheet(_FIELD_STYLE)
            label_field.setPlaceholderText("Slot label")
            label_field.textChanged.connect(self._on_field_changed)
            self._label_fields[index] = label_field
            row.addWidget(label_field, 1)

            if slot.kind == SLOT_KIND_ADDITIONAL:
                hint_field = VisibleSpaceLineEdit()
                hint_field.setText(slot.hint)
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
        self._schedule_rebuild()

    def _move_slot(self, index: int, direction: int) -> None:
        new_index = index + direction
        if not (0 <= new_index < len(self._format.slots)):
            return
        self._sync_from_fields()
        slots = self._format.slots
        slots[index], slots[new_index] = slots[new_index], slots[index]
        self._schedule_rebuild()

    def _on_field_changed(self, *_args) -> None:
        if self._building:
            return
        self._sync_from_fields()
        self._update_casing_labels()
        self._update_preview()
        self.format_changed.emit(self.format())

    def _sync_from_fields(self) -> None:
        for index, sep_field in enumerate(self._separator_fields):
            if index < len(self._format.separators):
                self._format.separators[index] = sep_field.text()

        for index, label_field in self._label_fields.items():
            slot = self._format.slots[index]
            fallback = {
                SLOT_KIND_SONG: "Song Name",
                SLOT_KIND_ARTIST: "Artist Name",
                SLOT_KIND_ADDITIONAL: "Additional",
            }.get(slot.kind, "Additional")
            self._format.slots[index].label = label_field.text().strip() or fallback

        for index, hint_field in self._hint_fields.items():
            self._format.slots[index].hint = hint_field.text().strip()

        for index, fixed_box in self._hint_fixed_boxes.items():
            self._format.slots[index].hint_fixed = fixed_box.isChecked()

        for kind, combo in self._casing_combos.items():
            mode = combo.currentData()
            if mode in CASING_MODES:
                self._format.casing[kind] = mode

    def _update_casing_labels(self) -> None:
        for kind, label_widget in self._casing_kind_labels.items():
            label_widget.setText(self._format.casing_label_for_kind(kind))

    def _update_preview(self) -> None:
        self._preview_label.setText(f"Pattern: {format_preview(self._format)}")
