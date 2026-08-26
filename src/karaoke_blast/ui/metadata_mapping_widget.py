"""Widget for mapping filename slots to VLC metadata fields."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from karaoke_blast.utils.filename_rename import FilenameFormat
from karaoke_blast.utils.metadata_field_mapping import (
    VLC_FIELD_ALBUM,
    VLC_FIELD_ARTIST,
    VLC_FIELD_DESCRIPTION,
    VLC_FIELD_TITLE,
    VLC_METADATA_FIELD_LABELS,
    MetadataFieldMapping,
)

_COMBO_STYLE = """
QComboBox {
    background-color: #2d2d42;
    color: #ffffff;
    border: 1px solid #5a5a72;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
QComboBox::drop-down {
    border: none;
}
"""

_HINT_STYLE = "color: #888; font-size: 11px; background: transparent;"
_NONE_VALUE = -1
_COMBO_MIN_WIDTH = 280


class MetadataMappingWidget(QWidget):
    """Map enabled filename slots to Title, Artist, Description, and Album."""

    mapping_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fmt = FilenameFormat()
        self._mapping = MetadataFieldMapping()
        self._combos: dict[str, QComboBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        heading = QLabel("VLC metadata mapping")
        heading.setStyleSheet("color: #e94560; font-size: 12px; font-weight: bold;")
        layout.addWidget(heading)

        hint = QLabel(
            "Choose which filename slot is written to each VLC field "
            "(Title, Artist, Description, Album)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(_HINT_STYLE)
        layout.addWidget(hint)

        self._form = QFormLayout()
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._form.setSpacing(8)
        self._form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        layout.addLayout(self._form)

        for field_key in (
            VLC_FIELD_TITLE,
            VLC_FIELD_ARTIST,
            VLC_FIELD_DESCRIPTION,
            VLC_FIELD_ALBUM,
        ):
            combo = self._make_combo()
            self._combos[field_key] = combo
            self._form.addRow(QLabel(VLC_METADATA_FIELD_LABELS[field_key]), combo)
            combo.currentIndexChanged.connect(self._on_combo_changed)

        self._empty_label = QLabel("Enable at least one filename slot to configure mapping.")
        self._empty_label.setStyleSheet(_HINT_STYLE)
        self._empty_label.hide()
        layout.addWidget(self._empty_label)

    def _make_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.setStyleSheet(_COMBO_STYLE)
        combo.setMinimumWidth(_COMBO_MIN_WIDTH)
        combo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        return combo

    def set_format_and_mapping(
        self,
        fmt: FilenameFormat,
        mapping: MetadataFieldMapping,
    ) -> None:
        self._fmt = fmt.copy()
        self._mapping = mapping.copy().normalize_for_format(self._fmt)
        self._rebuild()

    def mapping(self) -> MetadataFieldMapping:
        return self._collect_mapping().normalize_for_format(self._fmt)

    def _enabled_indices(self) -> list[int]:
        return self._fmt.enabled_slot_indices()

    def _combo_for_field(self, field_key: str) -> QComboBox:
        return self._combos[field_key]

    def _field_slot(self, field_key: str) -> int | None:
        if field_key == VLC_FIELD_DESCRIPTION:
            slots = self._mapping.description_slots
            return slots[0] if slots else None
        if field_key == VLC_FIELD_TITLE:
            return self._mapping.title_slot
        if field_key == VLC_FIELD_ARTIST:
            return self._mapping.artist_slot
        if field_key == VLC_FIELD_ALBUM:
            return self._mapping.album_slot
        return None

    def _rebuild(self) -> None:
        enabled = self._enabled_indices()
        has_slots = bool(enabled)
        self._empty_label.setVisible(not has_slots)
        for combo in self._combos.values():
            combo.setEnabled(has_slots)

        for field_key, combo in self._combos.items():
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("(none)", _NONE_VALUE)
            reserved = self._reserved_slots(exclude_field=field_key)
            for index in enabled:
                if index in reserved:
                    continue
                combo.addItem(self._fmt.slots[index].label, index)
            self._set_combo_slot(combo, self._field_slot(field_key))
            combo.blockSignals(False)

    def _reserved_slots(self, *, exclude_field: str) -> set[int]:
        reserved: set[int] = set()
        for field_key, combo in self._combos.items():
            if field_key == exclude_field:
                continue
            slot = self._combo_slot(combo)
            if slot is not None:
                reserved.add(slot)
        return reserved

    def _set_combo_slot(self, combo: QComboBox, slot_index: int | None) -> None:
        if slot_index is None:
            combo.setCurrentIndex(0)
            return
        for row in range(combo.count()):
            if combo.itemData(row) == slot_index:
                combo.setCurrentIndex(row)
                return
        combo.setCurrentIndex(0)

    def _combo_slot(self, combo: QComboBox) -> int | None:
        value = combo.currentData()
        if isinstance(value, int) and value >= 0:
            return value
        return None

    def _collect_mapping(self) -> MetadataFieldMapping:
        description_slot = self._combo_slot(self._combo_for_field(VLC_FIELD_DESCRIPTION))
        return MetadataFieldMapping(
            title_slot=self._combo_slot(self._combo_for_field(VLC_FIELD_TITLE)),
            artist_slot=self._combo_slot(self._combo_for_field(VLC_FIELD_ARTIST)),
            description_slots=[description_slot] if description_slot is not None else [],
            album_slot=self._combo_slot(self._combo_for_field(VLC_FIELD_ALBUM)),
        )

    def _on_combo_changed(self) -> None:
        self._mapping = self._collect_mapping()
        self._rebuild()
        self.mapping_changed.emit()
