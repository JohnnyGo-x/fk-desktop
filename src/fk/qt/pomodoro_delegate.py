#  Flowkeeper - Pomodoro timer for power users and teams
#  Copyright (c) 2023 Constantine Kulak
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

from PySide6.QtCore import QSize, QObject, QRectF, QModelIndex, QPointF
from PySide6.QtGui import Qt, QBrush, QPainter, QStaticText, QColor, QPen
from PySide6.QtWidgets import QStyleOptionViewItem

from fk.core.workitem import Workitem
from fk.qt.abstract_item_delegate import AbstractItemDelegate, get_padding

import datetime

_DAY_COLORS = [
    QColor.fromHsl(0, 120, 170),
    QColor.fromHsl(45, 120, 170),
    QColor.fromHsl(90, 120, 170),
    QColor.fromHsl(135, 120, 170),
    QColor.fromHsl(180, 120, 170),
    QColor.fromHsl(225, 120, 170),
    QColor.fromHsl(270, 120, 170),
    QColor.fromHsl(315, 120, 170),
]


class PomodoroDelegate(AbstractItemDelegate):
    _selection_brush: QBrush
    _theme: str
    _cross_out: bool
    _display_tags: bool
    _day_color_map: dict
    _day_color_index: int

    def _get_day_color(self, day: datetime.date) -> QColor:
        if day not in self._day_color_map:
            self._day_color_map[day] = _DAY_COLORS[self._day_color_index % len(_DAY_COLORS)]
            self._day_color_index += 1
        return self._day_color_map[day]

    def __init__(self,
                 parent: QObject = None,
                 theme: str = 'mixed',
                 selection_color: str = '#555',
                 crossout_color: str = '#777',
                 display_tags: bool = False):
        AbstractItemDelegate.__init__(self, parent, theme, selection_color, crossout_color)
        self._display_tags = display_tags
        self._day_color_map = {}
        self._day_color_index = 0

    def _draw_box(self, painter: QPainter, rect: QRectF, state: str, is_planned: bool, day_color: QColor | None):
        margin = 2.0
        inner = rect.adjusted(margin, margin, -margin, -margin)

        border_color = QColor('#888888') if is_planned else QColor('#aaaaaa')
        painter.setPen(QPen(border_color, 1.2))

        if state == 'finished':
            if day_color is not None:
                fill = QColor(day_color.red(), day_color.green(), day_color.blue(), 180)
            else:
                fill = QColor('dodgerblue')
            painter.setBrush(QBrush(fill))
        elif state == 'running':
            painter.setBrush(QBrush(QColor('forestgreen')))
        elif state == 'voided':
            painter.setBrush(QBrush(QColor('orangered')))
        else:
            if is_planned:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            else:
                painter.setBrush(QBrush(QColor(255, 255, 255, 30)))

        painter.drawRoundedRect(inner, 3.0, 3.0)

        if state == 'finished':
            check_color = QColor(255, 255, 255, 200)
            painter.setPen(QPen(check_color, 1.5))
            cx = inner.center().x()
            cy = inner.center().y()
            r = inner.width() * 0.2
            painter.drawLine(QPointF(cx - r, cy), QPointF(cx - r * 0.3, cy + r * 0.7))
            painter.drawLine(QPointF(cx - r * 0.3, cy + r * 0.7), QPointF(cx + r, cy - r * 0.5))
        elif state == 'running':
            painter.setPen(QPen(QColor(255, 255, 255, 200), 1.5))
            cx = inner.center().x()
            cy = inner.center().y()
            r = inner.width() * 0.15
            painter.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))
            painter.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        if index.data(501) == 'pomodoro':
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            space: QRectF = option.rect

            workitem: Workitem = index.data(500)
            self.paint_background(painter, option, False)

            s: QSize = index.data(Qt.ItemDataRole.SizeHintRole)
            height = s.height()

            left = space.left()
            text_padding = get_padding(option)
            padding = max((space.height() - height) / 2.0, 0.0)

            if workitem.is_tracker():
                st = QStaticText(index.data())
                st.setTextWidth(space.width() - 4)
                painter.drawStaticText(left + 4,
                                       space.top() + text_padding,
                                       st)
            else:
                for p in workitem.values():
                    width = height
                    rect = QRectF(left, space.top() + padding, width, height)

                    if p.is_running():
                        state = 'running'
                    elif p.is_finished():
                        state = 'finished'
                    else:
                        state = 'new'

                    day_color = None
                    if p.is_finished():
                        when_date = p.get_last_modified_date().astimezone().date()
                        day_color = self._get_day_color(when_date)

                    self._draw_box(painter, rect, state, p.is_planned(), day_color)
                    left += width

                    for _ in range(len(p)):
                        width = height / 4
                        rect = QRectF(left, space.top() + padding, width, height)
                        self._draw_box(painter, rect, 'voided', p.is_planned(), None)
                        left += width

            painter.restore()
