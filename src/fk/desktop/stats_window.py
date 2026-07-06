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
import datetime
from calendar import monthrange
from typing import Callable

from PySide6 import QtUiTools
from PySide6.QtCharts import QChart, QBarSet, QBarCategoryAxis, QValueAxis, QChartView, QStackedBarSeries
from PySide6.QtCore import Qt, QObject, QFile, QMargins
from PySide6.QtGui import QAction, QPainter, QColor, QFont
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QToolButton, QHBoxLayout, QScrollArea

from fk.core.abstract_event_source import AbstractEventSource
from fk.core.pomodoro import POMODORO_TYPE_NORMAL
from fk.qt.calendar_widget import CalendarWidget
from fk.qt.timeline_widget import TimelineWidget, TimelineEntry


class StatsWindow(QObject):
    _chart: QChart
    _chart_view: QChartView
    _source: AbstractEventSource
    _stats_window: QMainWindow
    _header_text: QLabel
    _header_subtext: QLabel
    _period_actions: dict[str, QAction]
    _prev_action: QAction
    _next_action: QAction

    _to: datetime.datetime
    _period: str

    _series: QStackedBarSeries
    _axis_x: QBarCategoryAxis
    _axis_y: QValueAxis
    _bars: dict[str, QBarSet]

    _color_highlight: QColor
    _color_primary: QColor
    _color_secondary: QColor

    _day_container: QWidget
    _calendar: CalendarWidget
    _timeline: TimelineWidget

    def __init__(self,
                 parent: QWidget,
                 header_font: QFont,
                 theme_variables: dict[str, str],
                 source: AbstractEventSource):
        super().__init__(parent)
        self._source = source
        self._period = 'day'
        self._reset_to(self._period)
        self._init_colors(theme_variables)

        file = QFile(":/stats.ui")
        file.open(QFile.OpenModeFlag.ReadOnly)
        # noinspection PyTypeChecker
        self._stats_window: QMainWindow = QtUiTools.QUiLoader().load(file, parent)
        file.close()

        # noinspection PyTypeChecker
        self._header_text = self._stats_window.findChild(QLabel, "statsHeaderText")
        self._header_text.setFont(header_font)

        # noinspection PyTypeChecker
        self._header_subtext = self._stats_window.findChild(QLabel, "statsHeaderSubtext")
        self._period_actions = {
            'year': self._create_checkable_action('year', 'Ctrl+Y'),
            'month6': self._create_checkable_action('month6', 'Ctrl+H'),
            'month': self._create_checkable_action('month', 'Ctrl+M'),
            'week': self._create_checkable_action('week', 'Ctrl+W'),
            'day': self._create_checkable_action('day', 'Ctrl+D'),
        }
        self._period_actions['day'].setChecked(True)
        self._prev_action = self._create_simple_action('prev', self._prev)
        self._prev_action.setShortcut('Left')
        self._next_action = self._create_simple_action('next', self._next)
        self._next_action.setShortcut('Right')

        close_action = QAction('Close', self._stats_window)
        close_action.triggered.connect(self._stats_window.close)
        close_action.setShortcut('Esc')
        self._stats_window.addAction(close_action)

        chart = QChart()
        self._chart = chart
        axis_x = QBarCategoryAxis(self)
        f = axis_x.labelsFont()
        f.setPointSize(round(f.pointSize() * 0.8))
        axis_x.setLabelsFont(f)
        axis_x.setGridLineVisible(False)
        self._axis_x = axis_x
        axis_y = QValueAxis(self)
        self._axis_y = axis_y
        axis_y.setLabelFormat('%d')
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        self._series = QStackedBarSeries(self)
        chart.addSeries(self._series)
        self._series.attachAxis(self._axis_x)
        self._series.attachAxis(self._axis_y)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        chart.setMargins(QMargins(10, 0, 10, 0))

        # noinspection PyTypeChecker
        layout: QVBoxLayout = self._stats_window.findChild(QVBoxLayout, "statsGraph")
        view = QChartView(chart, self._stats_window)
        view.setObjectName('statsView')
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._chart_view = view

        chart.setBackgroundVisible(False)
        chart.setPlotAreaBackgroundVisible(False)
        layout.addWidget(view)

        # Day view container (calendar + timeline)
        self._day_container = QWidget(self._stats_window)
        self._day_container.setObjectName('statsView')
        day_layout = QHBoxLayout(self._day_container)
        day_layout.setContentsMargins(15, 10, 15, 10)
        day_layout.setSpacing(15)

        self._calendar = CalendarWidget(theme_variables, self._day_container)
        day_layout.addWidget(self._calendar, 1)

        self._timeline_scroll = QScrollArea(self._day_container)
        self._timeline_scroll.setWidgetResizable(True)
        self._timeline_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._timeline_inner = QWidget()
        self._timeline_inner.setObjectName('statsView')
        tl_layout = QVBoxLayout(self._timeline_inner)
        tl_layout.setContentsMargins(0, 0, 0, 0)
        self._timeline = TimelineWidget(theme_variables, self._timeline_inner)
        tl_layout.addWidget(self._timeline)
        self._timeline_scroll.setWidget(self._timeline_inner)
        day_layout.addWidget(self._timeline_scroll, 2)

        layout.addWidget(self._day_container)
        self._day_container.setVisible(False)

        self._calendar.dateSelected.connect(self._on_date_selected)
        self._calendar.monthChanged.connect(self._on_month_changed)

        self._update_chart('day', self._to)

    def _init_colors(self, theme_variables: dict[str, str]) -> None:
        self._color_primary = QColor(theme_variables['TABLE_TEXT_COLOR'])
        self._color_secondary = QColor(theme_variables['SELECTION_BG_COLOR'])
        self._color_highlight = QColor(theme_variables['FOCUS_TEXT_COLOR'])

    def _style_chart(self) -> None:
        self._bars['finished'].setColor(QColor('dodgerblue'))
        self._bars['canceled'].setColor(QColor('orangered'))

        self._bars['finished'].setBorderColor(self._color_highlight)
        self._bars['canceled'].setBorderColor(self._color_highlight)

        self._chart.legend().setLabelColor(self._color_primary)
        self._axis_x.setLabelsColor(QColor(self._color_primary))
        self._axis_y.setLabelsColor(QColor(self._color_primary))

        self._axis_y.setGridLineColor(QColor(self._color_secondary))

    def _time_delta_for_period(self, period: str, date: datetime.datetime, left: bool):
        date = StatsWindow._drop_time(date, period, True)
        if period == 'week':
            return datetime.timedelta(days=(-7 if left else 7))
        elif period == 'year':
            year = date.year + (-1 if left else 1)
            cmp_date = datetime.datetime(year,
                                         date.month,
                                         min(date.day, monthrange(year, date.month)[1]),
                                         date.hour,
                                         tzinfo=date.tzinfo)
            return cmp_date - date
        elif period == 'day':
            return datetime.timedelta(days=(-1 if left else 1))
        elif period == 'month':
            year = date.year
            month = date.month
            if left:
                if month == 1:
                    month = 12
                    year -= 1
                else:
                    month -= 1
            else:
                if month == 12:
                    month = 1
                    year += 1
                else:
                    month += 1
            cmp_date = datetime.datetime(year,
                                         month,
                                         min(date.day, monthrange(year, month)[1]),
                                         date.hour,
                                         tzinfo=date.tzinfo)
            return cmp_date - date
        elif period == 'month6':
            delta = datetime.timedelta()
            for i in range(6):
                delta += self._time_delta_for_period('month', date + delta, left)
            return delta
        else:
            raise Exception(f'Unexpected period: {period}')

    @staticmethod
    def _drop_time(date: datetime.datetime, period: str, start: bool):
        tz = date.tzinfo
        if period == 'week':
            monday = date - datetime.timedelta(days=date.weekday())
            base = monday if start else (monday + datetime.timedelta(days=6))
            if start:
                return datetime.datetime(base.year, base.month, base.day, 0, 0, 0, tzinfo=tz)
            return datetime.datetime(base.year, base.month, base.day, 23, 59, 59, tzinfo=tz)
        elif period == 'year':
            if start:
                return datetime.datetime(date.year, 1, 1, 0, 0, 0, tzinfo=tz)
            return datetime.datetime(date.year, 12, 31, 23, 59, 59, tzinfo=tz)
        elif period == 'day':
            if start:
                return datetime.datetime(date.year, date.month, date.day, 0, 0, 0, tzinfo=tz)
            return datetime.datetime(date.year, date.month, date.day, 23, 59, 59, tzinfo=tz)
        elif period == 'month':
            last_day = monthrange(date.year, date.month)[1]
            if start:
                return datetime.datetime(date.year, date.month, 1, 0, 0, 0, tzinfo=tz)
            return datetime.datetime(date.year, date.month, last_day, 23, 59, 59, tzinfo=tz)
        elif period == 'month6':
            last_day = monthrange(date.year, date.month)[1]
            if start:
                year = date.year
                month = date.month - 5
                while month < 1:
                    month += 12
                    year -= 1
                return datetime.datetime(year, month, 1, 0, 0, 0, tzinfo=tz)
            return datetime.datetime(date.year, date.month, last_day, 23, 59, 59, tzinfo=tz)
        else:
            raise Exception(f'Unexpected period: {period}')

    def _substep_delta_for_period(self, period: str, date: datetime.datetime, left: bool):
        if period == 'week':
            return self._time_delta_for_period('day', date, left)
        elif period == 'year':
            return self._time_delta_for_period('month', date, left)
        elif period == 'day':
            return datetime.timedelta(hours=(-6 if left else 6))
        elif period == 'month':
            return self._time_delta_for_period('week', date, left)
        elif period == 'month6':
            return self._time_delta_for_period('month', date, left)
        else:
            raise Exception(f'Unexpected period: {period}')

    def _prev(self):
        if self._period == 'day':
            self._calendar.prev_month()
            return
        self._to = StatsWindow._drop_time(self._to, self._period, False)
        self._to += self._time_delta_for_period(self._period, self._to, True)
        self._update_chart(self._period, self._to)

    def _next(self):
        if self._period == 'day':
            self._calendar.next_month()
            return
        self._to = StatsWindow._drop_time(self._to, self._period, False)
        self._to += self._time_delta_for_period(self._period, self._to, False)
        self._update_chart(self._period, self._to)

    @staticmethod
    def _format_date(date: datetime.datetime):
        return date.strftime('%Y-%m-%d')

    def _update_chart(self, period: str, to: datetime.datetime) -> None:
        self._period = period

        if period == 'day':
            self._show_day_view(to)
            return

        self._chart_view.setVisible(True)
        self._day_container.setVisible(False)

        _from: datetime.datetime = (to +
                                    self._time_delta_for_period(period, to, True) +
                                    datetime.timedelta(minutes=1))
        header_subtext = f'Average over {StatsWindow._format_date(_from)} to {StatsWindow._format_date(to)}'
        self._header_subtext.setText(header_subtext)

        d = self.extract_data(period, _from, to)

        completed_count = sum(d[1])
        total_count = completed_count + sum(d[2])
        if total_count > 0:
            completion = round(100 * completed_count / total_count)
            header_text = f'Completed {completed_count} out of {total_count} ({completion}%)'
        else:
            header_text = 'No data'
        self._header_text.setText(header_text)

        self._axis_y.setRange(0, max(d[4]))
        self._axis_x.clear()
        self._axis_x.append(d[0])

        self._bars = {
            'finished': QBarSet("Completed", self),
            'canceled': QBarSet("Voided", self),
        }

        self._series.clear()
        self._series.append(self._bars['finished'])
        self._series.append(self._bars['canceled'])

        [self._bars['finished'].append(i) for i in d[1]]
        [self._bars['canceled'].append(i) for i in d[2]]

        self._style_chart()

    def _show_day_view(self, to: datetime.datetime) -> None:
        self._chart_view.setVisible(False)
        self._day_container.setVisible(True)

        year, month = to.year, to.month
        self._calendar.set_year_month(year, month)

        selected_date = to.date()
        self._calendar.set_selected(selected_date)

        active_days, entries = self._collect_day_data(year, month, selected_date)
        self._calendar.set_active_days(active_days)
        self._timeline.set_entries(entries)

        self._header_text.setText(f'{selected_date.strftime("%Y-%m-%d")}')
        completed = sum(1 for e in entries if e.state == 'finished')
        total = len(entries)
        if total > 0:
            self._header_subtext.setText(f'当天共 {total} 个番茄钟，其中 {completed} 个已完成')
        else:
            self._header_subtext.setText('当天无番茄钟记录')

    def _collect_day_data(self, year: int, month: int, selected_date: datetime.date):
        active_days: set[datetime.date] = set()
        entries: list[TimelineEntry] = []

        for p in self._source.pomodoros():
            if p.get_type() != POMODORO_TYPE_NORMAL:
                continue

            finished = p.is_finished()
            canceled = False
            for interruption in p.values():
                if interruption.is_void():
                    canceled = True
            if not finished and not canceled:
                continue
            when = p.get_last_modified_date().astimezone()
            if when is None:
                continue

            if when.year == year and when.month == month:
                active_days.add(when.date())

            if when.date() == selected_date:
                start = p.get_work_start_date()
                if start is not None:
                    start = start.astimezone()
                else:
                    start = when

                if finished:
                    end = p.get_last_modified_date().astimezone()
                    state = 'finished'
                elif canceled:
                    end = p.get_last_modified_date().astimezone()
                    state = 'voided'

                title = p.get_parent().get_display_name()
                entries.append(TimelineEntry(
                    start=start,
                    end=end,
                    title=title,
                    state=state,
                    is_planned=p.is_planned(),
                ))

        return active_days, entries

    def _on_date_selected(self, d: datetime.date) -> None:
        self._calendar.set_selected(d)
        active_days, entries = self._collect_day_data(d.year, d.month, d)
        self._calendar.set_active_days(active_days)
        self._timeline.set_entries(entries)

        self._header_text.setText(f'{d.strftime("%Y-%m-%d")}')
        completed = sum(1 for e in entries if e.state == 'finished')
        total = len(entries)
        if total > 0:
            self._header_subtext.setText(f'当天共 {total} 个番茄钟，其中 {completed} 个已完成')
        else:
            self._header_subtext.setText('当天无番茄钟记录')

    def _on_month_changed(self, year: int, month: int) -> None:
        selected = self._calendar.get_selected()
        if selected is not None and selected.year == year and selected.month == month:
            active_days, entries = self._collect_day_data(year, month, selected)
        else:
            active_days, _ = self._collect_day_data(year, month, datetime.date(year, month, 1))
            entries = []
        self._calendar.set_active_days(active_days)
        self._timeline.set_entries(entries)

    def _create_checkable_action(self, name: str, shortcut: str) -> QAction:
        # noinspection PyTypeChecker
        button: QToolButton = self._stats_window.findChild(QToolButton, name)
        action = QAction(button.text(), self)
        action.setCheckable(True)
        action.setShortcut(shortcut)
        button.setDefaultAction(action)
        action.triggered.connect(lambda: self.select_period(name))
        return action

    def _create_simple_action(self, name: str, callback: Callable) -> QAction:
        # noinspection PyTypeChecker
        button: QToolButton = self._stats_window.findChild(QToolButton, name)
        action = QAction(button.text(), self)
        button.setDefaultAction(action)
        action.triggered.connect(callback)
        return action

    def _reset_to(self, period):
        self._to = StatsWindow._drop_time(datetime.datetime.now(datetime.timezone.utc).astimezone(), period, False)

    def select_period(self, period: str) -> None:
        for name in self._period_actions:
            action = self._period_actions[name]
            action.setChecked(name == period)
        self._reset_to(period)
        self._update_chart(period, self._to)

    @staticmethod
    def _rotate(lst: list, n: int) -> list:
        return lst[n + 1:] + lst[:n + 1]

    def extract_data(self, group: str, period_from: datetime.datetime, period_to: datetime.datetime):
        if group == 'week':
            cats = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        elif group == 'year':
            cats = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        elif group == 'day':
            cats = [str(i) for i in range(24)]
        elif group == 'month':
            last_day = monthrange(period_to.year, period_to.month)[1]
            cats = [str(i + 1) for i in range(last_day)]
        elif group == 'month6':
            cats = []
            year = period_from.year
            month = period_from.month
            for _ in range(6):
                cats.append(f'{year}-{month:02d}')
                month += 1
                if month > 12:
                    month = 1
                    year += 1
        else:
            raise Exception(f'Grouping by {group} is not implemented')

        list_finished = [0 for _ in cats]
        list_canceled = list_finished.copy()
        list_ready = list_finished.copy()
        list_total = list_finished.copy()

        for p in self._source.pomodoros():
            if p.get_type() != POMODORO_TYPE_NORMAL:
                continue

            finished = p.is_finished()
            canceled = False
            for interruption in p.values():
                if interruption.is_void():
                    canceled = True
            if not finished and not canceled:
                continue
            when = p.get_last_modified_date().astimezone()
            if when is None:
                continue

            if when < period_from or when > period_to:
                continue

            index = 0
            if group == 'week':
                index = when.weekday()
            elif group == 'year':
                index = when.month - 1
            elif group == 'day':
                index = when.hour
            elif group == 'month':
                index = when.day - 1
            elif group == 'month6':
                months_from_start = (when.year - period_from.year) * 12 + (when.month - period_from.month)
                if 0 <= months_from_start < 6:
                    index = months_from_start
                else:
                    continue

            if index < 0 or index >= len(cats):
                continue

            if finished:
                list_finished[index] += 1
            elif canceled:
                list_canceled[index] += 1
            list_total[index] += 1

        return [cats, list_finished, list_canceled, list_ready, list_total]

    def show(self):
        self._stats_window.show()
