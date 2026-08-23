"""Dialog for assigning filename parts to Title / Artist / Comment metadata."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt
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

from karaoke_blast.ui.rename_file_dialog import HintableSlotField
from karaoke_blast.ui.slot_field_casing import apply_casing_to_field, cased_slot_text
from karaoke_blast.utils.filename_rename import (
    FilenameFormat,
    FormatSlot,
    SLOT_KIND_ADDITIONAL,
    SLOT_KIND_ARTIST,
    SLOT_KIND_SONG,
    apply_slot_casing,
    default_slot_values,
    fixed_slot_values,
    split_title,
)
from karaoke_blast.utils.media_metadata import MetadataError, write_tags

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
_ERROR_STYLE = "color: #ff6b81; font-size: 13px; background: transparent;"
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

_HINT_CHIP_STYLE = """
QPushButton {
    background-color: #2d2d42;
    color: #b8b8c8;
    border: 1px dashed #5a5a72;
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #3a3a52;
    color: white;
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

_READONLY_FIELD_STYLE = """
QLineEdit {
    background-color: #252536;
    color: #b8b8c8;
    border: 1px solid #4a4a62;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
}
"""

_COMMENT_JOIN = "; "


class MetadataResult(Enum):
    APPLIED = "applied"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class MetadataFileDialog(QDialog):
    """Assign split title parts to slots and write Title / Artist / Comment tags."""

    def __init__(
        self,
        path: Path,
        *,
        fmt: FilenameFormat,
        comment_slot_indices: list[int] | None = None,
        progress_label: str | None = None,
        auto_fill_slots: bool = False,
        apply_button_label: str = "Apply Metadata & Next",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._fmt = fmt.copy()
        self._comment_slot_indices = list(comment_slot_indices or [])
        self._auto_fill_slots = auto_fill_slots
        self._auto_filled_values = (
            default_slot_values(path.stem, self._fmt) if auto_fill_slots else {}
        )
        self._parts = split_title(path.stem)
        self._result = MetadataResult.CANCELLED
        self._focused_slot_index = self._first_appendable_slot_index()
        self._slot_fields: dict[int, QLineEdit] = {}
        self._hint_buttons: dict[int, QPushButton] = {}
        self._slot_radios: dict[int, QRadioButton] = {}
        self._chip_buttons: list[QPushButton] = []
        self._target_group = QButtonGroup(self)
        self._target_selector_widget = QWidget()
        self._target_selector_layout = QHBoxLayout(self._target_selector_widget)
        self._target_selector_layout.setContentsMargins(0, 0, 0, 0)
        self._target_selector_layout.setSpacing(12)
        self._target_group.idToggled.connect(self._on_target_selected)

        self.setWindowTitle("Tag Metadata")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        if progress_label:
            progress = QLabel(progress_label)
            progress.setStyleSheet(_PROGRESS_STYLE)
            layout.addWidget(progress)

        original = QLabel(f"File: {path.name}")
        original.setStyleSheet(_VALUE_STYLE)
        original.setWordWrap(True)
        layout.addWidget(original)

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

        self._title_preview = QLabel()
        self._title_preview.setStyleSheet(_PREVIEW_STYLE)
        self._title_preview.setWordWrap(True)
        layout.addWidget(self._title_preview)

        self._artist_preview = QLabel()
        self._artist_preview.setStyleSheet(_PREVIEW_STYLE)
        self._artist_preview.setWordWrap(True)
        layout.addWidget(self._artist_preview)

        self._comment_preview = QLabel()
        self._comment_preview.setStyleSheet(_PREVIEW_STYLE)
        self._comment_preview.setWordWrap(True)
        layout.addWidget(self._comment_preview)

        self._status_label = QLabel()
        self._status_label.setStyleSheet(_ERROR_STYLE)
        self._status_label.setWordWrap(True)
        self._status_label.hide()
        layout.addWidget(self._status_label)

        self._buttons = QDialogButtonBox()
        self._skip_button = self._buttons.addButton("Skip", QDialogButtonBox.ButtonRole.ActionRole)
        self._apply_button = self._buttons.addButton(
            apply_button_label, QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._cancel_button = self._buttons.addButton(
            QDialogButtonBox.StandardButton.Cancel
        )
        if progress_label is None:
            self._skip_button.hide()
        self._skip_button.clicked.connect(self._skip)
        self._apply_button.clicked.connect(self._apply)
        self._cancel_button.clicked.connect(self.reject)
        layout.addWidget(self._buttons)

        self._update_preview()

    def result_value(self) -> MetadataResult:
        return self._result

    def format(self) -> FilenameFormat:
        return self._fmt

    def _appendable_slot_indices(self) -> list[int]:
        return [
            index
            for index in self._fmt.enabled_slot_indices()
            if not self._is_fixed_slot(self._fmt.slots[index])
        ]

    def _first_appendable_slot_index(self) -> int:
        appendable = self._appendable_slot_indices()
        return appendable[0] if appendable else 0

    def _ensure_appendable_focus(self) -> None:
        appendable = self._appendable_slot_indices()
        if not appendable:
            return
        if self._focused_slot_index not in appendable:
            self._focused_slot_index = appendable[0]
        radio = self._slot_radios.get(self._focused_slot_index)
        if radio is not None:
            radio.setChecked(True)

    @staticmethod
    def _is_fixed_slot(slot: FormatSlot) -> bool:
        return (
            slot.kind == SLOT_KIND_ADDITIONAL
            and slot.hint_fixed
            and bool(slot.hint)
        )

    def _slot_hint(self, slot_index: int) -> str | None:
        slot = self._fmt.slots[slot_index]
        if self._is_fixed_slot(slot):
            return None
        if slot.kind == SLOT_KIND_ADDITIONAL and slot.hint:
            return slot.hint
        return None

    def _accept_slot_hint(self, slot_index: int) -> None:
        hint = self._slot_hint(slot_index)
        if not hint or slot_index not in self._slot_fields:
            return
        field = self._slot_fields[slot_index]
        if field.isReadOnly():
            return
        field.setText(hint)
        self._on_slot_text_changed(slot_index)

    def _try_accept_hint_via_right_arrow(self, slot_index: int, field: QLineEdit) -> bool:
        hint = self._slot_hint(slot_index)
        if not hint or field.isReadOnly():
            return False
        text = field.text().strip()
        if text:
            return False
        self._accept_slot_hint(slot_index)
        return True

    def _update_hint_button(self, slot_index: int) -> None:
        button = self._hint_buttons.get(slot_index)
        if button is None:
            return
        hint = self._slot_hint(slot_index)
        field = self._slot_fields.get(slot_index)
        if not hint or field is None:
            button.hide()
            return
        button.setVisible(field.text().strip() != hint)

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

        appendable_indices = self._appendable_slot_indices()
        for radio_index, slot_index in enumerate(appendable_indices):
            slot = self._fmt.slots[slot_index]
            radio = QRadioButton(slot.label)
            radio.setStyleSheet(_RADIO_STYLE)
            self._target_group.addButton(radio, radio_index)
            self._slot_radios[slot_index] = radio
            self._target_selector_layout.addWidget(radio)

        self._target_selector_layout.addStretch()
        self._target_selector_widget.setVisible(bool(appendable_indices))
        self._ensure_appendable_focus()

    def _rebuild_slot_fields(self, preserved_values: dict[int, str] | None = None) -> None:
        while self._slots_layout.count():
            item = self._slots_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._slot_fields.clear()
        self._hint_buttons.clear()

        fixed = fixed_slot_values(self._fmt)
        for slot_index in self._fmt.enabled_slot_indices():
            slot = self._fmt.slots[slot_index]
            row = QHBoxLayout()
            label = QLabel(f"{slot.label}:")
            label.setFixedWidth(110)
            label.setStyleSheet(_LABEL_STYLE)
            field = HintableSlotField(
                slot_index,
                on_accept_hint=self._try_accept_hint_via_right_arrow,
            )
            field.setStyleSheet(_FIELD_STYLE)
            field.textChanged.connect(
                lambda _text, index=slot_index: self._on_slot_text_changed(index)
            )
            field.installEventFilter(self)
            field.setProperty("slot_index", slot_index)
            is_fixed = self._is_fixed_slot(slot)
            if is_fixed:
                field.setReadOnly(True)
                field.setClearButtonEnabled(False)
            else:
                field.setClearButtonEnabled(True)
            initial = ""
            if is_fixed:
                initial = slot.hint
            elif preserved_values is not None and slot_index in preserved_values:
                initial = preserved_values[slot_index]
            elif self._auto_fill_slots and slot_index in self._auto_filled_values:
                initial = self._auto_filled_values[slot_index]
            elif slot_index in fixed:
                initial = fixed[slot_index]
            if initial:
                initial = cased_slot_text(initial, slot.kind, self._fmt)
                field.blockSignals(True)
                field.setText(initial)
                field.blockSignals(False)
            if slot.kind == SLOT_KIND_SONG:
                field.setPlaceholderText("")
            elif slot.kind == SLOT_KIND_ADDITIONAL and not slot.hint_fixed and slot.hint:
                field.setPlaceholderText(slot.hint)
            elif slot.kind == SLOT_KIND_ADDITIONAL:
                field.setPlaceholderText("Optional")
            hint = self._slot_hint(slot_index)
            field.set_hint_available(bool(hint))
            self._slot_fields[slot_index] = field
            row.addWidget(label)
            row.addWidget(field, 1)
            if hint:
                hint_button = QPushButton(hint)
                hint_button.setStyleSheet(_HINT_CHIP_STYLE)
                hint_button.setCursor(Qt.CursorShape.PointingHandCursor)
                hint_button.setToolTip(f'Use "{hint}" (Right Arrow or Down Arrow)')
                hint_button.clicked.connect(
                    lambda _checked=False, index=slot_index: self._accept_slot_hint(index)
                )
                field.textChanged.connect(
                    lambda _text, index=slot_index: self._update_hint_button(index)
                )
                self._hint_buttons[slot_index] = hint_button
                row.addWidget(hint_button)
                self._update_hint_button(slot_index)
            container = QWidget()
            container.setLayout(row)
            self._slots_layout.addWidget(container)

        self._update_target_highlight()

    def _on_target_selected(self, radio_index: int, checked: bool) -> None:
        if not checked:
            return
        appendable_indices = self._appendable_slot_indices()
        if radio_index < 0 or radio_index >= len(appendable_indices):
            return
        self._focused_slot_index = appendable_indices[radio_index]
        self._update_target_highlight()

    def _update_target_highlight(self) -> None:
        for slot_index, field in self._slot_fields.items():
            if field.isReadOnly():
                field.setStyleSheet(_READONLY_FIELD_STYLE)
            elif slot_index == self._focused_slot_index:
                field.setStyleSheet(_ACTIVE_FIELD_STYLE)
            else:
                field.setStyleSheet(_FIELD_STYLE)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.FocusIn and isinstance(obj, QLineEdit):
            slot_index = obj.property("slot_index")
            if isinstance(slot_index, int) and slot_index in self._slot_fields:
                field = self._slot_fields[slot_index]
                if field.isReadOnly():
                    self._update_target_highlight()
                    return super().eventFilter(obj, event)
                self._focused_slot_index = slot_index
                radio = self._slot_radios.get(slot_index)
                if radio is not None:
                    radio.setChecked(True)
                self._update_target_highlight()
        return super().eventFilter(obj, event)

    def _assign_part(self, part: str) -> None:
        if self._focused_slot_index not in self._slot_fields:
            return
        field = self._slot_fields[self._focused_slot_index]
        if field.isReadOnly():
            return
        current = field.text().strip()
        field.setText(f"{current} {part}".strip() if current else part)

    def _on_slot_text_changed(self, slot_index: int) -> None:
        field = self._slot_fields.get(slot_index)
        if field is None:
            return
        slot = self._fmt.slots[slot_index]
        if not field.isReadOnly():
            apply_casing_to_field(field, slot.kind, self._fmt)
        self._update_hint_button(slot_index)
        self._update_preview()

    def _slot_values(self) -> dict[int, str]:
        return {index: field.text().strip() for index, field in self._slot_fields.items()}

    def _resolved_title_artist_comment(self) -> tuple[str, str, str]:
        values = self._slot_values()
        title = ""
        artist = ""
        for index, slot in enumerate(self._fmt.slots):
            if not slot.enabled:
                continue
            text = apply_slot_casing(values.get(index, "").strip(), slot.kind, self._fmt)
            if slot.kind == SLOT_KIND_SONG:
                title = text
            elif slot.kind == SLOT_KIND_ARTIST:
                artist = text

        comment_parts: list[str] = []
        for index in self._comment_slot_indices:
            if index not in self._slot_fields:
                continue
            slot = self._fmt.slots[index]
            text = apply_slot_casing(values.get(index, "").strip(), slot.kind, self._fmt)
            if text and text not in comment_parts:
                comment_parts.append(text)
        comment = _COMMENT_JOIN.join(comment_parts)
        return title, artist, comment

    def _update_preview(self, *_args) -> None:
        title, artist, comment = self._resolved_title_artist_comment()
        self._title_preview.setStyleSheet(_PREVIEW_STYLE)
        self._artist_preview.setStyleSheet(_PREVIEW_STYLE)
        self._comment_preview.setStyleSheet(_PREVIEW_STYLE)
        self._title_preview.setText(f"Title: {title or '(required)'}")
        self._artist_preview.setText(f"Artist: {artist or '(none)'}")
        if self._comment_slot_indices:
            self._comment_preview.setText(f"Comment: {comment or '(empty)'}")
            self._comment_preview.show()
        else:
            self._comment_preview.setText("Comment: (no slots selected)")
            self._comment_preview.show()
        self._status_label.hide()
        self._apply_button.setEnabled(bool(title))

    def _skip(self) -> None:
        self._result = MetadataResult.SKIPPED
        self.accept()

    def _apply(self) -> None:
        title, artist, comment = self._resolved_title_artist_comment()
        if not title:
            return
        try:
            write_tags(
                self._path,
                title=title,
                artist=artist,
                comment=comment if self._comment_slot_indices else None,
            )
        except MetadataError as exc:
            self._status_label.setText(str(exc))
            self._status_label.show()
            return

        self._result = MetadataResult.APPLIED
        self.accept()
