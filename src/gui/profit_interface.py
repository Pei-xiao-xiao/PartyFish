from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QHeaderView, QTableWidgetItem, QLabel, QFrame, QStackedWidget, QToolTip, QScrollArea
from PySide6.QtCore import Qt, Signal, QDateTime
from PySide6.QtGui import QPainter, QColor, QCursor, QLinearGradient, QBrush, QPen, QWheelEvent
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QSplineSeries, QScatterSeries, QBarSeries, QBarSet, QBarCategoryAxis, QDateTimeAxis, QValueAxis
from qfluentwidgets import (CardWidget, TitleLabel, BodyLabel, ComboBox, TableWidget,
                            FluentIcon, InfoBadge, qconfig, PushButton, PrimaryPushButton,
                            LineEdit, ProgressBar, StrongBodyLabel, SegmentedWidget, TransparentToolButton)
from datetime import datetime, timedelta
import csv
import os
from collections import defaultdict
from src.config import cfg

# 温暖治愈系配色常量 - 使用更深更饱和的颜色使数据点更明显
CHART_COLORS = {
    'sales': '#3BA5D8',      # 深天蓝色
    'cost': '#E86B8A',       # 深粉红色/玫瑰红  
    'net': '#5DB584',        # 深薄荷绿
    'accent': '#F5A623',     # 深琥珀橙
}


class ChartScrollContainer(QScrollArea):
    """
    自定义图表滚动容器
    - 滚轮垂直滚动映射为横向滚动
    - 隐藏滚动条保持美观
    - 边缘渐变遮罩效果
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        # 隐藏滚动条但保留滚动功能
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 渐变遮罩宽度
        self._fade_width = 30
        
    def wheelEvent(self, event: QWheelEvent):
        """将垂直滚轮映射为横向滚动"""
        delta = event.angleDelta().y()
        h_bar = self.horizontalScrollBar()
        # 滚动速度，负号使滚轮方向更自然
        h_bar.setValue(h_bar.value() - delta)
        event.accept()
        
    def paintEvent(self, event):
        """绘制边缘渐变遮罩"""
        super().paintEvent(event)
        
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        
        h_bar = self.horizontalScrollBar()
        can_scroll_left = h_bar.value() > h_bar.minimum()
        can_scroll_right = h_bar.value() < h_bar.maximum()
        
        # 根据主题选择遮罩颜色
        is_dark = qconfig.theme.value == "Dark"
        base_color = QColor(35, 35, 35) if is_dark else QColor(255, 255, 255)
        
        rect = self.viewport().rect()
        
        # 左侧渐变遮罩
        if can_scroll_left:
            left_grad = QLinearGradient(0, 0, self._fade_width, 0)
            left_grad.setColorAt(0, base_color)
            base_transparent = QColor(base_color)
            base_transparent.setAlpha(0)
            left_grad.setColorAt(1, base_transparent)
            painter.fillRect(0, 0, self._fade_width, rect.height(), QBrush(left_grad))
        
        # 右侧渐变遮罩
        if can_scroll_right:
            right_grad = QLinearGradient(rect.width() - self._fade_width, 0, rect.width(), 0)
            base_transparent = QColor(base_color)
            base_transparent.setAlpha(0)
            right_grad.setColorAt(0, base_transparent)
            right_grad.setColorAt(1, base_color)
            painter.fillRect(rect.width() - self._fade_width, 0, self._fade_width, rect.height(), QBrush(right_grad))
        
        painter.end()


class HoverDeleteTableWidget(TableWidget):
    """
    带删除按钮的表格控件
    """
    delete_row_signal = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def add_delete_button(self, row):
        """添加常驻删除按钮"""
        # 使用容器来实现居中，同时处理水平和垂直居中
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        btn = TransparentToolButton(FluentIcon.DELETE, self)
        btn.setFixedSize(24, 24)
        btn.setToolTip("删除记录")
        btn.clicked.connect(lambda checked=False, r=row: self.delete_row_signal.emit(r))
        
        # 使用 addStretch 实现水平居中
        layout.addStretch(1)
        layout.addWidget(btn, 0, Qt.AlignVCenter)
        layout.addStretch(1)
        self.setCellWidget(row, 3, widget)

class ProfitInterface(QWidget):
    """
    收益统计与鱼饵管理界面
    """
    bait_changed_signal = Signal(str)
    test_recognition_signal = Signal()
    data_changed_signal = Signal() # Signal for data updates (add/delete)
    server_changed_signal = Signal(str) # New signal for server change

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('profitInterface')
        
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(30, 30, 30, 30)
        self.vBoxLayout.setSpacing(20)

        # 1. 顶部：鱼饵选择与今日概览
        self.init_top_panel()
        
        # 2. 中部：操作与进度
        self.init_operation_panel()
        
        # 3. 底部：左右分栏 (今日记录 | 历史分析)
        self.init_bottom_panel()

        # Load data
        self.today_sales_records = []
        self.today_fish_records = []
        self.history_daily_sales = {} # {date_str: total_sales}
        self.history_daily_cost = {}  # {date_str: total_cost}
        self.current_history_view = "line" # Default view
        self.reload_data()

    def init_top_panel(self):
        """初始化顶部面板"""
        top_layout = QHBoxLayout()
        top_layout.setSpacing(20)

        # 左侧：鱼饵选择卡片
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

        # 右侧：统计卡片组
        self.sales_card = self._create_stat_card("今日销售额", "0", FluentIcon.CALENDAR)
        self.cost_card = self._create_stat_card("今日鱼饵成本", "0", FluentIcon.TAG)
        self.net_card = self._create_stat_card("今日净收益", "0", FluentIcon.COMPLETED)
        self.limit_card = self._create_stat_card("剩余可卖额度", "900", FluentIcon.PIE_SINGLE)

        top_layout.addWidget(self.sales_card, 1)
        top_layout.addWidget(self.cost_card, 1)
        top_layout.addWidget(self.net_card, 1)
        top_layout.addWidget(self.limit_card, 1)

        self.vBoxLayout.addLayout(top_layout)

    def _create_stat_card(self, title, value, icon):
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
        
        # 1. 进度条
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
        
        # 2. 手动记录输入框
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
        
        # --- 左侧：今日记录 ---
        today_container = CardWidget(self)
        today_layout = QVBoxLayout(today_container)
        today_layout.setContentsMargins(20, 15, 20, 20)
        
        today_title = StrongBodyLabel("今日卖鱼记录", today_container)
        today_layout.addWidget(today_title)

        self.table = HoverDeleteTableWidget(today_container)
        self.table.setColumnCount(4)  # 添加一列用于删除按钮
        self.table.setHorizontalHeaderLabels(['时间', '鱼干', '鱼饵', '操作'])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 时间（自适应内容）
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)           # 数量（占用剩余空间）
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 鱼饵（根据内容自适应）
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)             # 删除按钮
        self.table.setColumnWidth(3, 40)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.delete_row_signal.connect(self._on_delete_row)  # 连接删除信号
        self.table.cellChanged.connect(self._on_cell_edited)  # 连接编辑信号
        self._editing_blocked = False  # 标志位，防止 reload 时触发 cellChanged
        
        today_layout.addWidget(self.table)
        bottom_layout.addWidget(today_container, 1) # Flex 1
        
        # --- 右侧：历史分析 ---
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
        self.view_switcher.setCurrentItem("line") # Default to chart
        self.view_switcher.currentItemChanged.connect(self._on_history_view_changed)
        hist_header.addWidget(self.view_switcher)
        hist_layout.addLayout(hist_header)
        
        # Stats - 添加4个统计卡片（包含总净收益）
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(8)
        self.hist_total_card = self._create_mini_stat("总收益", "0", CHART_COLORS['sales'])
        self.hist_avg_card = self._create_mini_stat("平均收益", "0", CHART_COLORS['accent'])
        self.hist_max_card = self._create_mini_stat("最高收益", "0", CHART_COLORS['sales'])
        self.hist_net_card = self._create_mini_stat("总净收益", "0", CHART_COLORS['net'])
        
        stats_layout.addWidget(self.hist_total_card)
        stats_layout.addWidget(self.hist_avg_card)
        stats_layout.addWidget(self.hist_max_card)
        stats_layout.addWidget(self.hist_net_card)
        hist_layout.addLayout(stats_layout)
        
        # Content Stack
        self.history_stack = QStackedWidget(self)
        
        # 0. List
        self.history_table = TableWidget(self)
        self.history_table.setColumnCount(3)
        self.history_table.setHorizontalHeaderLabels(['日期', '总收益', '净收益'])
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setBorderVisible(True)
        self.history_table.setBorderRadius(8)
        self.history_stack.addWidget(self.history_table)
        
        # 1. Line Chart
        self.line_chart = QChart()
        self.line_chart.legend().setVisible(True)
        self.line_chart.legend().setAlignment(Qt.AlignBottom)
        self.line_chart_view = QChartView(self.line_chart)
        self.line_chart_view.setRenderHint(QPainter.Antialiasing)
        
        # 使用自定义滚动容器（支持滚轮横向滚动、渐变遮罩）
        self.line_scroll = ChartScrollContainer()
        self.line_scroll.setWidget(self.line_chart_view)
        self.history_stack.addWidget(self.line_scroll)

        # 2. Bar Chart
        self.bar_chart = QChart()
        self.bar_chart.legend().setVisible(True)
        self.bar_chart.legend().setAlignment(Qt.AlignBottom)
        self.bar_chart_view = QChartView(self.bar_chart)
        self.bar_chart_view.setRenderHint(QPainter.Antialiasing)
        
        # 使用自定义滚动容器
        self.bar_scroll = ChartScrollContainer()
        self.bar_scroll.setWidget(self.bar_chart_view)
        self.history_stack.addWidget(self.bar_scroll)
        
        # Set default view
        self.history_stack.setCurrentIndex(1)
        
        hist_layout.addWidget(self.history_stack)
        bottom_layout.addWidget(history_container, 1) # Flex 1
        
        self.vBoxLayout.addLayout(bottom_layout, 2) # Give more vertical space to bottom

    def _create_mini_stat(self, title, value, color=None):
        """创建迷你统计块"""
        # 使用传入的颜色或默认的温暖系配色
        text_color = color if color else CHART_COLORS['sales']
        
        widget = QFrame()
        # 统一使用温暖米色背景，与图表背景风格一致
        if qconfig.theme.value == "Dark":
            widget.setStyleSheet(".QFrame {background-color: rgba(60, 60, 65, 180); border-radius: 8px;}")
        else:
            widget.setStyleSheet(".QFrame {background-color: rgba(250, 248, 245, 220); border-radius: 8px;}")
             
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        
        title_lbl = BodyLabel(title, widget)
        title_lbl.setStyleSheet("color: gray; font-size: 11px;")
        val_lbl = StrongBodyLabel(value, widget)
        val_lbl.setStyleSheet(f"font-size: 15px; color: {text_color};")
        
        layout.addWidget(title_lbl, 0, Qt.AlignCenter)
        layout.addWidget(val_lbl, 0, Qt.AlignCenter)
        
        # Hack to access label later
        widget.val_label = val_lbl
        return widget

    def _on_history_view_changed(self, route_key):
        self.current_history_view = route_key
        if route_key == "list":
            self.history_stack.setCurrentIndex(0)
        elif route_key == "line":
            self.history_stack.setCurrentIndex(1)
            self._update_line_chart()
        elif route_key == "bar":
            self.history_stack.setCurrentIndex(2)
            self._update_bar_chart()

    def _on_manual_add(self):
        """Handle manual record addition"""
        text = self.amount_input.text()
        if not text.isdigit():
            # TODO: Show error
            return
        
        amount = int(text)
        # Manually write to CSV safely
        if self._write_sale_to_csv(amount):
            self.reload_data()  # reload_data 会自动 emit data_changed_signal
            self.amount_input.clear()

    def _on_delete_row(self, row):
        """删除指定行的记录"""
        # 获取该行的时间戳
        item = self.table.item(row, 0)
        if not item:
            return
        target_ts = item.text()
        
        # 读取所有记录，过滤掉要删除的，重新写入
        sales_path = cfg.sales_file
        if not sales_path.exists():
            return
        
        new_lines = []
        with open(sales_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header:
                new_lines.append(header)
            for csv_row in reader:
                if csv_row and csv_row[0] == target_ts:
                    continue  # 跳过要删除的记录
                new_lines.append(csv_row)
        
        with open(sales_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(new_lines)
            
        self.reload_data()  # reload_data 会自动 emit data_changed_signal

    def _on_cell_edited(self, row, column):
        """处理单元格编辑完成事件，保存修改到 CSV"""
        # 只处理鱼干列（第 1 列）的编辑
        if column != 1 or self._editing_blocked:
            return
            
        # 获取该行的时间戳和新值
        ts_item = self.table.item(row, 0)
        amount_item = self.table.item(row, 1)
        if not ts_item or not amount_item:
            return
            
        target_ts = ts_item.text()
        new_amount = amount_item.text().strip()
        
        # 验证新值是否为有效数字
        if not new_amount.isdigit():
            # 如果输入无效，恢复原值
            self.reload_data()
            return
            
        # 读取 CSV，修改对应记录，重新写入
        sales_path = cfg.sales_file
        if not sales_path.exists():
            return
        
        new_lines = []
        with open(sales_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header:
                new_lines.append(header)
            for csv_row in reader:
                if csv_row and csv_row[0] == target_ts:
                    # 修改该行的金额
                    csv_row[1] = new_amount
                new_lines.append(csv_row)
        
        with open(sales_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(new_lines)
            
        self.reload_data()  # reload_data 会自动 emit data_changed_signal

    def _on_bait_changed(self, text):
        cfg.current_bait = text
        cfg.save()
        self.bait_changed_signal.emit(text)

    def _on_server_changed(self, text):
        new_region = "Global" if "亚服" in text else "CN"
        if cfg.global_settings.get("server_region") != new_region:
            cfg.global_settings["server_region"] = new_region
            cfg.save()
            self.reload_data()
            self.data_changed_signal.emit() # Notify others (overlay)
            self.server_changed_signal.emit(new_region)

    def _get_current_cycle_start_time(self):
        """
        计算当前统计周期的起始时间
        CN: 当日 00:00
        Global: 当日 12:00 (若当前 >= 12:00) 或 昨日 12:00 (若当前 < 12:00)
        """
        region = cfg.global_settings.get("server_region", "CN")
        now = datetime.now()
        
        if region == "CN":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # Global / 亚服
            noon_today = now.replace(hour=12, minute=0, second=0, microsecond=0)
            if now >= noon_today:
                return noon_today
            else:
                return noon_today - timedelta(days=1)


    def reload_data(self):
        """重新加载数据并刷新界面"""
        # today_str = datetime.now().strftime("%Y-%m-%d") # DEPRECATED
        start_time = self._get_current_cycle_start_time()
        
        # 1. Load Sales Records and determine cutoff time
        self.today_sales_records = []
        sales_path = cfg.sales_file
        total_sales = 0
        limit_reached_time = None
        
        if sales_path.exists():
            try:
                with open(sales_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader, None) # Skip header
                    # Read all rows first to sort by time if needed, assuming sorted
                    rows = list(reader)
                    
                    current_sum = 0
                    for row in rows:
                        if not row: continue
                        # Row: Timestamp,Amount,BaitUsed
                        ts_str = row[0]
                        try:
                            # 兼容性处理：防止毫秒或其他格式差异
                            # 预期格式: "%Y-%m-%d %H:%M:%S"
                            row_dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                            
                            if row_dt >= start_time:
                                amount = int(row[1])
                                self.today_sales_records.append(row)
                                total_sales += amount
                                current_sum += amount
                                
                                # Check if this sale pushed us over/to the limit
                                if current_sum >= 900 and limit_reached_time is None:
                                    limit_reached_time = row_dt
                                    
                        except ValueError:
                            continue

            except Exception as e:
                print(f"Error loading sales records: {e}")

        # 2. Process History Data (Daily Aggregation)
        self.history_daily_sales = defaultdict(int)
        self.history_daily_cost = defaultdict(int)
        cutoff_date = datetime.now() - timedelta(days=30)
        
        # Load Sales History
        if sales_path.exists():
             try:
                with open(sales_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if not row: continue
                        ts_str = row[0]
                        amount = int(row[1])
                        try:
                            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                            if dt >= cutoff_date:
                                date_str = dt.strftime("%Y-%m-%d")
                                self.history_daily_sales[date_str] += amount
                        except ValueError:
                            pass
             except Exception:
                 pass

        # Load Cost History
        records_path = cfg.records_file
        if records_path.exists():
            try:
                with open(records_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    bait_cost_idx = header.index("BaitCost") if header and "BaitCost" in header else -1
                    
                    if bait_cost_idx != -1:
                        # We need to know the "limit reached time" for EACH day to exclude cost
                        # This is expensive. For history, maybe we simplify?
                        # Or we iterate days?
                        # Let's simplify: Just sum all costs for now.
                        # To do it correctly, we'd need to replay the daily limit logic for every past day.
                        # Given the complexity, let's assume all recorded cost is valid cost for history chart for now,
                        # OR implement the daily check.
                        # Implementing daily check:
                        # We need daily sales records to find the cutoff time for each day.
                        # We already have self.history_daily_sales but that's just totals.
                        # Let's read sales again or store them better?
                        # Actually, let's just sum all costs. The "limit exclusion" logic is a refinement for TODAY's net income.
                        # For history trends, using raw cost is acceptable, or we can improve later.
                        for row in reader:
                            if not row: continue
                            ts_str = row[0]
                            try:
                                dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                                if dt >= cutoff_date:
                                    date_str = dt.strftime("%Y-%m-%d")
                                    if len(row) > bait_cost_idx:
                                        self.history_daily_cost[date_str] += int(row[bait_cost_idx])
                            except ValueError:
                                pass
            except Exception:
                pass

        # Update History UI
        sorted_dates = sorted(self.history_daily_sales.keys(), reverse=True)
        total_hist_income = sum(self.history_daily_sales.values())
        total_hist_cost = sum(self.history_daily_cost.values())
        total_hist_net = total_hist_income - total_hist_cost
        days_count = len(self.history_daily_sales)
        avg_income = total_hist_income // days_count if days_count > 0 else 0
        max_income = max(self.history_daily_sales.values()) if days_count > 0 else 0
        
        self.hist_total_card.val_label.setText(str(total_hist_income))
        self.hist_avg_card.val_label.setText(str(avg_income))
        self.hist_max_card.val_label.setText(str(max_income))
        self.hist_net_card.val_label.setText(str(total_hist_net))
        
        # Populate History Table
        self.history_table.setRowCount(0)
        for date_str in sorted_dates:
            sales = self.history_daily_sales[date_str]
            cost = self.history_daily_cost[date_str]
            net = sales - cost
            
            r = self.history_table.rowCount()
            self.history_table.insertRow(r)
            self.history_table.setItem(r, 0, QTableWidgetItem(date_str))
            self.history_table.setItem(r, 1, QTableWidgetItem(str(sales)))
            
            net_item = QTableWidgetItem(str(net))
            if net > 0:
                net_item.setForeground(QColor("#388e3c")) # Green
            elif net < 0:
                net_item.setForeground(QColor("#d32f2f")) # Red
                
            self.history_table.setItem(r, 2, net_item)
            
        # Update Chart if visible
        if self.current_history_view == "line":
            self._update_line_chart()
        elif self.current_history_view == "bar":
            self._update_bar_chart()

        # 3. Load Fish Records (for Cost)
        # 成本计算逻辑：仅计算 limit_reached_time 之前的鱼饵消耗
        total_cost = 0
        records_path = cfg.records_file
        
        if records_path.exists():
            try:
                with open(records_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    header = next(reader, None) # Timestamp,Name,Quality,Weight,IsNewRecord,Bait,BaitCost
                    
                    bait_cost_idx = -1
                    if header and "BaitCost" in header:
                        bait_cost_idx = header.index("BaitCost")
                    

                    for row in reader:
                        if not row: continue
                        ts_str = row[0]
                        try:
                            row_dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                            if row_dt >= start_time:
                                if bait_cost_idx != -1 and len(row) > bait_cost_idx:
                                    try:
                                        cost = int(row[bait_cost_idx])
                                        total_cost += cost
                                    except ValueError:
                                        pass
                                else:
                                    pass
                        except ValueError:
                            pass
            except Exception as e:
                print(f"Error loading fish records: {e}")

        # 3. Update UI
        self.sales_card.value_label.setText(str(total_sales))
        self.cost_card.value_label.setText(str(total_cost))
        self.net_card.value_label.setText(str(total_sales - total_cost))
        
        remaining = max(0, 900 - total_sales)
        # Check if we broke the limit (last sale pushed us over)
        # Logic: if total > 900, remaining is 0. 
        # But maybe we want to show negative? The requirement says "remaining amount".
        # Let's stick to 0 or negative.
        remaining_display = 900 - total_sales
        self.limit_card.value_label.setText(str(remaining_display))
        if remaining_display < 0:
             self.limit_card.value_label.setStyleSheet("color: #d32f2f;") # Red for overflow
        else:
             self.limit_card.value_label.setStyleSheet("")

        # Update Progress Bar
        capped_sales = min(total_sales, 899)
        self.progress_bar.setValue(capped_sales)
        self.progress_label.setText(f"今日进度: {capped_sales}/899")

        # 更新表格
        self._editing_blocked = True  # 阻止 cellChanged 信号
        self.table.setRowCount(0)
        # 倒序显示，最新的在最上面
        for row in reversed(self.today_sales_records):
            r = self.table.rowCount()
            self.table.insertRow(r)
            
            # 时间列（不可编辑）
            time_item = QTableWidgetItem(row[0])
            time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, 0, time_item)
            
            # 鱼干列（可编辑）
            self.table.setItem(r, 1, QTableWidgetItem(row[1]))
            
            # 鱼饵列（不可编辑）
            bait_item = QTableWidgetItem(row[2])
            bait_item.setFlags(bait_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, 2, bait_item)
            
            # 删除按钮（常驻）
            self.table.add_delete_button(r)
            
        self._editing_blocked = False  # 恢复编辑信号处理
        
        # 通知悬浮窗更新额度显示（修复刷新时间后悬浮窗不同步的问题）
        self.data_changed_signal.emit()
            
    def _write_sale_to_csv(self, amount):
        """
        Internal helper to write sale to CSV with safety checks.
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            bait_used = cfg.current_bait
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            bait_used = cfg.current_bait
            
            sales_path = cfg.sales_file
            
            # Ensure directory exists
            if not sales_path.parent.exists():
                sales_path.parent.mkdir(parents=True)
            
            file_exists = sales_path.exists()
            
            with open(sales_path, 'a', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['Timestamp', 'Amount', 'BaitUsed'])
                writer.writerow([timestamp, amount, bait_used])
            return True
        except Exception as e:
            print(f"Failed to write sales record: {e}")
            return False

    def add_sale_record(self, amount):
        """
        Called by worker signal when a sale is automatically recorded.
        Since worker already wrote the file, we just reload here.
        """
        # Reload data to refresh UI (reload_data 会自动 emit data_changed_signal)
        self.reload_data()

    def _update_line_chart(self):
        """绘制趋势图：使用圆润曲线和柔和配色，跳过无数据日期"""
        self.line_chart.removeAllSeries()
        for axis in self.line_chart.axes():
            self.line_chart.removeAxis(axis)
        
        # 使用 QSplineSeries 实现圆润曲线
        series_sales = QSplineSeries()
        series_sales.setName("总收益")
        series_sales.setColor(QColor(CHART_COLORS['sales']))
        series_sales.setPointsVisible(True)
        series_sales.setPointLabelsVisible(False)
        series_sales.hovered.connect(lambda point, state: self._on_line_hover(point, state, "总收益"))
        pen = series_sales.pen()
        pen.setWidth(3)  # 加粗线条使数据点更明显
        series_sales.setPen(pen)

        series_cost = QSplineSeries()
        series_cost.setName("消耗成本")
        series_cost.setColor(QColor(CHART_COLORS['cost']))
        series_cost.setPointsVisible(True)
        series_cost.setPointLabelsVisible(False)
        series_cost.hovered.connect(lambda point, state: self._on_line_hover(point, state, "消耗成本"))
        pen = series_cost.pen()
        pen.setWidth(3)
        series_cost.setPen(pen)

        series_net = QSplineSeries()
        series_net.setName("净收益")
        series_net.setColor(QColor(CHART_COLORS['net']))
        series_net.setPointsVisible(True)
        series_net.setPointLabelsVisible(False)
        series_net.hovered.connect(lambda point, state: self._on_line_hover(point, state, "净收益"))
        pen = series_net.pen()
        pen.setWidth(3)
        series_net.setPen(pen)
        
        # 只使用有数据的日期，跳过无数据日期
        sorted_dates = sorted(self.history_daily_sales.keys())
        if not sorted_dates: return
        
        # 保存日期索引映射用于 tooltip
        self.line_chart_dates = sorted_dates
        
        max_val = 100
        # 使用序号作为 X 坐标而非时间戳，这样可以跳过无数据日期
        for idx, date_str in enumerate(sorted_dates):
            sales = self.history_daily_sales[date_str]
            cost = self.history_daily_cost[date_str]
            net = sales - cost
            
            series_sales.append(idx, sales)
            series_cost.append(idx, cost)
            series_net.append(idx, net)
            
            if sales > max_val: max_val = sales
        
        # 添加散点系列显示明显的数据点标记
        scatter_sales = QScatterSeries()
        scatter_sales.setName("")  # 不显示在图例中
        scatter_sales.setColor(QColor(CHART_COLORS['sales']))
        scatter_sales.setMarkerSize(10)  # 数据点大小
        scatter_sales.setBorderColor(QColor("white"))
        
        scatter_cost = QScatterSeries()
        scatter_cost.setName("")
        scatter_cost.setColor(QColor(CHART_COLORS['cost']))
        scatter_cost.setMarkerSize(10)
        scatter_cost.setBorderColor(QColor("white"))
        
        scatter_net = QScatterSeries()
        scatter_net.setName("")
        scatter_net.setColor(QColor(CHART_COLORS['net']))
        scatter_net.setMarkerSize(10)
        scatter_net.setBorderColor(QColor("white"))
        
        for idx, date_str in enumerate(sorted_dates):
            sales = self.history_daily_sales[date_str]
            cost = self.history_daily_cost[date_str]
            net = sales - cost
            scatter_sales.append(idx, sales)
            scatter_cost.append(idx, cost)
            scatter_net.append(idx, net)
            
        self.line_chart.addSeries(series_sales)
        self.line_chart.addSeries(series_cost)
        self.line_chart.addSeries(series_net)
        self.line_chart.addSeries(scatter_sales)
        self.line_chart.addSeries(scatter_cost)
        self.line_chart.addSeries(scatter_net)
        
        # 使用类别轴显示日期标签（只显示有数据的日期）
        axis_x = QBarCategoryAxis()
        categories = [d[5:] for d in sorted_dates]  # MM-DD 格式
        axis_x.append(categories)
        axis_x.setGridLineVisible(False)
        
        # 设置图表宽度
        points_count = len(sorted_dates)
        pixels_per_point = 80  # 增大间距让标签完整显示
        
        viewport_width = self.line_scroll.width()
        if viewport_width < 100: viewport_width = 800

        usable_width = viewport_width - 80
        capacity = max(1, int(usable_width / pixels_per_point))
        
        if points_count <= capacity:
            self.line_chart_view.setMinimumWidth(0)
        else:
            required_width = points_count * pixels_per_point + 100
            self.line_chart_view.setMinimumWidth(required_width)

        self.line_chart.addAxis(axis_x, Qt.AlignBottom)
        series_sales.attachAxis(axis_x)
        series_cost.attachAxis(axis_x)
        series_net.attachAxis(axis_x)
        scatter_sales.attachAxis(axis_x)
        scatter_cost.attachAxis(axis_x)
        scatter_net.attachAxis(axis_x)
        
        # Axis Y
        axis_y = QValueAxis()
        nice_max = self._get_nice_max_axis(max_val)
        axis_y.setRange(0, nice_max)
        axis_y.setLabelFormat("%d")
        axis_y.setTickCount(6)
        
        self.line_chart.addAxis(axis_y, Qt.AlignLeft)
        series_sales.attachAxis(axis_y)
        series_cost.attachAxis(axis_y)
        series_net.attachAxis(axis_y)
        scatter_sales.attachAxis(axis_y)
        scatter_cost.attachAxis(axis_y)
        scatter_net.attachAxis(axis_y)
        
        self._apply_chart_theme(self.line_chart)
        
        # 隐藏散点系列的图例
        for marker in self.line_chart.legend().markers(scatter_sales):
            marker.setVisible(False)
        for marker in self.line_chart.legend().markers(scatter_cost):
            marker.setVisible(False)
        for marker in self.line_chart.legend().markers(scatter_net):
            marker.setVisible(False)

    def _update_bar_chart(self):
        """绘制柱状图：使用柔和配色和紧凑间距"""
        self.bar_chart.removeAllSeries()
        for axis in self.bar_chart.axes():
            self.bar_chart.removeAxis(axis)
        
        # 应用温暖系配色
        set_sales = QBarSet("总收益")
        set_sales.setColor(QColor(CHART_COLORS['sales']))
        set_sales.hovered.connect(self._on_bar_hover)
        
        set_cost = QBarSet("消耗成本")
        set_cost.setColor(QColor(CHART_COLORS['cost']))
        set_cost.hovered.connect(self._on_bar_hover)

        set_net = QBarSet("净收益")
        set_net.setColor(QColor(CHART_COLORS['net']))
        set_net.hovered.connect(self._on_bar_hover)
        
        sorted_dates = sorted(self.history_daily_sales.keys())
        
        display_dates = sorted_dates
        self.bar_categories_dates = display_dates

        if not display_dates: return
        
        categories = []
        max_val = 100
        
        for date_str in display_dates:
            sales = self.history_daily_sales[date_str]
            cost = self.history_daily_cost[date_str]
            net = sales - cost
            
            set_sales.append(sales)
            set_cost.append(cost)
            set_net.append(net)
            
            categories.append(date_str[5:]) # MM-DD
            if sales > max_val: max_val = sales
            
        series = QBarSeries()
        series.append(set_sales)
        series.append(set_cost)
        series.append(set_net)
        # 设置柱子宽度比例（0-1，值越大柱子越宽、间距越小）
        series.setBarWidth(0.85)
        self.bar_chart.addSeries(series)
        
        axis_x = QBarCategoryAxis()
        axis_x.setGridLineVisible(False)
        
        # 增大间距让日期标签完整显示
        points_count = len(display_dates)
        pixels_per_group = 80  # 从 50 增大到 80
        
        viewport_width = self.bar_scroll.width()
        if viewport_width < 100: viewport_width = 800
        
        usable_width = viewport_width - 80
        capacity = max(1, int(usable_width / pixels_per_group))
        
        if points_count < capacity:
            # Pad categories with empty strings to maintain density
            # We append the real categories first, then padding
            padding_count = capacity - points_count
            # Create dummy dates for display (e.g. padding to fill space)
            # or just empty strings. Screenshot shows clean grid lines.
            padding_cats = [" " * i for i in range(padding_count)]
            
            axis_x.append(categories + padding_cats)
            self.bar_chart_view.setMinimumWidth(0)
        else:
            required_width = points_count * pixels_per_group + 100
            self.bar_chart_view.setMinimumWidth(required_width)
            axis_x.append(categories)

        self.bar_chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)
        
        axis_y = QValueAxis()
        nice_max = self._get_nice_max_axis(max_val)
        axis_y.setRange(0, nice_max)
        axis_y.setLabelFormat("%d")
        axis_y.setTickCount(6)
        axis_y.setGridLineVisible(True) # Ensure horizontal lines are visible

        self.bar_chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)
        
        self._apply_chart_theme(self.bar_chart)

    def _get_nice_max_axis(self, value):
        if value <= 0: return 100
        # Determine step size
        import math
        # e.g. 850 -> order=100.
        order = 10 ** math.floor(math.log10(value))
        
        # Normalize value to 1-10 range
        norm = value / order
        
        step = order
        if norm <= 1.0: step = 0.2 * order # shouldn't happen with floor log10 logic usually unless equal
        elif norm <= 2.0: step = 0.5 * order
        elif norm <= 5.0: step = 1.0 * order
        else: step = 2.0 * order
        
        # Actually simplest approach:
        # Find next multiple of 100, 500, 1000 etc.
        # Let's try to get exactly 5 intervals if possible (tickCount=6)
        # nice_max should be divisible by 5
        
        target_step = value / 5.0
        # Round target_step up to nice number (1, 2, 5, 10, 20, 50...)
        magnitude = 10 ** math.floor(math.log10(target_step))
        residual = target_step / magnitude
        
        if residual > 5: nice_step = 10 * magnitude
        elif residual > 2: nice_step = 5 * magnitude
        elif residual > 1: nice_step = 2 * magnitude
        else: nice_step = 1 * magnitude
        
        nice_max = nice_step * 5
        return nice_max

    def _apply_chart_theme(self, chart):
        """应用图表主题：温和的背景效果"""
        is_dark = qconfig.theme.value == "Dark"
        
        # 不使用内置主题，保持自定义配色
        chart.setBackgroundVisible(True)
        
        # 设置温和的背景色
        if is_dark:
            chart.setBackgroundBrush(QBrush(QColor(45, 45, 50, 60)))  # 深色半透明
        else:
            chart.setBackgroundBrush(QBrush(QColor(250, 248, 245, 180)))  # 温暖米色半透明
        
        chart.setBackgroundRoundness(8)  # 圆角背景

    def _on_line_hover(self, point, state, name):
        """趋势图数据点悬停提示"""
        if state:
            # X 坐标现在是序号索引
            idx = int(round(point.x()))
            if not hasattr(self, 'line_chart_dates') or idx < 0 or idx >= len(self.line_chart_dates):
                return
            
            date_str = self.line_chart_dates[idx]
            sales = self.history_daily_sales.get(date_str, 0)
            cost = self.history_daily_cost.get(date_str, 0)
            net = sales - cost
            
            tooltip_text = (f"日期: {date_str}\n"
                            f"总收益: {sales}\n"
                            f"消耗成本: {cost}\n"
                            f"净收益: {net}")
            
            QToolTip.showText(QCursor.pos(), tooltip_text)
        else:
            QToolTip.hideText()

    def _on_bar_hover(self, status, index):
        if status:
            if index < 0 or index >= len(self.bar_categories_dates):
                return
                
            date_str = self.bar_categories_dates[index]
            sales = self.history_daily_sales.get(date_str, 0)
            cost = self.history_daily_cost.get(date_str, 0)
            net = sales - cost
            
            tooltip_text = (f"日期: {date_str}\n"
                            f"总收益: {sales}\n"
                            f"消耗成本: {cost}\n"
                            f"净收益: {net}")
            
            QToolTip.showText(QCursor.pos(), tooltip_text)
        else:
            QToolTip.hideText()

