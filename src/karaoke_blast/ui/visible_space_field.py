"""Line edit that renders spaces as visible middle dots."""

from __future__ import annotations

from PyQt6.QtCore import QRect, QTimer
from PyQt6.QtGui import QColor, QPainter, QPalette
from PyQt6.QtWidgets import QLineEdit, QStyle, QStyleOptionFrame


class VisibleSpaceLineEdit(QLineEdit):
    """QLineEdit that shows spaces as dimmed middle dots (·)."""

    GHOST_CHAR = "\u00b7"

    def __init__(self, *, trim_edges: bool = True, parent=None) -> None:
        super().__init__(parent)
        self._trim_edges = trim_edges
        self._cursor_visible = True
        self._cursor_blink_timer = QTimer(self)
        self._cursor_blink_timer.setInterval(500)
        self._cursor_blink_timer.timeout.connect(self._toggle_cursor_blink)
        if trim_edges:
            self.editingFinished.connect(self._trim_edges_on_finish)

    def _trim_edges_on_finish(self) -> None:
        if not self._trim_edges:
            return
        trimmed = self.text().strip()
        if trimmed != self.text():
            self.setText(trimmed)

    def _toggle_cursor_blink(self) -> None:
        self._cursor_visible = not self._cursor_visible
        self.update()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self._cursor_visible = True
        self._cursor_blink_timer.start()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._cursor_blink_timer.stop()
        self._cursor_visible = True

    def paintEvent(self, event) -> None:
        text = self.text()
        if not text or " " not in text:
            super().paintEvent(event)
            return

        painter = QPainter(self)
        option = QStyleOptionFrame()
        self.initStyleOption(option)
        self.style().drawPrimitive(
            QStyle.PrimitiveElement.PE_PanelLineEdit, option, painter, self
        )

        contents_rect = self.style().subElementRect(
            QStyle.SubElement.SE_LineEditContents, option, self
        )
        painter.setClipRect(contents_rect)

        palette = self.palette()
        enabled = self.isEnabled()
        if enabled:
            text_color = palette.color(QPalette.ColorRole.Text)
            ghost_color = QColor("#888888")
        else:
            text_color = palette.color(QPalette.ColorRole.Text)
            ghost_color = palette.color(QPalette.ColorRole.Text)

        highlight_bg = palette.color(QPalette.ColorRole.Highlight)
        highlight_fg = palette.color(QPalette.ColorRole.HighlightedText)

        font = self.font()
        painter.setFont(font)
        fm = painter.fontMetrics()
        baseline_y = contents_rect.center().y() + (fm.ascent() - fm.descent()) // 2

        chars = list(text)
        widths = [
            fm.horizontalAdvance(self.GHOST_CHAR if char == " " else char)
            for char in chars
        ]

        cursor_pos = self.cursorPosition()
        sel_start = self.selectionStart()
        sel_len = len(self.selectedText())
        sel_end = sel_start + sel_len if sel_start >= 0 else -1

        content_width = contents_rect.width()
        total_width = sum(widths)
        cursor_x = sum(widths[:cursor_pos])

        scroll = 0
        if cursor_x - scroll > content_width:
            scroll = cursor_x - content_width + fm.horizontalAdvance(self.GHOST_CHAR)
        if cursor_x - scroll < 0:
            scroll = cursor_x
        if total_width - scroll < content_width:
            scroll = max(0, total_width - content_width)

        origin_x = contents_rect.x() - scroll

        if sel_start >= 0 and sel_len > 0:
            sel_x_start = origin_x + sum(widths[:sel_start])
            sel_width = sum(widths[sel_start:sel_end])
            sel_rect = QRect(
                int(sel_x_start),
                contents_rect.y(),
                int(sel_width),
                contents_rect.height(),
            )
            painter.fillRect(sel_rect, highlight_bg)

        x = origin_x
        for index, char in enumerate(chars):
            display_char = self.GHOST_CHAR if char == " " else char
            in_selection = sel_start >= 0 and sel_start <= index < sel_end
            if in_selection:
                painter.setPen(highlight_fg)
            elif char == " ":
                painter.setPen(ghost_color)
            else:
                painter.setPen(text_color)
            painter.drawText(int(x), baseline_y, display_char)
            x += widths[index]

        if self.hasFocus() and self._cursor_visible and not self.isReadOnly():
            cur_x = origin_x + sum(widths[:cursor_pos])
            cursor_height = max(1, contents_rect.height() - 4)
            cursor_y = contents_rect.y() + (contents_rect.height() - cursor_height) // 2
            painter.fillRect(int(cur_x), cursor_y, 1, cursor_height, text_color)
