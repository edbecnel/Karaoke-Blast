"""Visual editor for filename format configuration."""

from __future__ import annotations

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
    NO_SUFFIX_FORMAT,
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
"""

_SLOT_STYLE = "color: white; font-size: 12px; font-weight: 600; background: transparent;"
_PREVIEW_STYLE = "color: #7ee787; font-size: 12px; background: transparent;"


class FormatConfigWidget(QWidget):
    """Configure slots, separators, and suffix for filename composition."""

    format_changed = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._format = DEFAULT_KARAOKE_FORMAT.copy()
        self._building = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Format")
        title.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        layout.addWidget(title)

        format_row = QHBoxLayout()
        format_row.setSpacing(8)

        self._slot1_label = QLabel()
        self._slot1_label.setStyleSheet(_SLOT_STYLE)
        format_row.addWidget(self._slot1_label)

        self._sep1_field = QLineEdit()
        self._sep1_field.setFixedSize(64, 28)
        self._sep1_field.setStyleSheet(_FIELD_STYLE)
        self._sep1_field.setToolTip("Separator between first and second fields")
        self._sep1_field.textChanged.connect(self._on_field_changed)
        format_row.addWidget(self._sep1_field)

        self._slot2_label = QLabel()
        self._slot2_label.setStyleSheet(_SLOT_STYLE)
        format_row.addWidget(self._slot2_label)

        swap_btn = QPushButton("⇄")
        swap_btn.setFixedSize(32, 28)
        swap_btn.setToolTip("Swap song and artist order")
        swap_btn.setStyleSheet(_BUTTON_STYLE)
        swap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        swap_btn.clicked.connect(self._swap_slots)
        format_row.addWidget(swap_btn)

        self._sep2_field = QLineEdit()
        self._sep2_field.setFixedSize(64, 28)
        self._sep2_field.setStyleSheet(_FIELD_STYLE)
        self._sep2_field.setToolTip("Separator before suffix")
        self._sep2_field.textChanged.connect(self._on_field_changed)
        format_row.addWidget(self._sep2_field)

        self._suffix_checkbox = QCheckBox("Include suffix:")
        self._suffix_checkbox.setStyleSheet(CHECKBOX_STYLE_WHITE_LABEL)
        self._suffix_checkbox.toggled.connect(self._on_suffix_toggled)
        format_row.addWidget(self._suffix_checkbox)

        self._suffix_field = QLineEdit()
        self._suffix_field.setPlaceholderText("Suffix text")
        self._suffix_field.setFixedHeight(28)
        self._suffix_field.setMinimumWidth(100)
        self._suffix_field.setStyleSheet(_FIELD_STYLE)
        self._suffix_field.textChanged.connect(self._on_field_changed)
        format_row.addWidget(self._suffix_field, 1)

        layout.addLayout(format_row)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        karaoke_btn = QPushButton("Karaoke standard")
        karaoke_btn.setStyleSheet(_BUTTON_STYLE)
        karaoke_btn.clicked.connect(self._apply_karaoke_preset)
        preset_row.addWidget(karaoke_btn)

        no_suffix_btn = QPushButton("No suffix")
        no_suffix_btn.setStyleSheet(_BUTTON_STYLE)
        no_suffix_btn.clicked.connect(self._apply_no_suffix_preset)
        preset_row.addWidget(no_suffix_btn)
        preset_row.addStretch()
        layout.addLayout(preset_row)

        self._preview_label = QLabel()
        self._preview_label.setStyleSheet(_PREVIEW_STYLE)
        self._preview_label.setWordWrap(True)
        layout.addWidget(self._preview_label)

        self.set_format(self._format)

    def format(self) -> FilenameFormat:
        return self._format.copy()

    def set_format(self, fmt: FilenameFormat) -> None:
        self._building = True
        self._format = fmt.copy()
        separators = self._format.normalized_separators()
        self._sep1_field.setText(separators[0] if separators else " - ")
        self._sep2_field.setText(
            separators[len(self._format.slot_names) - 1]
            if len(separators) > len(self._format.slot_names) - 1
            else separators[-1] if len(separators) > 1
            else " - "
        )
        self._suffix_checkbox.setChecked(self._format.suffix_enabled)
        self._suffix_field.setText(self._format.suffix_text)
        self._update_slot_labels()
        self._update_suffix_controls()
        self._update_preview()
        self._building = False

    def _update_slot_labels(self) -> None:
        names = self._format.slot_names
        self._slot1_label.setText(names[0] if names else "Song Name")
        self._slot2_label.setText(names[1] if len(names) > 1 else "Artist Name")

    def _swap_slots(self) -> None:
        if len(self._format.slot_names) < 2:
            return
        self._sync_from_fields()
        self._format.slot_names = [
            self._format.slot_names[1],
            self._format.slot_names[0],
        ]
        self._update_slot_labels()
        self._update_preview()
        self.format_changed.emit(self.format())

    def _update_suffix_controls(self) -> None:
        enabled = self._suffix_checkbox.isChecked()
        self._sep2_field.setVisible(enabled)
        self._suffix_field.setEnabled(enabled)

    def _apply_karaoke_preset(self) -> None:
        self.set_format(DEFAULT_KARAOKE_FORMAT.copy())
        self.format_changed.emit(self.format())

    def _apply_no_suffix_preset(self) -> None:
        self.set_format(NO_SUFFIX_FORMAT.copy())
        self.format_changed.emit(self.format())

    def _on_suffix_toggled(self, checked: bool) -> None:
        if self._building:
            return
        self._format.suffix_enabled = checked
        self._update_suffix_controls()
        self._sync_from_fields()
        self._update_preview()
        self.format_changed.emit(self.format())

    def _on_field_changed(self, *_args) -> None:
        if self._building:
            return
        self._sync_from_fields()
        self._update_preview()
        self.format_changed.emit(self.format())

    def _sync_from_fields(self) -> None:
        sep1 = self._sep1_field.text()
        sep2 = self._sep2_field.text()
        suffix_enabled = self._suffix_checkbox.isChecked()
        if suffix_enabled:
            self._format.separators = [sep1, sep2]
        else:
            self._format.separators = [sep1]
        self._format.suffix_enabled = suffix_enabled
        self._format.suffix_text = self._suffix_field.text().strip()

    def _update_preview(self) -> None:
        self._preview_label.setText(f"Pattern: {format_preview(self._format)}")
