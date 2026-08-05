"""Dialog for assigning title parts to filename slots."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.ui.format_config_widget import FormatConfigWidget
from karaoke_blast.utils.filename_rename import (
    FilenameFormat,
    RenameError,
    SLOT_KIND_ADDITIONAL,
    SLOT_KIND_SONG,
    compose_filename,
    default_slot_values,
    safe_rename,
    split_title,
)

_DIALOG_STYLE = """
QDialog {
    background-color: #1e1e2e;
}
"""

_FIELD_STYLE = """
QLineEdit {
    background-color: #2d2d42;
    color: #ffffff;
    border: 1px solid #5a5a72;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
}
"""

_LABEL_STYLE = "color: #ccc; font-size: 12px; background: transparent;"
_VALUE_STYLE = "color: white; font-size: 13px; background: transparent;"
_PREVIEW_STYLE = "color: #7ee787; font-size: 13px; font-weight: 600; background: transparent;"
_PROGRESS_STYLE = "color: #aaa; font-size: 12px; background: transparent;"

_CHIP_STYLE = """
QPushButton {
    background-color: #2d2d42;
    color: white;
    border: 1px solid #5a5a72;
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #3a3a52;
    border-color: #e94560;
}
"""

_RADIO_STYLE = "color: white; font-size: 12px;"

_ACTIVE_FIELD_STYLE = """
QLineEdit {
    background-color: #2d2d42;
    color: #ffffff;
    border: 1px solid #e94560;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
}
"""


class RenameResult(Enum):
    RENAMED = "renamed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class RenameFileDialog(QDialog):
    """Assign split title parts to filename slots and rename a file."""

    file_renamed = pyqtSignal(object, object)

    def __init__(
        self,
        path: Path,
        *,
        fmt: FilenameFormat,
        progress_label: str | None = None,
        show_format_config: bool = False,
        rename_button_label: str = "Rename & Next",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._fmt = fmt.copy()
        self._parts = split_title(path.stem)
        self._default_slot_values = default_slot_values(path.stem, self._fmt)
        self._result = RenameResult.CANCELLED
        self._new_path: Path | None = None
        self._format_widget: FormatConfigWidget | None = None
        self._focused_slot_index = self._first_enabled_slot_index()
        self._slot_fields: dict[int, QLineEdit] = {}
        self._slot_radios: dict[int, QRadioButton] = {}
        self._chip_buttons: list[QPushButton] = []
        self._target_group = QButtonGroup(self)
        self._target_selector_widget = QWidget()
        self._target_selector_layout = QHBoxLayout(self._target_selector_widget)
        self._target_selector_layout.setContentsMargins(0, 0, 0, 0)
        self._target_selector_layout.setSpacing(12)
        self._target_group.idToggled.connect(self._on_target_selected)

        self.setWindowTitle("Rename File")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        if progress_label:
            progress = QLabel(progress_label)
            progress.setStyleSheet(_PROGRESS_STYLE)
            layout.addWidget(progress)

        original = QLabel(f"Original: {path.name}")
        original.setStyleSheet(_VALUE_STYLE)
        original.setWordWrap(True)
        layout.addWidget(original)

        if show_format_config:
            self._format_widget = FormatConfigWidget()
            self._format_widget.set_format(self._fmt)
            self._format_widget.format_changed.connect(self._on_format_changed)
            layout.addWidget(self._format_widget)
        else:
            self._format_widget = None

        parts_label = QLabel("Parts — click a part to append to the selected target")
        parts_label.setStyleSheet(_LABEL_STYLE)
        layout.addWidget(parts_label)

        self._parts_row = QHBoxLayout()
        self._parts_row.setSpacing(6)
        layout.addLayout(self._parts_row)
        self._rebuild_part_chips()

        layout.addWidget(self._target_selector_widget)
        self._rebuild_target_selector()

        self._slots_layout = QVBoxLayout()
        self._slots_layout.setSpacing(8)
        layout.addLayout(self._slots_layout)
        self._rebuild_slot_fields()

        self._preview_label = QLabel()
        self._preview_label.setStyleSheet(_PREVIEW_STYLE)
        self._preview_label.setWordWrap(True)
        layout.addWidget(self._preview_label)

        self._buttons = QDialogButtonBox()
        self._skip_button = self._buttons.addButton("Skip", QDialogButtonBox.ButtonRole.ActionRole)
        self._rename_button = self._buttons.addButton(
            rename_button_label, QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._cancel_button = self._buttons.addButton(
            QDialogButtonBox.StandardButton.Cancel
        )
        if progress_label is None:
            self._skip_button.hide()
        self._skip_button.clicked.connect(self._skip)
        self._rename_button.clicked.connect(self._rename)
        self._cancel_button.clicked.connect(self.reject)
        layout.addWidget(self._buttons)

        self._update_preview()

    def result_value(self) -> RenameResult:
        return self._result

    def new_path(self) -> Path | None:
        return self._new_path

    def format(self) -> FilenameFormat:
        if self._format_widget is not None:
            return self._format_widget.format()
        return self._fmt

    def _enabled_slot_indices(self) -> list[int]:
        return self.format().enabled_slot_indices()

    def _first_enabled_slot_index(self) -> int:
        enabled = self._enabled_slot_indices()
        return enabled[0] if enabled else 0

    def _rebuild_part_chips(self) -> None:
        while self._parts_row.count():
            item = self._parts_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._chip_buttons.clear()

        for part in self._parts:
            chip = QPushButton(part)
            chip.setStyleSheet(_CHIP_STYLE)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _checked=False, value=part: self._assign_part(value))
            self._chip_buttons.append(chip)
            self._parts_row.addWidget(chip)
        self._parts_row.addStretch()

    def _rebuild_target_selector(self) -> None:
        for button in self._target_group.buttons():
            self._target_group.removeButton(button)
            button.deleteLater()
        self._slot_radios.clear()

        while self._target_selector_layout.count():
            item = self._target_selector_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        append_label = QLabel("Append to:")
        append_label.setStyleSheet(_LABEL_STYLE)
        self._target_selector_layout.addWidget(append_label)

        enabled_indices = self._enabled_slot_indices()
        for radio_index, slot_index in enumerate(enabled_indices):
            slot = self.format().slots[slot_index]
            radio = QRadioButton(slot.label)
            radio.setStyleSheet(_RADIO_STYLE)
            self._target_group.addButton(radio, radio_index)
            self._slot_radios[slot_index] = radio
            self._target_selector_layout.addWidget(radio)

        self._target_selector_layout.addStretch()

        if enabled_indices:
            if self._focused_slot_index not in enabled_indices:
                self._focused_slot_index = enabled_indices[0]
            radio = self._slot_radios.get(self._focused_slot_index)
            if radio is not None:
                radio.setChecked(True)

    def _rebuild_slot_fields(self) -> None:
        while self._slots_layout.count():
            item = self._slots_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._slot_fields.clear()

        fmt = self.format()
        for slot_index in fmt.enabled_slot_indices():
            slot = fmt.slots[slot_index]
            row = QHBoxLayout()
            label = QLabel(f"{slot.label}:")
            label.setFixedWidth(110)
            label.setStyleSheet(_LABEL_STYLE)
            field = QLineEdit()
            field.setStyleSheet(_FIELD_STYLE)
            field.textChanged.connect(self._update_preview)
            field.installEventFilter(self)
            field.setProperty("slot_index", slot_index)
            initial_value = self._default_slot_values.get(slot_index, "")
            if initial_value:
                field.blockSignals(True)
                field.setText(initial_value)
                field.blockSignals(False)
            if slot.kind == SLOT_KIND_SONG:
                field.setPlaceholderText("")
            elif slot.kind == SLOT_KIND_ADDITIONAL and not slot.hint_fixed and slot.hint:
                field.setPlaceholderText(slot.hint)
            elif slot.kind == SLOT_KIND_ADDITIONAL:
                field.setPlaceholderText("Optional")
            self._slot_fields[slot_index] = field
            row.addWidget(label)
            row.addWidget(field, 1)
            container = QWidget()
            container.setLayout(row)
            self._slots_layout.addWidget(container)

        self._update_target_highlight()

    def _on_target_selected(self, radio_index: int, checked: bool) -> None:
        if not checked:
            return
        enabled_indices = self._enabled_slot_indices()
        if radio_index < 0 or radio_index >= len(enabled_indices):
            return
        self._focused_slot_index = enabled_indices[radio_index]
        self._update_target_highlight()

    def _update_target_highlight(self) -> None:
        for slot_index, field in self._slot_fields.items():
            field.setStyleSheet(
                _ACTIVE_FIELD_STYLE
                if slot_index == self._focused_slot_index
                else _FIELD_STYLE
            )

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.FocusIn and isinstance(obj, QLineEdit):
            slot_index = obj.property("slot_index")
            if isinstance(slot_index, int) and slot_index in self._slot_fields:
                self._focused_slot_index = slot_index
                radio = self._slot_radios.get(slot_index)
                if radio is not None:
                    radio.setChecked(True)
                self._update_target_highlight()
        return super().eventFilter(obj, event)

    def _on_format_changed(self, fmt: FilenameFormat) -> None:
        self._fmt = fmt.copy()
        values = {index: field.text() for index, field in self._slot_fields.items()}
        previous_focus = self._focused_slot_index
        self._default_slot_values = default_slot_values(self._path.stem, self._fmt)
        for slot_index in self._fmt.enabled_slot_indices():
            slot = self._fmt.slots[slot_index]
            if slot_index not in values and slot.hint_fixed and slot.hint:
                values[slot_index] = slot.hint
        self._rebuild_target_selector()
        self._rebuild_slot_fields()
        for index, value in values.items():
            if index in self._slot_fields:
                self._slot_fields[index].setText(value)
        if previous_focus in self._slot_fields:
            self._focused_slot_index = previous_focus
            radio = self._slot_radios.get(previous_focus)
            if radio is not None:
                radio.setChecked(True)
        else:
            self._focused_slot_index = self._first_enabled_slot_index()
        self._update_target_highlight()
        self._update_preview()

    def _assign_part(self, part: str) -> None:
        if self._focused_slot_index not in self._slot_fields:
            return
        field = self._slot_fields[self._focused_slot_index]
        current = field.text().strip()
        field.setText(f"{current} {part}".strip() if current else part)
        self._update_preview()

    def _slot_values(self) -> dict[int, str]:
        return {index: field.text() for index, field in self._slot_fields.items()}

    def _update_preview(self, *_args) -> None:
        preview = compose_filename(self._slot_values(), self.format())
        if preview:
            self._preview_label.setStyleSheet(_PREVIEW_STYLE)
            self._preview_label.setText(f"Preview: {preview}{self._path.suffix}")
        else:
            self._preview_label.setStyleSheet(_PREVIEW_STYLE)
            self._preview_label.setText("Preview: (fill Song Name to preview)")
        self._rename_button.setEnabled(bool(preview))

    def _skip(self) -> None:
        self._result = RenameResult.SKIPPED
        self.accept()

    def _rename(self) -> None:
        preview = compose_filename(self._slot_values(), self.format())
        if not preview:
            return
        try:
            new_path = safe_rename(self._path, preview)
        except RenameError as exc:
            self._preview_label.setStyleSheet("color: #ff6b81; font-size: 13px;")
            self._preview_label.setText(str(exc))
            return

        self._result = RenameResult.RENAMED
        self._new_path = new_path
        self.file_renamed.emit(self._path, new_path)
        self.accept()
