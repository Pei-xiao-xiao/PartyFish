from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHeaderView,
    QTableWidgetItem,
    QLabel,
    QHBoxLayout,
    QFrame,
    QToolTip,
    QCalendarWidget,
    QPushButton,
    QDialog,
    QDialogButtonBox,
)
from PySide6.QtGui import QColor, QBrush, Qt, QPainter, QCursor
from PySide6.QtCore import Qt as QtCoreQt, QMargins, QDate
from PySide6.QtCharts import QChart, QChartView, QPieSeries, QPieSlice
from qfluentwidgets import (
    TableWidget,
    ComboBox,
    CardWidget,
    BodyLabel,
    TitleLabel,
    FluentIcon,
    qconfig,
    SegmentedWidget,
    InfoBadge,
    setTheme,
    Theme,
    PrimaryPushButton,
    SearchLineEdit,
)
from datetime import datetime
from src.gui.components import QUALITY_COLORS
from src.config import cfg
from src.services.record_data_service import RecordDataService, FishRecord
from src.services.record_stats_service import RecordStatsService
from src.services.record_chart_service import RecordChartService


class NumericTableWidgetItem(QTableWidgetItem):
    """
    Custom TableWidgetItem to ensure proper sorting for numeric columns (Weight).
    """

    def __lt__(self, other):
        try:
            return float(self.text()) < float(other.text())
        except ValueError:
            return super().__lt__(other)


class RecordsInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("recordsInterface")

        # 初始化服务
        self.data_service = RecordDataService()
        self.stats_service = RecordStatsService()
        self.chart_service = RecordChartService()

        # --- Main Layout ---
        self.vBoxLayout = QVBoxLayout(self)

        # --- Top Controls ---
        top_controls_layout = QHBoxLayout()
        self.view_switcher = SegmentedWidget(self)
        self.view_switcher.addItem("history", "全部统计")
        self.view_switcher.addItem("today", "今日统计")
        self.view_switcher.addItem("date", "日期统计")
        self.view_switcher.setCurrentItem("history")
        self.view_switcher.currentItemChanged.connect(self._on_view_changed)
        top_controls_layout.addWidget(self.view_switcher)

        # Date selector (initially hidden)
        self.date_selector_layout = QHBoxLayout()
        self.date_selector_label = QLabel("选择日期:")
        self.date_selector_button = PrimaryPushButton("选择日期")
        self.date_selector_button.setFixedWidth(120)
        self.date_selector_button.clicked.connect(self._show_date_dialog)

        self.current_date_label = QLabel("")
        self.current_date_label.setFixedWidth(120)
        self.current_date_label.setStyleSheet(
            "font-weight: bold; color: #3BA5D8; font-size: 14px;"
        )

        self.date_selector_layout.addWidget(self.date_selector_label)
        self.date_selector_layout.addSpacing(8)
        self.date_selector_layout.addWidget(self.date_selector_button)
        self.date_selector_layout.addSpacing(12)
        self.date_selector_layout.addWidget(self.current_date_label)
        self.date_selector_layout.addStretch(1)
        self.date_selector_layout.setContentsMargins(15, 0, 0, 0)
        top_controls_layout.addLayout(self.date_selector_layout)

        top_controls_layout.addStretch(1)

        # 搜索鱼名
        self.search_input = SearchLineEdit()
        self.search_input.setPlaceholderText("搜索鱼名")
        self.search_input.setFixedWidth(200)
        self.search_input.textChanged.connect(self._filter_table)
        top_controls_layout.addWidget(QLabel("搜索鱼名:"))
        top_controls_layout.addWidget(self.search_input)

        top_controls_layout.addSpacing(20)

        # 筛选品质
        self.filter_combo = ComboBox()
        self.filter_combo.addItems(
            ["全部品质", "标准", "非凡", "稀有", "史诗", "传奇", "首次捕获"]
        )
        self.filter_combo.currentTextChanged.connect(self._filter_table)
        self.filter_combo.setFixedWidth(150)
        top_controls_layout.addWidget(QLabel("筛选品质:"))
        top_controls_layout.addWidget(self.filter_combo)
        self.vBoxLayout.addLayout(top_controls_layout)

        # Initialize date selector as hidden
        self._toggle_date_selector(False)

        # Initialize selected date
        self.selected_date = datetime.now().strftime("%Y-%m-%d")
        self.current_date_label.setText(self.selected_date)

        # --- Dashboard (Statistics) ---
        self.dashboard_layout_row1 = QHBoxLayout()
        self.dashboard_layout_row1.setSpacing(15)
        self.total_card = self._create_stat_card("总数", "0", FluentIcon.CALENDAR)
        self.today_card = self._create_stat_card("今日捕获", "0", FluentIcon.FLAG)
        self.legendary_card = self._create_stat_card("传奇数量", "0", FluentIcon.TAG)
        self.unhook_rate_card = self._create_stat_card("脱钩数", "0", FluentIcon.CLOSE)
        self.dashboard_layout_row1.addWidget(self.total_card)
        self.dashboard_layout_row1.addWidget(self.today_card)
        self.dashboard_layout_row1.addWidget(self.legendary_card)
        self.dashboard_layout_row1.addWidget(self.unhook_rate_card)

        self.vBoxLayout.addLayout(self.dashboard_layout_row1)

        # --- Bottom Layout (Table + Chart) ---
        bottom_layout = QHBoxLayout()

        # Table
        self.table = TableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["时间", "名称", "重量", "品质"])
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.setWordWrap(False)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        bottom_layout.addWidget(self.table, 3)

        # Pie Chart
        self._init_pie_chart()
        bottom_layout.addWidget(self.chart_view, 2)

        self.vBoxLayout.addLayout(bottom_layout)

        # --- Data Storage ---
        self.all_records = []
        self._load_data()

    def _init_pie_chart(self):
        """Initializes the pie chart component."""
        self.pie_series = QPieSeries()
        self.pie_series.setHoleSize(0.35)

        chart = QChart()
        chart.addSeries(self.pie_series)
        chart.setTitle("品质分布")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        is_dark_theme = qconfig.theme.value == "Dark"
        self.chart_service.apply_theme(chart, is_dark_theme)

        self.chart_view = QChartView(chart)
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

    def _on_view_changed(self, item):
        """Handle view change between different statistics views"""
        current_view = item
        if current_view == "date":
            self._toggle_date_selector(True)
        else:
            self._toggle_date_selector(False)
        self._update_stats_and_table()

    def _toggle_date_selector(self, visible):
        """Show or hide the date selector layout"""
        for widget in [
            self.date_selector_label,
            self.date_selector_button,
            self.current_date_label,
        ]:
            widget.setVisible(visible)

    def _show_date_dialog(self):
        """Show a popup dialog for date selection"""
        from PySide6.QtGui import QTextCharFormat

        dialog = QDialog(self)
        dialog.setWindowTitle("选择日期")
        dialog.setModal(True)

        calendar = QCalendarWidget(dialog)
        calendar.setGridVisible(True)

        # 获取可用日期
        available_dates = self.data_service.get_available_dates(self.all_records)
        available_qdates = set()
        for date_str in available_dates:
            year, month, day = map(int, date_str.split("-"))
            available_qdates.add(QDate(year, month, day))

        # 创建文本格式
        available_format = QTextCharFormat()
        available_format.setForeground(QColor("#000000"))
        available_format.setFontWeight(100)
        available_format.setFontPointSize(12)

        unavailable_format = QTextCharFormat()
        unavailable_format.setForeground(QColor("gray"))
        unavailable_format.setFontWeight(50)
        unavailable_format.setFontPointSize(10)

        # 设置日期范围
        if available_qdates:
            min_date = min(available_qdates)
            max_date = max(available_qdates)
            calendar.setMinimumDate(min_date)
            calendar.setMaximumDate(max_date)

            start_date = min_date.addMonths(-1)
            end_date = max_date.addMonths(1)
            current_date = start_date

            while current_date <= end_date:
                if current_date >= min_date and current_date <= max_date:
                    if current_date in available_qdates:
                        calendar.setDateTextFormat(current_date, available_format)
                    else:
                        calendar.setDateTextFormat(current_date, unavailable_format)
                else:
                    calendar.setDateTextFormat(current_date, unavailable_format)
                current_date = current_date.addDays(1)
        else:
            today = QDate.currentDate()
            calendar.setMinimumDate(today)
            calendar.setMaximumDate(today)
            calendar.setDateTextFormat(today, unavailable_format)

        def validate_selection():
            selected_date = calendar.selectedDate()
            if selected_date not in available_qdates:
                if available_qdates:
                    calendar.setSelectedDate(next(iter(available_qdates)))

        calendar.selectionChanged.connect(validate_selection)

        year, month, day = map(int, self.selected_date.split("-"))
        default_qdate = QDate(year, month, day)
        if default_qdate in available_qdates:
            calendar.setSelectedDate(default_qdate)
        elif available_qdates:
            calendar.setSelectedDate(next(iter(available_qdates)))

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        layout = QVBoxLayout()
        layout.addWidget(calendar)
        layout.addWidget(button_box)
        dialog.setLayout(layout)

        if dialog.exec() == QDialog.Accepted:
            selected_qdate = calendar.selectedDate()
            self.selected_date = selected_qdate.toString("yyyy-MM-dd")
            self.current_date_label.setText(self.selected_date)
            self._update_stats_and_table()

    def _create_stat_card(self, title, value, icon):
        """Helper to create a more appealing stat card"""
        card = CardWidget(self)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(15, 10, 15, 10)

        icon_label = QLabel()
        icon_label.setPixmap(icon.icon(color=qconfig.themeColor.value).pixmap(28, 28))

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(10, 0, 0, 0)

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

    def _load_data(self):
        """Load data from CSV and populate table"""
        self.all_records = self.data_service.load_records()
        self._update_stats_and_table()

    def _populate_table(self, records_to_display):
        """Populate the table with a given list of records"""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        for record in records_to_display:
            self._add_row_to_table(
                record.timestamp,
                record.name,
                record.quality,
                record.weight,
                record.is_new_record,
            )
        self.table.setSortingEnabled(True)

    def _add_row_to_table(self, timestamp, name, quality, weight, is_new_record=False):
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)

        items = [
            QTableWidgetItem(str(timestamp)),
            QTableWidgetItem(str(name)),
            NumericTableWidgetItem(str(weight)),
            QTableWidgetItem(str(quality)),
        ]

        # Determine color based on quality and theme
        quality_str = str(quality)
        is_dark_theme = qconfig.theme.value == "Dark"
        color = None
        if quality_str in QUALITY_COLORS:
            color = (
                QUALITY_COLORS[quality_str][1]
                if is_dark_theme
                else QUALITY_COLORS[quality_str][0]
            )

        # Apply color to all items in the row
        if color:
            brush = QBrush(color)
            for item in items:
                item.setForeground(brush)

        # Store metadata (is_new_record) in the quality item (column 3)
        items[3].setData(QtCoreQt.ItemDataRole.UserRole, is_new_record)

        for col_index, item in enumerate(items):
            self.table.setItem(row_count, col_index, item)

    def _update_stats_and_table(self):
        """
        Central function to update stats and table based on the current view.
        """
        current_view_item = self.view_switcher.currentItem()
        if not current_view_item:
            return
        current_view = current_view_item.text()

        # 根据视图筛选记录
        if current_view == "今日统计":
            display_records = self.data_service.filter_by_today(self.all_records)
        elif current_view == "日期统计":
            display_records = self.data_service.filter_by_date(
                self.all_records, self.selected_date
            )
        else:
            display_records = self.all_records

        # 计算统计数据
        stats = self.stats_service.calculate_stats(display_records, self.all_records)

        # 更新统计卡片
        if current_view == "全部统计":
            self.total_card.value_label.setText(str(len(self.all_records)))
        elif current_view == "今日统计":
            self.total_card.value_label.setText(str(stats.today_count))
        elif current_view == "日期统计":
            self.total_card.value_label.setText(str(stats.total_count))
        else:
            self.total_card.value_label.setText(str(len(self.all_records)))

        self.today_card.value_label.setText(str(stats.today_count))
        self.legendary_card.value_label.setText(str(stats.legendary_count))
        self.unhook_rate_card.value_label.setText(str(stats.unhook_count))

        # 更新表格和图表
        self._populate_table(display_records)
        self.chart_service.update_pie_chart(
            self.pie_series, stats.quality_counts, qconfig.theme.value == "Dark"
        )
        self._update_legend_markers()
        self._filter_table()

    def _update_legend_markers(self):
        """更新图例标记"""
        markers = self.chart_view.chart().legend().markers(self.pie_series)
        for marker in markers:
            slice_obj = marker.slice()
            quality_name = slice_obj.property("quality_name")
            if quality_name:
                marker.setLabel(quality_name)

    def _filter_table(self):
        """Filter rows based on fish name and quality"""
        filter_quality = self.filter_combo.currentText()
        search_text = self.search_input.text().strip().lower()

        for row in range(self.table.rowCount()):
            quality_item = self.table.item(row, 3)
            name_item = self.table.item(row, 1)

            if not quality_item or not name_item:
                continue

            is_new_record = quality_item.data(QtCoreQt.ItemDataRole.UserRole)

            # 检查品质筛选
            quality_match = False
            if filter_quality == "全部品质":
                quality_match = True
            elif filter_quality == "首次捕获":
                if is_new_record:
                    quality_match = True
            else:
                quality_text = quality_item.text()
                if filter_quality == "传奇":
                    quality_match = quality_text in ["传奇", "传说"]
                elif filter_quality in quality_text:
                    quality_match = True

            # 检查鱼名搜索
            name_match = True
            if search_text:
                fish_name = name_item.text().lower()
                name_match = search_text in fish_name

            # 同时满足两个条件才显示
            should_show = quality_match and name_match
            self.table.setRowHidden(row, not should_show)

    def add_record(self, record: dict):
        """
        添加一条记录到表格 (Called by worker signal)
        """
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 转换为 FishRecord 对象
        fish_record = FishRecord(
            timestamp=now_ts,
            name=record["name"],
            quality=record["quality"],
            weight=record["weight"],
            is_new_record=record.get("is_new_record", False),
        )

        # 添加到列表开头
        self.all_records.insert(0, fish_record)

        # 刷新界面
        self._update_stats_and_table()
        self.table.scrollToTop()

    def refresh_table_colors(self):
        """
        Iterate over all rows and re-apply colors based on the current theme.
        Also, refresh the chart theme.
        """
        is_dark_theme = qconfig.theme.value == "Dark"

        # 刷新图表主题
        self.chart_service.apply_theme(self.chart_view.chart(), is_dark_theme)

        # 重新计算统计并更新图表
        current_view_item = self.view_switcher.currentItem()
        if current_view_item:
            current_view = current_view_item.text()
            if current_view == "今日统计":
                display_records = self.data_service.filter_by_today(self.all_records)
            elif current_view == "日期统计":
                display_records = self.data_service.filter_by_date(
                    self.all_records, self.selected_date
                )
            else:
                display_records = self.all_records

            stats = self.stats_service.calculate_stats(
                display_records, self.all_records
            )
            self.chart_service.update_pie_chart(
                self.pie_series, stats.quality_counts, is_dark_theme
            )
            self._update_legend_markers()

        # 刷新表格颜色
        for row in range(self.table.rowCount()):
            quality_item = self.table.item(row, 3)
            if not quality_item:
                continue

            quality_str = quality_item.text()
            color = None
            if quality_str in QUALITY_COLORS:
                color = (
                    QUALITY_COLORS[quality_str][1]
                    if is_dark_theme
                    else QUALITY_COLORS[quality_str][0]
                )

            if color:
                brush = QBrush(color)
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item.setForeground(brush)
