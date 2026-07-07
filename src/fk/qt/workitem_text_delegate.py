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
import re
from html import escape

from PySide6.QtCore import QSize, QObject, QModelIndex, QRectF, QPointF, Qt
from PySide6.QtGui import QStaticText, QPainter, QColor, QBrush, QPen, QFont, QFontMetrics
from PySide6.QtWidgets import QStyleOptionViewItem, QStyle, QLineEdit

from fk.core.workitem import Workitem
from fk.qt.abstract_item_delegate import AbstractItemDelegate

TAG_REGEX = re.compile('#(\\w+)')

_APPLE_BLUE = QColor('#007AFF')
_CIRCLE_STROKE = QColor('#C7C7CC')
_SEPARATOR = QColor(0, 0, 0, 24)
_META_COLOR = QColor('#8E8E93')

_CIRCLE_DIAM = 18
_CIRCLE_LEFT_PAD = 12
_TEXT_LEFT_GAP = 12


class WorkitemProgressDelegate(AbstractItemDelegate):
    _text_color: str

    def __init__(self,
                 parent: QObject = None,
                 theme: str = 'mixed',
                 text_color: str = '#000',
                 selection_color: str = '#555',
                 crossout_color: str = '#777'):
        AbstractItemDelegate.__init__(self, parent, theme, selection_color, crossout_color)
        self._text_color = text_color

    def _get_progress(self, workitem: Workitem) -> tuple[int, int, float]:
        total = len(workitem)
        if total == 0:
            return 0, 0, 0.0
        completed = sum(1 for p in workitem.values() if p.is_finished())
        return completed, total, completed / total

    def _get_days_used(self, workitem: Workitem) -> int:
        dates = set()
        for p in workitem.values():
            if p.get_work_start_date() is not None:
                d = p.get_work_start_date().astimezone().date()
                dates.add(d)
            if p.is_finished() and p.get_last_modified_date() is not None:
                d = p.get_last_modified_date().astimezone().date()
                dates.add(d)
        if len(dates) == 0:
            return 0
        return (max(dates) - min(dates)).days + 1

    def _format_title_html(self, workitem: Workitem, is_placeholder: bool, is_done: bool) -> str:
        text = workitem.get_name()
        text = TAG_REGEX.sub('<b>\\1</b>', escape(text, False))
        if is_placeholder:
            color = 'gray'
        elif is_done:
            color = '#8E8E93'
        else:
            color = self._text_color
        return (f'<span '
                f'style="color: {color}; '
                f'">{text}</span>')

    def _get_meta_text(self, workitem: Workitem) -> str:
        completed, total, _ = self._get_progress(workitem)
        days = self._get_days_used(workitem)
        parts = []
        if total > 0:
            parts.append(f'{completed}/{total}')
        if days > 0:
            parts.append(f'{days}天')
        return '   ·   '.join(parts) if parts else ''

    def _draw_circle(self, painter: QPainter, cx: float, cy: float, workitem: Workitem) -> None:
        completed, total, ratio = self._get_progress(workitem)
        is_done = workitem.is_sealed() or (total > 0 and completed >= total)

        radius = _CIRCLE_DIAM / 2.0
        circle_rect = QRectF(cx - radius, cy - radius, _CIRCLE_DIAM, _CIRCLE_DIAM)

        painter.save()
        if is_done:
            painter.setBrush(QBrush(_APPLE_BLUE))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(circle_rect)
            check_pen = QPen(QColor('white'))
            check_pen.setWidthF(2.0)
            check_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            check_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(check_pen)
            p1 = QPointF(cx - 4, cy)
            p2 = QPointF(cx - 1, cy + 3)
            p3 = QPointF(cx + 4, cy - 3)
            painter.drawLine(p1, p2)
            painter.drawLine(p2, p3)
        else:
            if total > 0 and ratio > 0:
                inner_pen = QPen(_APPLE_BLUE)
                inner_pen.setWidthF(1.8)
                painter.setPen(inner_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(circle_rect)
                fill_rect = circle_rect.adjusted(3.5, 3.5, -3.5, -3.5)
                painter.setBrush(QBrush(_APPLE_BLUE))
                painter.setPen(Qt.PenStyle.NoPen)
                span = int(-360 * 16 * ratio)
                painter.drawPie(fill_rect, 90 * 16, span)
            else:
                stroke_pen = QPen(_CIRCLE_STROKE)
                stroke_pen.setWidthF(1.6)
                painter.setPen(stroke_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(circle_rect)
        painter.restore()

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        is_placeholder = index.data(501) == 'drop'
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        workitem: Workitem = index.data(500)
        completed, total, ratio = self._get_progress(workitem)
        is_done = workitem.is_sealed() or (total > 0 and completed >= total)

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, self._selection_brush)

        rect = QRectF(option.rect)
        cx = rect.left() + _CIRCLE_LEFT_PAD + _CIRCLE_DIAM / 2.0
        cy = rect.top() + rect.height() / 2.0
        self._draw_circle(painter, cx, cy, workitem)

        text_left = rect.left() + _CIRCLE_LEFT_PAD + _CIRCLE_DIAM + _TEXT_LEFT_GAP

        meta_text = self._get_meta_text(workitem)
        meta_width = 0
        if meta_text:
            meta_font = QFont(painter.font())
            meta_font.setPointSizeF(max(painter.font().pointSizeF() * 0.85, 8.0))
            fm = QFontMetrics(meta_font)
            meta_width = fm.horizontalAdvance(meta_text) + 16
            painter.save()
            painter.setFont(meta_font)
            painter.setPen(_META_COLOR)
            meta_rect = QRectF(text_left, rect.top(), rect.width() - (text_left - rect.left()) - 8, rect.height())
            painter.drawText(
                meta_rect,
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                meta_text,
            )
            painter.restore()

        st = QStaticText(self._format_title_html(workitem, is_placeholder, is_done))
        title_width = max(rect.width() - (text_left - rect.left()) - meta_width, 20)
        st.setTextWidth(title_width)
        title_h = st.size().height()
        title_y = rect.top() + (rect.height() - title_h) / 2.0
        painter.drawStaticText(QPointF(text_left, title_y), st)

        sep_pen = QPen(_SEPARATOR)
        sep_pen.setWidthF(0.7)
        painter.setPen(sep_pen)
        sep_y = rect.bottom() - 0.5
        painter.drawLine(QPointF(text_left, sep_y), QPointF(rect.right(), sep_y))

        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height() + 12, 44))
        return size

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setMinimumHeight(32)
        editor.setStyleSheet("""
            QLineEdit {
                padding: 6px 10px;
                font-size: 13px;
                border: 1px solid #007AFF;
                border-radius: 6px;
                background: white;
                color: #000;
                selection-background-color: #B4D8FE;
            }
        """)
        return editor

    def updateEditorGeometry(self, editor, option, index):
        rect = option.rect
        text_left_offset = _CIRCLE_LEFT_PAD + _CIRCLE_DIAM + _TEXT_LEFT_GAP
        min_h = 32
        editor_x = rect.x() + text_left_offset
        editor_w = max(rect.width() - text_left_offset - 8, 60)
        if rect.height() < min_h:
            y_offset = (min_h - rect.height()) // 2
            editor_y = max(rect.y() - y_offset, 0)
            editor.setGeometry(editor_x, editor_y, editor_w, min_h)
        else:
            editor.setGeometry(editor_x, rect.y() + (rect.height() - min_h) // 2, editor_w, min_h)
