from __future__ import annotations

import datetime
from calendar import monthrange

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QFont, QFontMetrics, QPen, QBrush
from PySide6.QtWidgets import QWidget


class CalendarWidget(QWidget):
    dateSelected = Signal(datetime.date)
    monthChanged = Signal(int, int)

    _year: int
    _month: int
    _selected: datetime.date | None
    _active_days: set[datetime.date]
    _theme: dict[str, str]
    _colors: dict[str, QColor]

    _week_headers: list[str]
    _header_height: int = 30
    _title_height: int = 36

    def __init__(self, theme_variables: dict[str, str], parent=None):
        super().__init__(parent)
        self._theme = theme_variables
        self._init_colors()
        now = datetime.date.today()
        self._year = now.year
        self._month = now.month
        self._selected = now
        self._active_days = set()
        self._week_headers = ['一', '二', '三', '四', '五', '六', '日']
        self.setMinimumSize(280, 260)
        self.setMouseTracking(True)

    def _init_colors(self):
        t = self._theme
        self._colors = {
            'bg': QColor(t.get('PRIMARY_BG_COLOR', '#ffffff')),
            'secondary': QColor(t.get('SECONDARY_BG_COLOR', '#f7f8fa')),
            'text': QColor(t.get('TABLE_TEXT_COLOR', '#000000')),
            'selection': QColor(t.get('SELECTION_BG_COLOR', '#cfdefc')),
            'border': QColor(t.get('BORDER_COLOR', '#d7d8da')),
            'focus': QColor(t.get('FOCUS_TEXT_COLOR', '#000000')),
            'dim': QColor(t.get('TABLE_CROSSOUT_COLOR', '#777777')),
            'accent': QColor('#1a73e8'),
        }

    def set_active_days(self, days: set[datetime.date]):
        self._active_days = days
        self.update()

    def set_selected(self, d: datetime.date):
        self._selected = d
        self.update()

    def get_selected(self) -> datetime.date | None:
        return self._selected

    def set_year_month(self, year: int, month: int):
        self._year = year
        self._month = month
        self.monthChanged.emit(year, month)
        self.update()

    def prev_month(self):
        if self._month == 1:
            self._year -= 1
            self._month = 12
        else:
            self._month -= 1
        self.set_year_month(self._year, self._month)

    def next_month(self):
        if self._month == 12:
            self._year += 1
            self._month = 1
        else:
            self._month += 1
        self.set_year_month(self._year, self._month)

    def _cell_rect(self, row: int, col: int) -> QRectF:
        w = self.width()
        h = self.height()
        top_offset = self._title_height + self._header_height
        cell_w = w / 7.0
        cell_h = (h - top_offset) / 6.0
        x = col * cell_w
        y = top_offset + row * cell_h
        return QRectF(x, y, cell_w, cell_h)

    def _date_at(self, row: int, col: int) -> datetime.date | None:
        first_weekday = datetime.date(self._year, self._month, 1).weekday()
        day = row * 7 + col - first_weekday + 1
        if day < 1 or day > monthrange(self._year, self._month)[1]:
            return None
        return datetime.date(self._year, self._month, day)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        painter.fillRect(self.rect(), self._colors['bg'])

        title_font = QFont(self.font())
        title_font.setPointSize(max(self.font().pointSize(), 11))
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(self._colors['text'])
        title = f'{self._year} 年 {self._month} 月'
        title_rect = QRectF(0, 0, w, self._title_height)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, title)

        header_font = QFont(self.font())
        header_font.setPointSize(max(self.font().pointSize() - 1, 8))
        painter.setFont(header_font)
        painter.setPen(self._colors['dim'])
        cell_w = w / 7.0
        for i, label in enumerate(self._week_headers):
            rect = QRectF(i * cell_w, self._title_height, cell_w, self._header_height)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

        today = datetime.date.today()
        painter.setFont(self.font())
        for row in range(6):
            for col in range(7):
                d = self._date_at(row, col)
                rect = self._cell_rect(row, col)
                if d is None:
                    continue

                is_current_month = d.month == self._month

                if self._selected is not None and d == self._selected:
                    painter.setBrush(QBrush(self._colors['selection']))
                    painter.setPen(Qt.PenStyle.NoPen)
                    margin = 3.0
                    painter.drawRoundedRect(
                        rect.adjusted(margin, margin, -margin, -margin),
                        8.0, 8.0)
                    painter.setPen(self._colors['focus'])
                elif d == today:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(self._colors['accent'], 1.5))
                    margin = 3.0
                    painter.drawRoundedRect(
                        rect.adjusted(margin, margin, -margin, -margin),
                        8.0, 8.0)
                    if is_current_month:
                        painter.setPen(self._colors['accent'])
                    else:
                        painter.setPen(self._colors['dim'])
                else:
                    if is_current_month:
                        painter.setPen(self._colors['text'])
                    else:
                        painter.setPen(self._colors['dim'])

                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(d.day))

                if d in self._active_days:
                    painter.setBrush(QBrush(self._colors['accent']))
                    painter.setPen(Qt.PenStyle.NoPen)
                    cx = rect.center().x()
                    cy = rect.bottom() - 8.0
                    painter.drawEllipse(QPointF(cx, cy), 3.0, 3.0)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        top_offset = self._title_height + self._header_height
        if pos.y() < top_offset:
            return
        cell_h = (self.height() - top_offset) / 6.0
        cell_w = self.width() / 7.0
        row = int((pos.y() - top_offset) / cell_h)
        col = int(pos.x() / cell_w)
        if 0 <= row < 6 and 0 <= col < 7:
            d = self._date_at(row, col)
            if d is not None:
                self._selected = d
                if d.month != self._month:
                    self._year = d.year
                    self._month = d.month
                    self.monthChanged.emit(self._year, self._month)
                self.dateSelected.emit(d)
                self.update()
