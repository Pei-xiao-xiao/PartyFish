"""
收益统计与鱼饵管理界面
重构后的版本，使用服务类处理业务逻辑
"""

import csv
from collections import defaultdict
from datetime import datetime, timedelta
from PySide6.QtCore import Qt, Signal, QPointF, QTimer
from PySide6.QtGui import QColor, QBrush, QLinearGradient, QPainter, QCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QHeaderView,
    QTableWidgetItem,
    QStackedWidget,
    QScrollArea,
    QToolTip,
)
from PySide6.QtCharts import QChart, QChartView
from qfluentwidgets import (
    CardWidget,
    BodyLabel,
    StrongBodyLabel,
    TitleLabel,
    ComboBox,
    PushButton,
    PrimaryPushButton,
    LineEdit,
    ProgressBar,
    TableWidget,
    SegmentedWidget,
    TransparentToolButton,
    FluentIcon,
    qconfig,
    isDarkTheme,
)

from src.config import cfg
from src.services.profit_analysis_service import ProfitAnalysisService
from src.services.chart_builder_service import ChartBuilderService, CHART_COLORS


class ChartScrollContainer(QScrollArea):
    """支持滚轮横向滚动和渐变遮罩的图表容器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self._fade_width = 14
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.viewport().setStyleSheet("background: transparent;")
        self.viewport().setAutoFillBackground(False)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta)
        event.accept()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)

        h_bar = self.horizontalScrollBar()
        can_scroll_left = h_bar.value() > h_bar.minimum()
        can_scroll_right = h_bar.value() < h_bar.maximum()

        theme_val = qconfig.theme.value
        is_dark_by_value = (
            str(theme_val.name).upper() == "DARK"
            if hasattr(theme_val, "name")
            else str(theme_val).lower() == "dark"
        )
        is_dark = isDarkTheme() or is_dark_by_value

        # Prefer current viewport palette to match the real background,
        # and guard against bright fallback colors in dark mode.
        base_color = self.viewport().palette().color(self.viewport().backgroundRole())
        if not base_color.isValid():
            base_color = QColor(56, 61, 72) if is_dark else QColor(255, 255, 255)
        if is_dark and base_color.lightness() > 140:
            base_color = QColor(56, 61, 72)
        elif (not is_dark) and base_color.lightness() < 120:
            base_color = QColor(255, 255, 255)

        rect = self.viewport().rect()

        if can_scroll_left:
            left_grad = QLinearGradient(0, 0, self._fade_width, 0)
            left_grad.setColorAt(0, base_color)
            base_transparent = QColor(base_color)
            base_transparent.setAlpha(0)
            left_grad.setColorAt(1, base_transparent)
            painter.fillRect(0, 0, self._fade_width, rect.height(), QBrush(left_grad))

        if can_scroll_right:
            right_grad = QLinearGradient(
                rect.width() - self._fade_width, 0, rect.width(), 0
            )
            base_transparent = QColor(base_color)
            base_transparent.setAlpha(0)
            right_grad.setColorAt(0, base_transparent)
            right_grad.setColorAt(1, base_color)
            painter.fillRect(
                rect.width() - self._fade_width,
                0,
                self._fade_width,
                rect.height(),
                QBrush(right_grad),
            )

        painter.end()


class HoverDeleteTableWidget(TableWidget):
    """带删除按钮的表格控件"""

    delete_row_signal = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

    def add_delete_button(self, row):
        """添加常驻删除按钮"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        btn = TransparentToolButton(FluentIcon.DELETE, self)
        btn.setFixedSize(24, 24)
        btn.setToolTip("删除记录")
        btn.clicked.connect(lambda checked=False, r=row: self.delete_row_signal.emit(r))

        layout.addStretch(1)
        layout.addWidget(btn, 0, Qt.AlignVCenter)
        layout.addStretch(1)
        self.setCellWidget(row, 3, widget)


class ProfitInterface(QWidget):
    """收益统计与鱼饵管理界面"""

    bait_changed_signal = Signal(str)
    test_recognition_signal = Signal()
    data_changed_signal = Signal()
    server_changed_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("profitInterface")

        # 初始化服务
        self.analysis_service = ProfitAnalysisService()
        self.chart_service = ChartBuilderService()

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(30, 30, 30, 30)
        self.vBoxLayout.setSpacing(20)

        # 初始化 UI
        self.init_top_panel()
        self.init_operation_panel()
        self.init_bottom_panel()

        # 数据状态
        self.current_history_view = "line"
        self.line_chart_dates = []
        self.bar_categories_dates = []
        self._editing_blocked = False
        self._pending_reload = False
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.timeout.connect(self._flush_pending_reload)

        # 加载数据
        self.reload_data()

    def init_top_panel(self):
        """初始化顶部面板"""
        top_layout = QHBoxLayout()
        top_layout.setSpacing(20)

        # 鱼饵选择卡片
        bait_card = CardWidget(self)
        bait_layout = QVBoxLayout(bait_card)

        bait_title = BodyLabel("当前使用鱼饵", bait_card)
        self.bait_combo = ComboBox(bait_card)
        self.bait_combo.addItems(list(cfg.BAIT_PRICES.keys()))
        self.bait_combo.setCurrentText(cfg.current_bait)
        self.bait_combo.currentTextChanged.connect(self._on_bait_changed)

        bait_layout.addWidget(bait_title)
        bait_layout.addWidget(self.bait_combo)
        bait_layout.addStretch(1)

        top_layout.addWidget(bait_card, 1)

        # 统计卡片组
        self.sales_card = self._create_stat_card("今日销售额", "0", FluentIcon.CALENDAR)
        self.cost_card = self._create_stat_card("今日鱼饵成本", "0", FluentIcon.TAG)
        self.net_card = self._create_stat_card("今日净收益", "0", FluentIcon.COMPLETED)
        self.limit_card = self._create_stat_card(
            "剩余可卖额度", "900", FluentIcon.PIE_SINGLE
        )

        top_layout.addWidget(self.sales_card, 1)
        top_layout.addWidget(self.cost_card, 1)
        top_layout.addWidget(self.net_card, 1)
        top_layout.addWidget(self.limit_card, 1)

        self.vBoxLayout.addLayout(top_layout)

    def _create_stat_card(self, title, value, icon):
        """创建统计卡片"""
        card = CardWidget(self)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(15, 10, 15, 10)

        icon_label = QLabel()
        icon_label.setPixmap(icon.icon(color=qconfig.themeColor.value).pixmap(28, 28))

        text_layout = QVBoxLayout()
        title_label = BodyLabel(title, card)
        value_label = TitleLabel(value, card)

        text_layout.addWidget(title_label)
        text_layout.addWidget(value_label)
        text_layout.setSpacing(0)

        layout.addWidget(icon_label)
        layout.addLayout(text_layout)
        layout.addStretch(1)

        card.value_label = value_label
        return card

    def init_operation_panel(self):
        """初始化手动操作与进度区域"""
        op_container = CardWidget(self)
        op_layout = QVBoxLayout(op_container)
        op_layout.setContentsMargins(20, 20, 20, 20)
        op_layout.setSpacing(15)

        # 进度条
        progress_layout = QHBoxLayout()

        # 区服选择
        self.server_combo = ComboBox(op_container)
        self.server_combo.addItems(["国服 (00:00 重置)", "亚服 (12:00 重置)"])
        current_region = cfg.global_settings.get("server_region", "CN")
        if current_region == "Global":
            self.server_combo.setCurrentIndex(1)
        else:
            self.server_combo.setCurrentIndex(0)

        self.server_combo.currentTextChanged.connect(self._on_server_changed)
        self.server_combo.setFixedWidth(160)

        self.progress_label = StrongBodyLabel("今日进度: 0/899", op_container)
        self.progress_bar = ProgressBar(op_container)
        self.progress_bar.setRange(0, 899)
        self.progress_bar.setValue(0)

        progress_layout.addWidget(self.server_combo)
        progress_layout.addSpacing(10)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        op_layout.addLayout(progress_layout)

        # 手动记录输入框
        input_layout = QHBoxLayout()
        self.amount_input = LineEdit(op_container)
        self.amount_input.setPlaceholderText("输入卖出鱼干")
        self.amount_input.setClearButtonEnabled(True)
        self.amount_input.returnPressed.connect(self._on_manual_add)

        self.add_btn = PrimaryPushButton("出售", op_container)
        self.add_btn.setIcon(FluentIcon.ADD)
        self.add_btn.clicked.connect(self._on_manual_add)

        input_layout.addWidget(self.amount_input)
        input_layout.addWidget(self.add_btn)
        op_layout.addLayout(input_layout)

        self.vBoxLayout.addWidget(op_container)

    def init_bottom_panel(self):
        """初始化底部左右分栏"""
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(20)

        # 左侧：今日记录
        today_container = CardWidget(self)
        today_layout = QVBoxLayout(today_container)
        today_layout.setContentsMargins(20, 15, 20, 20)

        today_title = StrongBodyLabel("今日卖鱼记录", today_container)
        today_layout.addWidget(today_title)

        self.table = HoverDeleteTableWidget(today_container)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["时间", "鱼干", "鱼饵", "操作"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 80)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 40)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.delete_row_signal.connect(self._on_delete_row)
        self.table.cellChanged.connect(self._on_cell_edited)

        today_layout.addWidget(self.table)
        bottom_layout.addWidget(today_container, 1)

        # 右侧：历史分析
        history_container = CardWidget(self)
        hist_layout = QVBoxLayout(history_container)
        hist_layout.setContentsMargins(20, 15, 20, 20)

        # Header
        hist_header = QHBoxLayout()
        hist_header.addWidget(StrongBodyLabel("历史记录 (30天)", history_container))
        hist_header.addStretch(1)

        self.view_switcher = SegmentedWidget(self)
        self.view_switcher.addItem("list", "列表")
        self.view_switcher.addItem("line", "趋势")
        self.view_switcher.addItem("bar", "柱状")
        self.view_switcher.setCurrentItem("line")
        self.view_switcher.currentItemChanged.connect(self._on_history_view_changed)
        hist_header.addWidget(self.view_switcher)
        hist_layout.addLayout(hist_header)

        # Stats
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(8)
        self.hist_total_card = self._create_mini_stat(
            "总收益", "0", CHART_COLORS["sales"]
        )
        self.hist_avg_card = self._create_mini_stat(
            "平均收益", "0", CHART_COLORS["accent"]
        )
        self.hist_max_card = self._create_mini_stat(
            "最高收益", "0", CHART_COLORS["sales"]
        )
        self.hist_net_card = self._create_mini_stat(
            "总净收益", "0", CHART_COLORS["net"]
        )

        stats_layout.addWidget(self.hist_total_card)
        stats_layout.addWidget(self.hist_avg_card)
        stats_layout.addWidget(self.hist_max_card)
        stats_layout.addWidget(self.hist_net_card)
        hist_layout.addLayout(stats_layout)

        # Content Stack
        self.history_stack = QStackedWidget(self)

        # 列表视图
        self.history_table = TableWidget(self)
        self.history_table.setColumnCount(3)
        self.history_table.setHorizontalHeaderLabels(["日期", "总收益", "净收益"])
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setBorderVisible(True)
        self.history_table.setBorderRadius(8)
        self.history_stack.addWidget(self.history_table)

        # 趋势图
        self.line_chart = QChart()
        self.line_chart.legend().setVisible(True)
        self.line_chart.legend().setAlignment(Qt.AlignBottom)
        self.line_chart_view = QChartView(self.line_chart)
        self.line_chart_view.setStyleSheet("background: transparent; border: none;")
        self.line_chart_view.setRenderHint(QPainter.Antialiasing)

        self.line_scroll = ChartScrollContainer()
        self.line_scroll.setWidget(self.line_chart_view)
        self.history_stack.addWidget(self.line_scroll)

        # 柱状图
        self.bar_chart = QChart()
        self.bar_chart.legend().setVisible(True)
        self.bar_chart.legend().setAlignment(Qt.AlignBottom)
        self.bar_chart_view = QChartView(self.bar_chart)
        self.bar_chart_view.setStyleSheet("background: transparent; border: none;")
        self.bar_chart_view.setRenderHint(QPainter.Antialiasing)

        self.bar_scroll = ChartScrollContainer()
        self.bar_scroll.setWidget(self.bar_chart_view)
        self.history_stack.addWidget(self.bar_scroll)

        self.history_stack.setCurrentIndex(1)

        hist_layout.addWidget(self.history_stack)
        bottom_layout.addWidget(history_container, 1)

        self.vBoxLayout.addLayout(bottom_layout, 2)

    def _create_mini_stat(self, title, value, color=None):
        """创建迷你统计块"""
        text_color = color if color else CHART_COLORS["sales"]

        widget = QFrame()
        if isDarkTheme():
            widget.setStyleSheet(
                ".QFrame {background-color: rgba(60, 60, 65, 180); border-radius: 8px;}"
            )
        else:
            widget.setStyleSheet(
                ".QFrame {background-color: rgba(250, 248, 245, 220); border-radius: 8px;}"
            )

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        title_lbl = BodyLabel(title, widget)
        title_lbl.setStyleSheet("color: gray; font-size: 11px;")
        val_lbl = StrongBodyLabel(value, widget)
        val_lbl.setStyleSheet(f"font-size: 15px; color: {text_color};")

        layout.addWidget(title_lbl, 0, Qt.AlignCenter)
        layout.addWidget(val_lbl, 0, Qt.AlignCenter)

        widget.val_label = val_lbl
        return widget

    def _apply_theme_styles(self):
        """Apply theme-aware styles for mini stat cards and chart views."""
        is_dark = isDarkTheme()
        mini_card_bg = (
            "rgba(60, 60, 65, 180)" if is_dark else "rgba(250, 248, 245, 220)"
        )
        mini_title_color = "#a3a3a3" if is_dark else "gray"

        for widget in [
            getattr(self, "hist_total_card", None),
            getattr(self, "hist_avg_card", None),
            getattr(self, "hist_max_card", None),
            getattr(self, "hist_net_card", None),
        ]:
            if not widget:
                continue
            widget.setStyleSheet(
                f".QFrame {{background-color: {mini_card_bg}; border-radius: 8px;}}"
            )
            for child in widget.findChildren(BodyLabel):
                child.setStyleSheet(f"color: {mini_title_color}; font-size: 11px;")

        # Keep chart views transparent to avoid bright borders after theme switch.
        if hasattr(self, "line_chart_view"):
            self.line_chart_view.setStyleSheet("background: transparent; border: none;")
        if hasattr(self, "bar_chart_view"):
            self.bar_chart_view.setStyleSheet("background: transparent; border: none;")

    def refresh_theme(self):
        """Public API for theme switch refresh."""
        self.reload_data()

    def request_reload(self, delay_ms: int = 250):
        """
        Request a deferred data reload.
        When interface is hidden, mark dirty and reload on next show.
        """
        self._pending_reload = True
        if not self.isVisible():
            self._reload_timer.stop()
            return
        if not self._reload_timer.isActive():
            self._reload_timer.start(max(0, delay_ms))

    def _flush_pending_reload(self):
        if not self._pending_reload or not self.isVisible():
            return
        self.reload_data()

    def showEvent(self, event):
        super().showEvent(event)
        if self._pending_reload and not self._reload_timer.isActive():
            self._reload_timer.start(10)

    def reload_data(self):
        """重新加载数据并刷新界面"""
        self._pending_reload = False
        self._apply_theme_styles()
        # 使用服务加载数据
        start_time = self.analysis_service.get_current_cycle_start_time()
        today_stats = self.analysis_service.load_today_stats(start_time)
        history_stats = self.analysis_service.load_history_stats(days=30)

        # 更新今日统计 UI
        self.sales_card.value_label.setText(str(today_stats.total_sales))
        self.cost_card.value_label.setText(str(today_stats.total_cost))
        self.net_card.value_label.setText(str(today_stats.net_profit))

        remaining_display = today_stats.remaining_limit
        self.limit_card.value_label.setText(str(remaining_display))
        if remaining_display < 0:
            self.limit_card.value_label.setStyleSheet("color: #d32f2f;")
        else:
            self.limit_card.value_label.setStyleSheet("")

        # 更新进度条
        capped_sales = min(today_stats.total_sales, 899)
        self.progress_bar.setValue(capped_sales)
        self.progress_label.setText(f"今日进度: {capped_sales}/899")

        # 更新今日记录表格
        self._editing_blocked = True
        self.table.setRowCount(0)
        for row in reversed(today_stats.sales_records):
            r = self.table.rowCount()
            self.table.insertRow(r)

            time_item = QTableWidgetItem(row[0])
            time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
            time_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 0, time_item)

            amount_item = QTableWidgetItem(row[1])
            amount_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 1, amount_item)

            bait_item = QTableWidgetItem(row[2])
            bait_item.setFlags(bait_item.flags() & ~Qt.ItemIsEditable)
            bait_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 2, bait_item)

            self.table.add_delete_button(r)

        self._editing_blocked = False

        # 更新历史统计 UI
        self.hist_total_card.val_label.setText(str(history_stats.total_income))
        self.hist_avg_card.val_label.setText(str(history_stats.avg_income))
        self.hist_max_card.val_label.setText(str(history_stats.max_income))
        self.hist_net_card.val_label.setText(str(history_stats.total_net))

        # 更新历史表格
        sorted_dates = sorted(history_stats.daily_sales.keys(), reverse=True)
        self.history_table.setRowCount(0)
        for date_str in sorted_dates:
            sales = history_stats.daily_sales[date_str]
            cost = history_stats.daily_cost.get(date_str, 0)
            net = sales - cost

            r = self.history_table.rowCount()
            self.history_table.insertRow(r)
            date_item = QTableWidgetItem(date_str)
            date_item.setTextAlignment(Qt.AlignCenter)
            self.history_table.setItem(r, 0, date_item)

            sales_item = QTableWidgetItem(str(sales))
            sales_item.setTextAlignment(Qt.AlignCenter)
            self.history_table.setItem(r, 1, sales_item)

            net_item = QTableWidgetItem(str(net))
            net_item.setTextAlignment(Qt.AlignCenter)
            if net > 0:
                net_item.setForeground(QColor("#388e3c"))
            elif net < 0:
                net_item.setForeground(QColor("#d32f2f"))

            self.history_table.setItem(r, 2, net_item)

        # 更新图表
        if self.current_history_view == "line":
            self._update_line_chart(history_stats)
        elif self.current_history_view == "bar":
            self._update_bar_chart(history_stats)

        # 通知其他组件
        self.data_changed_signal.emit()

    def _update_line_chart(self, history_stats):
        """更新趋势图"""
        self.line_chart_dates = self.chart_service.build_line_chart(
            self.line_chart,
            history_stats.daily_sales,
            history_stats.daily_cost,
            self.line_chart_view,
            self.line_scroll,
        )

        # 连接悬停事件
        for series in self.line_chart.series():
            if hasattr(series, "hovered"):
                series.blockSignals(True)
                series.hovered.connect(
                    lambda point, state, s=series: self._on_line_hover(
                        point, state, s.name(), history_stats
                    )
                )
                series.blockSignals(False)

    def _update_bar_chart(self, history_stats):
        """更新柱状图"""
        self.bar_categories_dates = self.chart_service.build_bar_chart(
            self.bar_chart,
            history_stats.daily_sales,
            history_stats.daily_cost,
            self.bar_chart_view,
            self.bar_scroll,
        )

        # 连接悬停事件
        for series in self.bar_chart.series():
            if hasattr(series, "hovered"):
                for bar_set in series.barSets():
                    bar_set.blockSignals(True)
                    bar_set.hovered.connect(
                        lambda status, index, hs=history_stats: self._on_bar_hover(
                            status, index, hs
                        )
                    )
                    bar_set.blockSignals(False)

    def _on_history_view_changed(self, route_key):
        """历史视图切换"""
        self.current_history_view = route_key
        if route_key == "list":
            self.history_stack.setCurrentIndex(0)
        elif route_key == "line":
            self.history_stack.setCurrentIndex(1)
            start_time = self.analysis_service.get_current_cycle_start_time()
            history_stats = self.analysis_service.load_history_stats(days=30)
            self._update_line_chart(history_stats)
        elif route_key == "bar":
            self.history_stack.setCurrentIndex(2)
            start_time = self.analysis_service.get_current_cycle_start_time()
            history_stats = self.analysis_service.load_history_stats(days=30)
            self._update_bar_chart(history_stats)

    def _on_manual_add(self):
        """手动添加记录"""
        text = self.amount_input.text()
        if not text.isdigit():
            return

        amount = int(text)
        if self.analysis_service.write_sale_record(amount, cfg.current_bait):
            self.reload_data()
            self.amount_input.clear()

    def _on_delete_row(self, row):
        """删除记录"""
        item = self.table.item(row, 0)
        if not item:
            return
        target_ts = item.text()

        if self.analysis_service.delete_sale_record(target_ts):
            self.reload_data()

    def _on_cell_edited(self, row, column):
        """编辑单元格"""
        if column != 1 or self._editing_blocked:
            return

        ts_item = self.table.item(row, 0)
        amount_item = self.table.item(row, 1)
        if not ts_item or not amount_item:
            return

        target_ts = ts_item.text()
        new_amount = amount_item.text().strip()

        if self.analysis_service.update_sale_record(target_ts, new_amount):
            self.reload_data()
        else:
            self.reload_data()

    def _on_bait_changed(self, text):
        """鱼饵变更"""
        cfg.current_bait = text
        cfg.save()
        self.bait_changed_signal.emit(text)

    def _on_server_changed(self, text):
        """区服变更"""
        new_region = "Global" if "亚服" in text else "CN"
        if cfg.global_settings.get("server_region") != new_region:
            cfg.global_settings["server_region"] = new_region
            cfg.save()
            self.reload_data()
            self.server_changed_signal.emit(new_region)

    def add_sale_record(self, amount):
        """添加销售记录（由 worker 调用）"""
        self.request_reload(delay_ms=0)

    def update_current_bait_display(self, bait_name):
        """更新当前鱼饵显示"""
        self.bait_combo.setCurrentText(bait_name)

    def _on_line_hover(self, point, state, name, history_stats):
        """趋势图悬停提示"""
        if state:
            idx = int(round(point.x()))
            if idx < 0 or idx >= len(self.line_chart_dates):
                return

            date_str = self.line_chart_dates[idx]
            sales = history_stats.daily_sales.get(date_str, 0)
            cost = history_stats.daily_cost.get(date_str, 0)
            net = sales - cost

            tooltip_text = (
                f"日期: {date_str}\n"
                f"总收益: {sales}\n"
                f"消耗成本: {cost}\n"
                f"净收益: {net}"
            )

            QToolTip.showText(QCursor.pos(), tooltip_text)
        else:
            QToolTip.hideText()

    def _on_bar_hover(self, status, index, history_stats):
        """柱状图悬停提示"""
        if status:
            if index < 0 or index >= len(self.bar_categories_dates):
                return

            date_str = self.bar_categories_dates[index]
            sales = history_stats.daily_sales.get(date_str, 0)
            cost = history_stats.daily_cost.get(date_str, 0)
            net = sales - cost

            tooltip_text = (
                f"日期: {date_str}\n"
                f"总收益: {sales}\n"
                f"消耗成本: {cost}\n"
                f"净收益: {net}"
            )

            QToolTip.showText(QCursor.pos(), tooltip_text)
        else:
            QToolTip.hideText()
