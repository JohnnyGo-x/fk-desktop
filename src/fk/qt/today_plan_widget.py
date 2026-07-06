from __future__ import annotations

import datetime
import json
import logging

from PySide6.QtCore import Qt, QSize, QRectF, Signal, QTimer
from PySide6.QtGui import QColor, QFont, QPalette, QPainter, QBrush, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
    QCheckBox, QSpinBox, QSizePolicy, QPushButton, QDialog,
    QDialogButtonBox, QStyledItemDelegate, QLineEdit,
)

from fk.core.abstract_event_source import AbstractEventSource, start_workitem
from fk.core.abstract_settings import AbstractSettings
from fk.core.event_source_holder import EventSourceHolder, AfterSourceChanged
from fk.core.pomodoro import POMODORO_TYPE_NORMAL
from fk.core.events import SourceMessagesProcessed, AfterPomodoroComplete, AfterPomodoroVoided, TimerWorkComplete, TimerRestComplete
from fk.qt.timeline_widget import TimelineWidget, TimelineEntry

logger = logging.getLogger(__name__)


def _apply_bg(widget: QWidget, color: QColor) -> None:
    widget.setAutoFillBackground(True)
    pal = widget.palette()
    pal.setColor(QPalette.ColorRole.Window, color)
    pal.setColor(QPalette.ColorRole.Base, color)
    widget.setPalette(pal)


class ClickableFrame(QFrame):
    clicked = Signal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class Stepper(QWidget):
    _value: int
    _min: int
    _max: int
    _label: QLabel

    def __init__(self, value: int, min_val: int = 0, max_val: int = 20, parent=None):
        super().__init__(parent)
        self._value = max(min_val, min(value, max_val))
        self._min = min_val
        self._max = max_val

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        btn_common = """
            QPushButton {
                background: #F2F2F7;
                border: 1px solid #D1D1D6;
                color: #1C1C1E;
                font-size: 15px;
                font-weight: bold;
                padding: 0;
            }
            QPushButton:hover { background: #E5E5EA; }
            QPushButton:pressed { background: #D1D1D6; }
            QPushButton:disabled { color: #C7C7CC; }
        """

        self._minus = QPushButton('−')
        self._minus.setCursor(Qt.CursorShape.PointingHandCursor)
        self._minus.setFixedSize(28, 28)
        self._minus.setStyleSheet(btn_common + """
            QPushButton {
                border-top-left-radius: 6px;
                border-bottom-left-radius: 6px;
                border-right: none;
            }
        """)
        self._minus.clicked.connect(self._dec)

        self._label = QLabel(str(self._value))
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setFixedSize(40, 28)
        self._label.setStyleSheet("""
            QLabel {
                background: white;
                color: #1C1C1E;
                border-top: 1px solid #D1D1D6;
                border-bottom: 1px solid #D1D1D6;
                font-weight: 600;
            }
        """)

        self._plus = QPushButton('+')
        self._plus.setCursor(Qt.CursorShape.PointingHandCursor)
        self._plus.setFixedSize(28, 28)
        self._plus.setStyleSheet(btn_common + """
            QPushButton {
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                border-left: none;
            }
        """)
        self._plus.clicked.connect(self._inc)

        layout.addWidget(self._minus)
        layout.addWidget(self._label)
        layout.addWidget(self._plus)
        self._update_buttons()

    def _inc(self):
        if self._value < self._max:
            self._value += 1
            self._label.setText(str(self._value))
            self._update_buttons()

    def _dec(self):
        if self._value > self._min:
            self._value -= 1
            self._label.setText(str(self._value))
            self._update_buttons()

    def _update_buttons(self):
        self._minus.setEnabled(self._value > self._min)
        self._plus.setEnabled(self._value < self._max)

    def value(self) -> int:
        return self._value


class PieChartWidget(QWidget):
    _done: int
    _total: int
    _fg: QColor
    _bg: QColor
    _text_color: QColor

    def __init__(self, done: int, total: int,
                 fg: QColor, bg: QColor, text_color: QColor, parent=None):
        super().__init__(parent)
        self._done = done
        self._total = total
        self._fg = fg
        self._bg = bg
        self._text_color = text_color
        self.setFixedSize(44, 44)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def update_data(self, done: int, total: int) -> None:
        self._done = done
        self._total = total
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(3, 3, self.width() - 6, self.height() - 6)

        painter.setBrush(QBrush(self._bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(rect)

        if self._total > 0 and self._done > 0:
            ratio = min(self._done / self._total, 1.0)
            painter.setBrush(QBrush(self._fg))
            painter.setPen(Qt.PenStyle.NoPen)
            span = int(-360 * 16 * ratio)
            painter.drawPie(rect, 90 * 16, span)

        inner_rect = rect.adjusted(6, 6, -6, -6)
        painter.setBrush(QBrush(QColor(255, 255, 255, 0)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.drawEllipse(inner_rect)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        painter.setPen(self._text_color)
        font = QFont(self.font())
        font.setPointSizeF(max(self.font().pointSizeF() - 1, 8.0))
        font.setBold(True)
        painter.setFont(font)
        text = f'{self._done}/{self._total}' if self._total > 0 else '—'
        painter.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), text)
        painter.end()


class PlanDialog(QDialog):
    _rows: dict
    _theme: dict[str, str]

    def __init__(self, workitems: list, current_state: dict[str, dict],
                 theme_variables: dict[str, str], parent=None):
        super().__init__(parent)
        self.setWindowTitle('规划今日')
        self.resize(560, 480)
        self._rows = {}
        self._theme = theme_variables
        self._all_workitems = workitems

        primary_bg = QColor(theme_variables.get('PRIMARY_BG_COLOR', '#ffffff'))
        secondary_bg = QColor(theme_variables.get('SECONDARY_BG_COLOR', '#f5f7fa'))
        text_color = theme_variables.get('TABLE_TEXT_COLOR', '#000')
        dim_color = theme_variables.get('TABLE_CROSSOUT_COLOR', '#888')

        _apply_bg(self, primary_bg)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel('选择今日要做的任务')
        title_font = QFont(self.font())
        title_font.setPointSize(max(self.font().pointSize() + 4, 15))
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f'color: {text_color}; background: transparent;')
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        _apply_bg(scroll, primary_bg)
        _apply_bg(scroll.viewport(), primary_bg)

        self._list_container = QWidget()
        _apply_bg(self._list_container, primary_bg)
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 8, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch(1)
        scroll.setWidget(self._list_container)
        layout.addWidget(scroll, 1)

        self._current_state = dict(current_state)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('确定')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._rebuild_list()

    def _clear_list(self):
        while self._list_layout.count() > 0:
            item = self._list_layout.takeAt(0)
            w = item.widget() if item is not None else None
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _rebuild_list(self):
        self._clear_list()
        self._rows = {}

        secondary_bg = self._theme.get('SECONDARY_BG_COLOR', '#f5f7fa')
        text_color = self._theme.get('TABLE_TEXT_COLOR', '#000')
        dim_color = self._theme.get('TABLE_CROSSOUT_COLOR', '#888')

        filtered = list(self._all_workitems)

        if not filtered:
            empty = QLabel('暂无可选任务')
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f'color: {dim_color}; background: transparent; padding: 30px;')
            self._list_layout.addWidget(empty)
            self._list_layout.addStretch(1)
            return

        for wi in filtered:
            uid = wi.get_uid()
            plist = list(wi.values())
            total = len(plist)
            done = sum(1 for p in plist if p.is_finished())
            remaining = max(total - done, 0)
            saved = self._current_state.get(uid, {})
            enabled = saved.get('enabled', False)
            count = saved.get('count', remaining if remaining > 0 else 1)

            card = ClickableFrame()
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setStyleSheet(f"""
                QFrame {{
                    background: {secondary_bg};
                    border-radius: 8px;
                }}
                QFrame QLabel {{ background: transparent; color: {text_color}; }}
                QFrame QCheckBox {{ background: transparent; color: {text_color}; }}
            """)
            row = QHBoxLayout(card)
            row.setContentsMargins(12, 8, 12, 8)
            row.setSpacing(10)

            cb = QCheckBox()
            cb.setChecked(enabled)
            cb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            row.addWidget(cb)
            card.clicked.connect(lambda _cb=cb: _cb.setChecked(not _cb.isChecked()))

            name_col = QVBoxLayout()
            name_col.setContentsMargins(0, 0, 0, 0)
            name_col.setSpacing(2)

            backlog_name = ''
            try:
                parent = wi.get_parent()
                if parent is not None:
                    backlog_name = parent.get_name()
            except Exception:
                backlog_name = ''
            if backlog_name:
                bl_label = QLabel(backlog_name)
                bl_label.setStyleSheet(f'color: {dim_color}; background: transparent; font-size: 11px;')
                name_col.addWidget(bl_label)

            name = QLabel(wi.get_display_name())
            name.setWordWrap(True)
            name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            name_col.addWidget(name)
            row.addLayout(name_col, 1)

            progress = QLabel(f'{done}/{total}')
            progress.setStyleSheet(f'color: {dim_color}; background: transparent;')
            row.addWidget(progress)

            spin = Stepper(count, 0, 20)
            row.addWidget(spin)

            self._list_layout.addWidget(card)
            self._rows[uid] = (cb, spin)

        self._list_layout.addStretch(1)

    def get_result(self) -> dict[str, dict]:
        return {
            uid: {'enabled': cb.isChecked(), 'count': spin.value()}
            for uid, (cb, spin) in self._rows.items()
            if cb.isChecked()
        }


class ReviewDialog(QDialog):
    def __init__(self, source: AbstractEventSource, theme_variables: dict[str, str], parent=None):
        super().__init__(parent)
        self.setWindowTitle('任务回顾')
        self.resize(760, 580)

        primary_bg = QColor(theme_variables.get('PRIMARY_BG_COLOR', '#ffffff'))
        secondary_bg = theme_variables.get('SECONDARY_BG_COLOR', '#f5f7fa')
        text_color = theme_variables.get('TABLE_TEXT_COLOR', '#000')
        dim_color = theme_variables.get('TABLE_CROSSOUT_COLOR', '#888')
        border_color = theme_variables.get('BORDER_COLOR', '#ddd')

        _apply_bg(self, primary_bg)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)

        title = QLabel('任务回顾')
        title_font = QFont(self.font())
        title_font.setPointSize(max(self.font().pointSize() + 6, 18))
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f'color: {text_color}; background: transparent;')
        outer.addWidget(title)

        # Compute overall stats
        all_backlogs = list(source.backlogs())
        total_tasks = 0
        done_tasks = 0
        total_seconds = 0.0
        all_dates = set()
        for bl in all_backlogs:
            for wi in bl.values():
                total_tasks += 1
                plist = list(wi.values())
                completed = sum(1 for p in plist if p.is_finished())
                if len(plist) > 0 and completed >= len(plist):
                    done_tasks += 1
                for p in plist:
                    if p.is_finished():
                        total_seconds += p.get_work_duration() or 0
                        when = p.get_last_modified_date()
                        if when is not None:
                            all_dates.add(when.astimezone().date())

        summary_text = (
            f'累计任务 {total_tasks} 个 · '
            f'已完成 {done_tasks} 个 · '
            f'总耗时 {self._fmt_duration(total_seconds)} · '
            f'累计天数 {len(all_dates)}'
        )
        summary = QLabel(summary_text)
        summary.setStyleSheet(f'color: {dim_color}; background: transparent;')
        outer.addWidget(summary)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet(f'background: {border_color}; border: none;')
        outer.addWidget(divider)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        _apply_bg(scroll, primary_bg)
        _apply_bg(scroll.viewport(), primary_bg)

        container = QWidget()
        _apply_bg(container, primary_bg)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 8, 0)
        c_layout.setSpacing(14)

        section_font = QFont(self.font())
        section_font.setPointSize(max(self.font().pointSize() + 2, 13))
        section_font.setBold(True)

        sub_font = QFont(self.font())
        sub_font.setPointSize(max(self.font().pointSize() - 1, 9))

        if not all_backlogs:
            empty = QLabel('暂无数据')
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f'color: {dim_color}; background: transparent; padding: 40px;')
            c_layout.addWidget(empty)

        for bl in all_backlogs:
            workitems = list(bl.values())
            if not workitems:
                continue

            bl_total_tasks = len(workitems)
            bl_done_tasks = 0
            bl_total_seconds = 0.0
            bl_dates = set()
            for wi in workitems:
                plist = list(wi.values())
                completed = sum(1 for p in plist if p.is_finished())
                if len(plist) > 0 and completed >= len(plist):
                    bl_done_tasks += 1
                for p in plist:
                    if p.is_finished():
                        bl_total_seconds += p.get_work_duration() or 0
                        when = p.get_last_modified_date()
                        if when is not None:
                            bl_dates.add(when.astimezone().date())

            bl_header = QLabel(bl.get_name())
            bl_header.setFont(section_font)
            bl_header.setStyleSheet(f'color: {text_color}; background: transparent;')
            c_layout.addWidget(bl_header)

            bl_summary = QLabel(
                f'{bl_done_tasks}/{bl_total_tasks} 完成 · '
                f'{self._fmt_duration(bl_total_seconds)} · '
                f'{len(bl_dates)} 天'
            )
            bl_summary.setStyleSheet(f'color: {dim_color}; background: transparent;')
            bl_summary.setFont(sub_font)
            c_layout.addWidget(bl_summary)

            for wi in workitems:
                plist = list(wi.values())
                total = len(plist)
                completed = sum(1 for p in plist if p.is_finished())
                dates = set()
                seconds = 0.0
                first_when = None
                last_when = None
                for p in plist:
                    if p.is_finished():
                        seconds += p.get_work_duration() or 0
                        when = p.get_last_modified_date()
                        if when is not None:
                            d = when.astimezone().date()
                            dates.add(d)
                            if first_when is None or d < first_when:
                                first_when = d
                            if last_when is None or d > last_when:
                                last_when = d

                is_done = wi.is_sealed() or (total > 0 and completed >= total)

                card = QFrame()
                card.setStyleSheet(f"""
                    QFrame {{
                        background: {secondary_bg};
                        border-radius: 10px;
                    }}
                    QFrame QLabel {{ background: transparent; }}
                """)
                row = QHBoxLayout(card)
                row.setContentsMargins(14, 10, 14, 10)
                row.setSpacing(12)

                pie = PieChartWidget(
                    done=completed,
                    total=total,
                    fg=QColor('#4CAF50') if is_done else QColor('#007AFF'),
                    bg=QColor(border_color),
                    text_color=QColor(text_color),
                )
                row.addWidget(pie)

                info_col = QVBoxLayout()
                info_col.setContentsMargins(0, 0, 0, 0)
                info_col.setSpacing(3)

                name_label = QLabel(wi.get_display_name())
                name_font = QFont(self.font())
                name_font.setPointSize(max(self.font().pointSize() + 1, 12))
                name_font.setBold(True)
                if is_done:
                    name_font.setStrikeOut(True)
                name_label.setFont(name_font)
                name_label.setWordWrap(True)
                name_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
                name_label.setStyleSheet(
                    f'color: {"#8E8E93" if is_done else text_color}; background: transparent;'
                )
                info_col.addWidget(name_label)

                parts = [f'{completed}/{total} 番茄钟']
                parts.append(f'{self._fmt_duration(seconds)}')
                if len(dates) > 0:
                    parts.append(f'{len(dates)} 天')
                if first_when is not None and last_when is not None and first_when != last_when:
                    parts.append(f'{first_when.strftime("%m/%d")} → {last_when.strftime("%m/%d")}')
                elif first_when is not None:
                    parts.append(first_when.strftime("%m/%d"))

                detail = QLabel('   ·   '.join(parts))
                detail.setStyleSheet(f'color: {dim_color}; background: transparent;')
                detail.setWordWrap(True)
                detail.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
                info_col.addWidget(detail)

                row.addLayout(info_col, 1)
                c_layout.addWidget(card)

        c_layout.addStretch(1)
        scroll.setWidget(container)
        outer.addWidget(scroll, 1)

        close_btn = QPushButton('关闭')
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(80)
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_row.addWidget(close_btn)
        outer.addLayout(close_row)

    @staticmethod
    def _fmt_duration(seconds: float) -> str:
        if seconds <= 0:
            return '0 分钟'
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        if hours > 0:
            return f'{hours} 小时 {minutes} 分'
        return f'{minutes} 分钟'


class TodayPlanWidget(QWidget):
    _source: AbstractEventSource
    _settings: AbstractSettings
    _theme: dict[str, str]
    _timeline: TimelineWidget
    _subheader_label: QLabel
    _cards_container: QWidget
    _cards_layout: QVBoxLayout
    _plan_state: dict[str, dict]
    _has_planned: bool
    _primary_bg: QColor
    _secondary_bg: QColor
    _text_color: QColor
    _dim_color: QColor
    _border_color: QColor
    _accent_color: QColor
    _card_widgets: dict[str, QWidget]
    _hint_widget: QWidget | None
    _refresh_timer: QTimer
    _refresh_pending: bool

    def __init__(self, theme_variables: dict[str, str], source_holder: EventSourceHolder, parent=None):
        super().__init__(parent)
        self.setObjectName('today_plan_widget')
        self._theme = theme_variables
        self._source = None
        self._settings = source_holder.get_settings()
        self._plan_state = {}
        self._has_planned = False
        self._card_widgets = {}
        self._hint_widget = None
        self._refresh_pending = False

        self._primary_bg = QColor(theme_variables.get('PRIMARY_BG_COLOR', '#ffffff'))
        self._secondary_bg = QColor(theme_variables.get('SECONDARY_BG_COLOR', '#f5f7fa'))
        self._text_color = QColor(theme_variables.get('TABLE_TEXT_COLOR', '#000'))
        self._dim_color = QColor(theme_variables.get('TABLE_CROSSOUT_COLOR', '#888'))
        self._border_color = QColor(theme_variables.get('BORDER_COLOR', '#ddd'))
        self._accent_color = QColor('#4CAF50')

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        _apply_bg(self, self._primary_bg)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(12)

        head_row = QHBoxLayout()
        header_label = QLabel('今日安排')
        header_font = QFont(self.font())
        header_font.setPointSize(max(self.font().pointSize() + 8, 20))
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet(f'color: {self._text_color.name()}; background: transparent;')
        head_row.addWidget(header_label)
        head_row.addStretch(1)

        self._plan_button = QPushButton('规划今日')
        self._plan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._plan_button.setStyleSheet(f"""
            QPushButton {{
                background: {self._accent_color.name()};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #45a049; }}
        """)
        self._plan_button.clicked.connect(self._on_plan_clicked)
        head_row.addWidget(self._plan_button)

        self._review_button = QPushButton('回顾')
        self._review_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._review_button.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self._text_color.name()};
                border: 1px solid {self._border_color.name()};
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: {self._secondary_bg.name()}; }}
        """)
        self._review_button.clicked.connect(self._on_review_clicked)
        head_row.addWidget(self._review_button)
        outer.addLayout(head_row)

        self._subheader_label = QLabel('')
        sub_font = QFont(self.font())
        sub_font.setPointSize(max(self.font().pointSize() + 1, 11))
        self._subheader_label.setFont(sub_font)
        self._subheader_label.setStyleSheet(f'color: {self._dim_color.name()}; background: transparent;')
        outer.addWidget(self._subheader_label)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet(f'background: {self._border_color.name()}; border: none;')
        outer.addWidget(divider)

        section_font = QFont(self.font())
        section_font.setPointSize(max(self.font().pointSize() + 2, 13))
        section_font.setBold(True)

        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(20)

        # Left: today's tasks
        left_col = QWidget()
        _apply_bg(left_col, self._primary_bg)
        left_col.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        left_title = QLabel('今日任务')
        left_title.setFont(section_font)
        left_title.setStyleSheet(f'color: {self._text_color.name()}; background: transparent;')
        left_layout.addWidget(left_title)

        cards_scroll = QScrollArea()
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        _apply_bg(cards_scroll, self._primary_bg)
        _apply_bg(cards_scroll.viewport(), self._primary_bg)

        self._cards_container = QWidget()
        _apply_bg(self._cards_container, self._primary_bg)
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 8, 0)
        self._cards_layout.setSpacing(10)
        self._cards_layout.addStretch(1)
        cards_scroll.setWidget(self._cards_container)
        left_layout.addWidget(cards_scroll, 1)

        # Right: timeline
        right_col = QWidget()
        _apply_bg(right_col, self._primary_bg)
        right_col.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        timeline_title = QLabel('今日进度')
        timeline_title.setFont(section_font)
        timeline_title.setStyleSheet(f'color: {self._text_color.name()}; background: transparent;')
        right_layout.addWidget(timeline_title)

        timeline_scroll = QScrollArea()
        timeline_scroll.setWidgetResizable(True)
        timeline_scroll.setFrameShape(QFrame.Shape.NoFrame)
        _apply_bg(timeline_scroll, self._primary_bg)
        _apply_bg(timeline_scroll.viewport(), self._primary_bg)

        timeline_inner = QWidget()
        _apply_bg(timeline_inner, self._primary_bg)
        tl_layout = QVBoxLayout(timeline_inner)
        tl_layout.setContentsMargins(0, 0, 0, 0)
        self._timeline = TimelineWidget(theme_variables, timeline_inner)
        tl_layout.addWidget(self._timeline)
        timeline_scroll.setWidget(timeline_inner)
        right_layout.addWidget(timeline_scroll, 1)

        columns.addWidget(left_col, 1)
        columns.addWidget(right_col, 1)
        outer.addLayout(columns, 1)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._do_refresh)

        self._load_plan_state()

        source_holder.on(AfterSourceChanged, self._on_source_changed)

    def _load_plan_state(self) -> None:
        try:
            s = json.loads(self._settings.get('Application.today_plan_settings') or '{}')
        except (json.JSONDecodeError, TypeError):
            s = {}
        self._plan_state = s.get('plan_state', {})
        self._has_planned = bool(s.get('has_planned', False))

    def _save_plan_state(self) -> None:
        self._settings.set({
            'Application.today_plan_settings': json.dumps({
                'plan_state': self._plan_state,
                'has_planned': self._has_planned,
            })
        })

    def _on_source_changed(self, event: str, source: AbstractEventSource) -> None:
        self._source = source
        self._load_plan_state()
        source.on(SourceMessagesProcessed, self._on_data_loaded)
        source.on(AfterPomodoroComplete, self._on_data_loaded)
        source.on(AfterPomodoroVoided, self._on_data_loaded)
        source.on(TimerWorkComplete, self._on_data_loaded)
        source.on(TimerRestComplete, self._on_data_loaded)
        self.refresh()

    def _on_data_loaded(self, event: str, source: AbstractEventSource, **kwargs) -> None:
        self.refresh()

    def _get_all_incomplete_workitems(self) -> list:
        if self._source is None:
            return []
        items = []
        for wi in self._source.workitems():
            if wi.is_sealed():
                continue
            plist = list(wi.values())
            if len(plist) == 0:
                continue
            done = sum(1 for p in plist if p.is_finished())
            if done >= len(plist):
                continue
            items.append(wi)
        return items

    def _on_plan_clicked(self):
        if self._source is None:
            return
        workitems = self._get_all_incomplete_workitems()
        dialog = PlanDialog(workitems, self._plan_state, self._theme, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._plan_state = dialog.get_result()
            self._has_planned = True
            self._save_plan_state()
            self.refresh()

    def _on_review_clicked(self):
        if self._source is None:
            return
        dialog = ReviewDialog(self._source, self._theme, self)
        dialog.exec()

    def _remove_card(self, uid: str) -> None:
        w = self._card_widgets.pop(uid, None)
        if w is not None:
            self._cards_layout.removeWidget(w)
            w.setParent(None)
            w.hide()
            w.deleteLater()

    def _find_workitem(self, uid: str):
        if self._source is None:
            return None
        for wi in self._source.workitems():
            if wi.get_uid() == uid:
                return wi
        return None

    def _count_workitem_done_today(self, wi) -> int:
        today = datetime.date.today()
        count = 0
        for p in wi.values():
            if not p.is_finished():
                continue
            when = p.get_last_modified_date()
            if when is None:
                continue
            if when.astimezone().date() != today:
                continue
            count += 1
        return count

    def _make_card(self, wi, planned_count: int) -> QWidget:
        plist = list(wi.values())
        total = len(plist)
        done_today = self._count_workitem_done_today(wi)

        card = QFrame()
        _apply_bg(card, self._secondary_bg)
        card.setStyleSheet(f"""
            QFrame {{
                background: {self._secondary_bg.name()};
                border-radius: 12px;
            }}
            QFrame QLabel {{ background: transparent; color: {self._text_color.name()}; }}
        """)
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 12, 14, 12)
        row.setSpacing(14)

        pie_total = planned_count if planned_count > 0 else max(total, 1)
        pie_done = min(done_today, pie_total)
        pie = PieChartWidget(
            done=pie_done,
            total=pie_total,
            fg=self._accent_color,
            bg=QColor(self._border_color),
            text_color=self._text_color,
        )
        pie.setObjectName('pie_chart')
        row.addWidget(pie)

        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(3)

        backlog_name = ''
        try:
            parent = wi.get_parent()
            if parent is not None:
                backlog_name = parent.get_name()
        except Exception:
            backlog_name = ''
        if backlog_name:
            bl_label = QLabel(backlog_name)
            bl_label.setStyleSheet(f'color: {self._dim_color.name()}; background: transparent; font-size: 11px;')
            bl_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            info_col.addWidget(bl_label)

        name_label = QLabel(wi.get_display_name())
        name_font = QFont(self.font())
        name_font.setPointSize(max(self.font().pointSize() + 1, 12))
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setWordWrap(True)
        name_label.setMinimumWidth(0)
        name_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        info_col.addWidget(name_label)

        remaining = max(planned_count - done_today, 0)
        detail_text = f'计划 {planned_count} · 完成 {done_today} · 剩余 {remaining}'
        detail_label = QLabel(detail_text)
        detail_label.setStyleSheet(f'color: {self._dim_color.name()}; background: transparent;')
        detail_label.setWordWrap(True)
        detail_label.setMinimumWidth(0)
        detail_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        info_col.addWidget(detail_label)

        row.addLayout(info_col, 1)

        start_btn = QPushButton('开始')
        start_btn.setObjectName('start_btn')
        start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_btn.setFixedWidth(64)
        start_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        start_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self._accent_color.name()};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #45a049; }}
            QPushButton:disabled {{ background: #cccccc; color: #666666; }}
        """)
        if wi.is_sealed() or (planned_count > 0 and done_today >= planned_count):
            start_btn.setEnabled(False)
            start_btn.setText('已完成')
        start_btn.clicked.connect(lambda _, w=wi: self._on_start_clicked(w))
        row.addWidget(start_btn)

        return card

    def _on_start_clicked(self, wi):
        if self._source is None:
            return
        try:
            start_workitem(wi, self._source)
        except Exception as ex:
            logger.warning('Failed to start workitem: %s', ex)

    def _count_completed_today(self) -> int:
        if self._source is None:
            return 0
        today = datetime.date.today()
        count = 0
        for p in self._source.pomodoros():
            if p.get_type() != POMODORO_TYPE_NORMAL:
                continue
            if not p.is_finished():
                continue
            when = p.get_last_modified_date()
            if when is None:
                continue
            if when.astimezone().date() != today:
                continue
            count += 1
        return count

    def _update_summary(self) -> None:
        today = datetime.date.today()
        completed = self._count_completed_today()
        planned = sum(s.get('count', 0) for s in self._plan_state.values() if s.get('enabled'))
        weekdays_cn = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        base = f'{today.strftime("%Y-%m-%d")}    {weekdays_cn[today.weekday()]}'
        if self._has_planned:
            self._subheader_label.setText(
                f'{base}    ·    计划 {planned} 个    ·    已完成 {completed} 个'
            )
        else:
            self._subheader_label.setText(
                f'{base}    ·    尚未规划    ·    今日已完成 {completed} 个'
            )

    def refresh(self) -> None:
        if not self._refresh_pending:
            self._refresh_pending = True
            self._refresh_timer.start(0)

    def _do_refresh(self) -> None:
        self._refresh_pending = False
        if self._source is None:
            return

        today = datetime.date.today()

        entries: list[TimelineEntry] = []
        for p in self._source.pomodoros():
            if p.get_type() != POMODORO_TYPE_NORMAL:
                continue
            if not p.is_finished():
                continue
            when = p.get_last_modified_date()
            if when is None:
                continue
            when = when.astimezone()
            if when.date() != today:
                continue
            start = p.get_work_start_date()
            start = start.astimezone() if start is not None else when
            entries.append(TimelineEntry(
                start=start,
                end=when,
                title=p.get_parent().get_display_name(),
                state='finished',
                is_planned=p.is_planned(),
            ))
        self._timeline.set_entries(entries)

        should_show_hint = False
        hint_text = '点击右上角"规划今日"按钮开始安排今日任务'

        if not self._has_planned or not self._plan_state:
            should_show_hint = True
        else:
            desired = {}
            for uid, state in self._plan_state.items():
                if not state.get('enabled'):
                    continue
                wi = self._find_workitem(uid)
                if wi is None:
                    continue
                desired[uid] = state.get('count', 0)

            if not desired:
                should_show_hint = True
                hint_text = '未选择任何任务，请点击"规划今日"重新选择'
            else:
                for uid in list(self._card_widgets.keys()):
                    if uid not in desired:
                        self._remove_card(uid)

                for uid, planned_count in desired.items():
                    wi = self._find_workitem(uid)
                    if wi is None:
                        self._remove_card(uid)
                        continue
                    if uid in self._card_widgets:
                        self._update_card(uid, wi, planned_count)
                    else:
                        card = self._make_card(wi, planned_count)
                        insert_idx = self._cards_layout.count() - 1
                        if insert_idx < 0:
                            insert_idx = 0
                        self._cards_layout.insertWidget(insert_idx, card)
                        self._card_widgets[uid] = card

        if should_show_hint:
            if self._hint_widget is None:
                self._hint_widget = QLabel(hint_text)
                self._hint_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._hint_widget.setStyleSheet(
                    f'color: {self._dim_color.name()}; background: transparent; padding: 40px;'
                )
                hint_font = QFont(self.font())
                hint_font.setPointSize(max(self.font().pointSize() + 1, 11))
                self._hint_widget.setFont(hint_font)
            else:
                self._hint_widget.setText(hint_text)
            if self._hint_widget.parent() is None:
                insert_idx = self._cards_layout.count() - 1
                if insert_idx < 0:
                    insert_idx = 0
                self._cards_layout.insertWidget(insert_idx, self._hint_widget)
            self._hint_widget.show()
        else:
            if self._hint_widget is not None:
                self._hint_widget.hide()

        if self._cards_layout.count() == 0 or (
            self._cards_layout.count() == 1 and self._cards_layout.itemAt(0).spacerItem() is not None
        ):
            if self._cards_layout.count() == 0:
                self._cards_layout.addStretch(1)

        self._update_summary()

    def _update_card(self, uid: str, wi, planned_count: int) -> None:
        card = self._card_widgets.get(uid)
        if card is None:
            return
        done_today = self._count_workitem_done_today(wi)
        remaining = max(planned_count - done_today, 0)

        pie = card.findChild(QWidget, 'pie_chart')
        if pie is not None and isinstance(pie, PieChartWidget):
            pie_total = planned_count if planned_count > 0 else max(len(list(wi.values())), 1)
            pie.update_data(min(done_today, pie_total), pie_total)

        labels = card.findChildren(QLabel)
        for lbl in labels:
            text = lbl.text()
            if text.startswith('计划 ') or text.startswith('未选择'):
                lbl.setText(f'计划 {planned_count} · 完成 {done_today} · 剩余 {remaining}')

        start_btn = card.findChild(QPushButton, 'start_btn')
        if start_btn is not None:
            if wi.is_sealed() or (planned_count > 0 and done_today >= planned_count):
                start_btn.setEnabled(False)
                start_btn.setText('已完成')
            else:
                start_btn.setEnabled(True)
                start_btn.setText('开始')

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
