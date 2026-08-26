"""Dialog to configure metadata display format for library lists."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.ui.checkbox_style import CHECKBOX_STYLE_WHITE_LABEL
from karaoke_blast.ui.visible_space_field import VisibleSpaceLineEdit
from karaoke_blast.utils.song_display import (
    DisplayFormat,
    format_display_preview,
    slot_kind_label,
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

_LABEL_STYLE = "color: white; font-size: 12px; font-weight: 600; background: transparent;"
_PREVIEW_STYLE = "color: #7ee787; font-size: 12px; background: transparent;"
_SEP_LABEL_STYLE = "color: #888; font-size: 11px; background: transparent;"
_HINT_STYLE = "color: #888; font-size: 11px; background: transparent;"


class DisplayFormatDialog(QDialog):
    """Edit order, enablement, and separators for VLC metadata display fields."""

    def __init__(
        self,
        fmt: DisplayFormat | None = None,
        *,
        media_type_name: str = "Media",
        field_labels: dict[str, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{media_type_name} display format")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setStyleSheet(_DIALOG_STYLE)

        self._format = (fmt or DisplayFormat()).copy()
        self._field_labels = dict(field_labels or {})
        self._building = False
        self._slot_rows_layout = QVBoxLayout()
        self._slot_rows_layout.setSpacing(4)
        self._separator_fields: list[VisibleSpaceLineEdit] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Metadata display format")
        title.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        hint = QLabel(
            "Choose which embedded metadata fields appear in the list, their order, "
            "and the separators between them. Items without a title still show the "
            "file name."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(_HINT_STYLE)
        layout.addWidget(hint)

        layout.addLayout(self._slot_rows_layout)

        self._preview_label = QLabel()
        self._preview_label.setStyleSheet(_PREVIEW_STYLE)
        self._preview_label.setWordWrap(True)
        layout.addWidget(self._preview_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        for button in buttons.buttons():
            button.setStyleSheet(_BUTTON_STYLE)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(buttons)

        self._rebuild_rows()
        self._update_preview()

    def format(self) -> DisplayFormat:
        self._sync_from_fields()
        return self._format.copy()

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
        self._update_preview()

    def _rebuild_rows(self) -> None:
        self._building = True
        self._clear_layout(self._slot_rows_layout)
        self._separator_fields.clear()

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
            enabled_box.setToolTip("Include this field in the display")
            enabled_box.toggled.connect(
                lambda checked, slot_index=index: self._on_slot_enabled(
                    slot_index, checked
                )
            )
            row.addWidget(enabled_box)

            badge = QLabel(slot_kind_label(slot.kind, self._field_labels))
            badge.setStyleSheet(_LABEL_STYLE)
            row.addWidget(badge, 1)

            up_btn = QPushButton("↑")
            up_btn.setFixedSize(28, 28)
            up_btn.setStyleSheet(_BUTTON_STYLE)
            up_btn.setEnabled(index > 0)
            up_btn.setToolTip("Move up")
            up_btn.clicked.connect(
                lambda _checked=False, slot_index=index: self._move_slot(slot_index, -1)
            )
            row.addWidget(up_btn)

            down_btn = QPushButton("↓")
            down_btn.setFixedSize(28, 28)
            down_btn.setStyleSheet(_BUTTON_STYLE)
            down_btn.setEnabled(index < len(self._format.slots) - 1)
            down_btn.setToolTip("Move down")
            down_btn.clicked.connect(
                lambda _checked=False, slot_index=index: self._move_slot(slot_index, 1)
            )
            row.addWidget(down_btn)

            container = QWidget()
            container.setLayout(row)
            self._slot_rows_layout.addWidget(container)

        self._building = False

    def _on_slot_enabled(self, index: int, checked: bool) -> None:
        if self._building:
            return
        self._sync_from_fields()
        self._format.slots[index].enabled = checked
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
        self._update_preview()

    def _sync_from_fields(self) -> None:
        for index, sep_field in enumerate(self._separator_fields):
            if index < len(self._format.separators):
                self._format.separators[index] = sep_field.text()

    def _update_preview(self) -> None:
        preview = format_display_preview(self._format, field_labels=self._field_labels)
        self._preview_label.setText(f"Preview: {preview}" if preview else "Preview: (none)")
