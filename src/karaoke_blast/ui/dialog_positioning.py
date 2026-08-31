"""Helpers for positioning modal dialogs over anchor widgets."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QWidget


def _move_dialog_global(dialog: QDialog, global_pos: QPoint) -> None:
    parent = dialog.parentWidget()
    if parent is not None:
        dialog.move(parent.mapFromGlobal(global_pos))
        return
    dialog.move(global_pos)


def fit_dialog_to_anchor(
    dialog: QDialog,
    anchor: QWidget,
    *,
    margin: int = 12,
) -> None:
    """Place *dialog* with its left edge on *anchor*, vertically centered within it."""
    if not anchor.isVisible():
        return
    top_left = anchor.mapToGlobal(QPoint(0, 0))
    bounds = QRect(top_left, anchor.size()).adjusted(margin, margin, -margin, -margin)
    if bounds.width() <= 0 or bounds.height() <= 0:
        return

    screen = dialog.screen() or anchor.screen() or QApplication.primaryScreen()
    if screen is not None:
        available = screen.availableGeometry()
        max_height = max(360, available.height() - 24)
        if dialog.height() > max_height:
            dialog.resize(dialog.width(), min(dialog.sizeHint().height(), max_height))

    frame = dialog.frameGeometry()
    y = bounds.top() + max(0, (bounds.height() - frame.height()) // 2)
    target_global = QPoint(bounds.left(), y)

    if screen is not None:
        available = screen.availableGeometry()
        if target_global.y() + frame.height() > available.bottom():
            target_global.setY(max(available.top(), available.bottom() - frame.height()))
        if target_global.y() < available.top():
            target_global.setY(available.top())

    _move_dialog_global(dialog, target_global)


def schedule_fit_dialog_to_anchor(
    dialog: QDialog,
    anchor: QWidget,
    *,
    margin: int = 12,
) -> None:
    """Re-apply anchor positioning after Qt finishes its own show placement."""

    def apply() -> None:
        if dialog.isVisible():
            fit_dialog_to_anchor(dialog, anchor, margin=margin)

    QTimer.singleShot(0, apply)
    QTimer.singleShot(50, apply)
    QTimer.singleShot(150, apply)
