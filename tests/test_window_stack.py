"""Tests for topmost-window hit testing."""

from unittest.mock import patch

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication, QWidget

from karaoke_blast.utils import window_stack


def test_cursor_over_topmost_uses_platform_helper(qtbot) -> None:
    widget = QWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)

    with patch.object(
        window_stack,
        "_macos_cursor_over_topmost_application_window",
        return_value=True,
    ) as macos_check:
        with patch.object(window_stack.sys, "platform", "darwin"):
            assert window_stack.cursor_over_topmost_application_window(widget) is True
        macos_check.assert_called_once()


def test_macos_hit_test_returns_false_when_point_not_in_any_window() -> None:
    with patch.object(window_stack, "os") as mock_os:
        mock_os.getpid.return_value = 42
        with patch(
            "ctypes.CDLL",
            side_effect=RuntimeError("no CG"),
        ):
            assert (
                window_stack._macos_cursor_over_topmost_application_window(QPoint(0, 0))
                is False
            )
