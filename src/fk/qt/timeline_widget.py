from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Literal

from PySide6.QtCore import Qt, QRectF, QPointF, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import QWidget


@dataclass
class TimelineEntry:
    start: datetime.datetime
    end: datetime.datetime | None
    title: str
    state: Literal['finished', 'voided', 'new', 'running']
    is_planned: bool
    is_rest: bool = False


class TimelineWidget(QWidget):
    _entries: list[TimelineEntry]
    _colors: dict[str, QColor]
    _axis_x: int = 40
    _item_height: int = 56
    _rest_item_height: int = 44
    _top_margin: int = 16

    def __init__(self, theme_variables: dict[str, str], parent=None):
        super().__init__(parent)
        self._entries = []
        t = theme_variables
        self._colors = {
            'bg': QColor(t.get('PRIMARY_BG_COLOR', '#ffffff')),
            'secondary': QColor(t.get('SECONDARY_BG_COLOR', '#f7f8fa')),
            'text': QColor(t.get('TABLE_TEXT_COLOR', '#000000')),
            'border': QColor(t.get('BORDER_COLOR', '#d7d8da')),
            'dim': QColor(t.get('TABLE_CROSSOUT_COLOR', '#777777')),
            'selection': QColor(t.get('SELECTION_BG_COLOR', '#cfdefc')),
        }
        self.setMinimumHeight(120)

    def set_entries(self, entries: list[TimelineEntry]):
        real_entries = [e for e in entries if not e.is_rest]
        real_entries = sorted(real_entries, key=lambda e: e.start)

        if not real_entries:
            self._entries = []
            self.setMinimumHeight(120)
            self.update()
            return

        ref = real_entries[0].start
        tzinfo = ref.tzinfo
        ref_date = ref.date()

        rest_lunch = self._make_rest_entry(12, 14, '午休', ref_date, tzinfo)
        rest_dinner = self._make_rest_entry(18, 19, '晚休', ref_date, tzinfo)

        merged: list[TimelineEntry] = list(real_entries)
        merged.append(rest_lunch)
        merged.append(rest_dinner)
        merged = sorted(merged, key=lambda e: e.start)

        self._entries = merged

        height = self._top_margin * 2
        for e in self._entries:
            height += self._rest_item_height if e.is_rest else self._item_height
        self.setMinimumHeight(max(height, 120))
        self.update()

    def _make_rest_entry(self, start_hour: int, end_hour: int, label: str,
                         ref_date: datetime.date, tzinfo) -> TimelineEntry:
        return TimelineEntry(
            start=datetime.datetime.combine(ref_date, datetime.time(start_hour, 0), tzinfo=tzinfo),
            end=datetime.datetime.combine(ref_date, datetime.time(end_hour, 0), tzinfo=tzinfo),
            title=f'{label} {start_hour:02d}:00-{end_hour:02d}:00',
            state='finished',
            is_planned=False,
            is_rest=True,
        )

    def sizeHint(self):
        height = self._top_margin * 2
        for e in self._entries:
            height += self._rest_item_height if e.is_rest else self._item_height
        return QSize(self.width(), max(height, 120))

    def _state_color(self, state: str) -> QColor:
        if state == 'finished':
            return QColor('dodgerblue')
        elif state == 'voided':
            return QColor('orangered')
        elif state == 'running':
            return QColor('forestgreen')
        else:
            return QColor('lightgray')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        painter.fillRect(self.rect(), self._colors['bg'])

        if not self._entries:
            painter.setPen(self._colors['dim'])
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, '当天无番茄钟记录')
            painter.end()
            return

        y = self._top_margin
        axis_bottom = y
        for e in self._entries:
            axis_bottom += self._rest_item_height if e.is_rest else self._item_height
        axis_x = self._axis_x

        painter.setPen(QPen(self._colors['border'], 2.0))
        painter.drawLine(QPointF(axis_x, self._top_margin), QPointF(axis_x, axis_bottom))

        for entry in self._entries:
            item_h = self._rest_item_height if entry.is_rest else self._item_height
            cy = y + item_h / 2.0

            if entry.is_rest:
                if entry.start.hour < 15:
                    anchor_color = QColor('#FFB300')
                else:
                    anchor_color = QColor('#9C27B0')
                painter.setBrush(QBrush(anchor_color))
                painter.setPen(QPen(self._colors['bg'], 2.0))
                painter.drawEllipse(QPointF(axis_x, cy), 7.0, 7.0)

                rest_font = QFont(self.font())
                rest_font.setPointSize(max(self.font().pointSize() - 1, 8))
                rest_font.setItalic(True)
                painter.setFont(rest_font)
                painter.setPen(self._colors['dim'])
                text_rect = QRectF(axis_x + 16, y, w - axis_x - 24, item_h)
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, entry.title)
            else:
                dot_color = self._state_color(entry.state)
                painter.setBrush(QBrush(dot_color))
                painter.setPen(QPen(self._colors['bg'], 2.0))
                painter.drawEllipse(QPointF(axis_x, cy), 6.0, 6.0)

                card_x = axis_x + 20.0
                card_w = w - card_x - 8.0
                card_h = item_h - 8.0
                card_rect = QRectF(card_x, y + 4.0, card_w, card_h)

                if entry.state == 'finished':
                    card_bg = QColor(200, 230, 200, 80)
                    painter.setBrush(QBrush(card_bg))
                else:
                    painter.setBrush(QBrush(self._colors['secondary']))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(card_rect, 6.0, 6.0)
                painter.setPen(QPen(self._colors['border'], 1.0))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(card_rect, 6.0, 6.0)

                time_str = entry.start.strftime('%H:%M')
                if entry.end is not None:
                    time_str += ' – ' + entry.end.strftime('%H:%M')
                else:
                    time_str += ' – …'

                time_font = QFont(self.font())
                time_font.setBold(True)
                time_font.setPointSize(max(self.font().pointSize(), 9))
                painter.setFont(time_font)
                painter.setPen(self._colors['text'])
                text_rect = QRectF(card_x + 10, y + 6, card_w - 20, card_h / 2)
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, time_str)

                title_font = QFont(self.font())
                title_font.setPointSize(max(self.font().pointSize() - 1, 8))
                painter.setFont(title_font)
                if entry.state == 'voided':
                    painter.setPen(self._colors['dim'])
                else:
                    painter.setPen(self._colors['text'])
                title_rect = QRectF(card_x + 10, y + 6 + card_h / 2, card_w - 20, card_h / 2)
                painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, entry.title)

            y += item_h

        painter.end()
