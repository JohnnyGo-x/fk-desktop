# Flowkeeper (自定义分支)

本仓库基于开源项目 [flowkeeper-org/fk-desktop](https://github.com/flowkeeper-org/fk-desktop)
（原项目作者 Constantine Kulak，GPL-3.0 许可证）进行二次开发，在保留原版番茄钟核心功能的基础上，
针对个人工作流做了一系列界面与交互上的定制改造。

原项目简介：Flowkeeper 是一款专注、独立的番茄钟桌面计时器，面向重度用户，以「把一件事做好」为目标，
是自由开源软件。详见 [flowkeeper.org](https://flowkeeper.org) 。

---

## 主要修改内容

### 1. 新增「今日计划」视图

- 新增 `src/fk/qt/today_plan_widget.py`，实现一个独立的「今日计划」面板，取代默认工作项列表作为主界面。
  - 支持为每个工作项规划当日番茄钟数量，并显示完成进度。
  - 支持一键开始/回顾当天计划，统计当日已完成番茄钟数量。
  - 自定义 `Stepper` 步进器组件用于调整计划番茄数。
  - 自定义 `PlanDialog` 用于集中规划当日各项工作的番茄钟分配。
- 在 `src/fk/desktop/desktop.py` 中新增 `window.todayPlan` 动作与 `toggle_today_plan` 方法，
  通过工具栏切换「今日计划」与「任务列表」两种视图。
  - 默认启动即进入「今日计划」视图，隐藏左侧 backlog 列表面板。
  - 新增 `toolToday` / `toolTasks` 工具按钮用于在两视图间切换。
- 新增 `src/fk/desktop/Flowkeeper.py` 作为可直接运行的入口脚本，便于以 `python -m fk.desktop.Flowkeeper` 方式启动。

### 2. 统计窗口增强：日历 + 时间线

- 新增 `src/fk/qt/calendar_widget.py`：自绘月历组件，支持月份切换、日期点选、高亮当天与有记录的日期。
- 新增 `src/fk/qt/timeline_widget.py`：当天番茄钟时间线组件，按完成状态（已完成/进行中/已作废）着色，
  并自动插入「午休」「晚休」分隔条目。
- 在 `src/fk/desktop/stats_window.py` 中将统计默认周期从「周」改为「日」，
  并新增日视图容器（日历 + 时间线），与原有柱状图并存，按所选周期切换显示。
- 修复 `_drop_time` 对各周期边界日期的计算（周按周一到周日、年按 1/1–12/31、月按 1 日到月末、
  6 个月按当前月往前回溯 5 个月），并保留原始时区信息。

### 3. 重新设计任务列表样式与委托

- `src/fk/qt/workitem_text_delegate.py` 重写：
  - 每行左侧绘制圆形进度环（Apple 风格），完成时显示对勾，未完成时按完成比例填充扇形。
  - 右侧显示元信息（已完成/总数、跨天数）。
  - 完成态工作项标题改为灰色并加删除线；底部绘制分隔线。
- `src/fk/qt/pomodoro_delegate.py` 重写：
  - 弃用原有 SVG 图标渲染，改为自绘圆角方块表示每个番茄钟。
  - 完成的番茄钟按所在日期映射不同颜色，便于直观区分跨天完成情况。
  - 进行中显示十字标记，已作废显示空心方块。
- `src/fk/qt/workitem_tableview.py` / `src/fk/qt/backlog_tableview.py`：
  - 新增自定 `_WorkitemEditDelegate` / `_BacklogEditDelegate`，使内联编辑输入框采用圆角蓝色边框样式，最小高度 32px。
  - Backlog 表格启用交替行底色。

### 4. 新增「重新打开」工作项功能

- `src/fk/core/events.py` 与 `src/fk/core/abstract_event_source.py` 新增
  `BeforeWorkitemReopen` / `AfterWorkitemReopen` 事件。
- `src/fk/core/workitem.py` 新增 `unseal()` 方法，将已封存（sealed）的工作项恢复为 `new` 状态。
- `src/fk/core/workitem_strategies.py` 新增 `ReopenWorkitemStrategy` 策略。
- `src/fk/qt/workitem_tableview.py` 新增右键菜单项「Reopen Item」（`Ctrl+Shift+R`），
  仅对已封存的工作项启用。配套图标 `res/icons/*/24x24/tool-reopen.svg`。

### 5. UI / 样式调整

- `res/core.ui`：左侧工具栏新增 `toolToday` / `toolTasks` / `toolStats` 三个按钮，
  并将 `toolBacklogs` 默认隐藏。
- `res/stats.ui`：将「Prev/Next」按钮调整为 `< Prev` / `Next >`，把默认选中周期从「week」改为「day」。
- `res/style-template.qss` 及各主题 JSON（`style-dark.json` 等）：
  - 新增 `HOVER_BG_COLOR`、`ALTERNATE_ROW_COLOR`、`ITEM_RADIUS`、`TOOLBAR_RADIUS` 等主题变量。
  - 表格行增加 hover 背景与内边距，圆角化工具按钮，搜索框样式调整等。
- 新增工具栏图标资源（`tool-reopen` / `tool-stats` / `tool-tasks` / `tool-today`，分 dark/light/mixed 三套）。

### 6. 移除搜索栏

- 在 `src/fk/desktop/desktop.py` 中移除了原 `SearchBar` 的创建与挂载（标注为 "Search bar removed"），
  `show_search()` 方法被置空。相关 UI 资源保留但不再生效。

### 7. macOS 打包脚本增强

- `scripts/macos/package-nuitka.sh` 重构：
  - 自动检测并选择 Python 3.10+ 解释器（优先 3.12/3.13）。
  - 自动创建虚拟环境并安装 PySide6、Nuitka 等依赖。
  - 自动生成 `flowkeeper.icns` 与 `resources.py`。
  - 使用项目根目录的绝对路径，避免依赖当前工作目录。
  - 默认以未签名方式构建 `.app` 包。

---

## 构建

构建方式与原项目一致，依赖 Qt 6.7.0+ 与 Python 3.9+。详见下方原项目说明；
macOS 下可直接执行 `scripts/macos/package-nuitka.sh` 一键构建。
Windows 下可直接执行 `py -3 -m PyInstaller scripts/common/pyinstaller/portable.spec --distpath=build` 一键构建。

```shell
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
build/common/generate-resources.sh
```

## 运行

```shell
PYTHONPATH=src python -m fk.desktop.desktop
# 或使用新增入口：
PYTHONPATH=src python -m fk.desktop.Flowkeeper
```

## 测试

```shell
PYTHONPATH=src python -m coverage run -m unittest discover -v fk.tests
python -m coverage html
PYTHONPATH=src python -m fk.desktop.desktop --e2e
```

## 技术文档

参见 `doc/` 目录下的原项目设计文档：
- [Design considerations](doc/design.md)
- [Data model](doc/data-model.md)
- [Strategies](doc/strategies.md)
- [Events](doc/events.md)
- [UI actions](doc/actions.md)
- [CI/CD pipeline](doc/pipeline.md)
- [Building for Alpine Linux](doc/build-alpine.md)
- [Building for FreeBSD](doc/build-freebsd.md)

## 致谢

本项目基于 [flowkeeper-org/fk-desktop](https://github.com/flowkeeper-org/fk-desktop)，
感谢原作者 Constantine Kulak 及社区贡献者的工作。

## Copyright

Copyright (c) 2023 - 2024 Constantine Kulak（原项目作者）。
本分支在原 GPL-3.0 许可证下继续发布，所有修改同样遵循 GPLv3。

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
