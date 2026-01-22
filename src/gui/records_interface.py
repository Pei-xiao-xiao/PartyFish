from PySide6.QtWidgets import QWidget, QVBoxLayout, QHeaderView, QTableWidgetItem, QLabel, QHBoxLayout, QFrame, QToolTip, QCalendarWidget, QPushButton, QDialog, QDialogButtonBox
from PySide6.QtGui import QColor, QBrush, Qt, QPainter, QCursor
from PySide6.QtCore import Qt as QtCoreQt, QMargins
from PySide6.QtCharts import QChart, QChartView, QPieSeries, QPieSlice
from qfluentwidgets import TableWidget, ComboBox, CardWidget, BodyLabel, TitleLabel, FluentIcon, qconfig, SegmentedWidget, InfoBadge, setTheme, Theme, PrimaryPushButton
from datetime import datetime
import csv
import os
from collections import Counter
from src.gui.components import QUALITY_COLORS
from src.config import cfg

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
        self.setObjectName('recordsInterface')
        
        # --- Main Layout ---
        self.vBoxLayout = QVBoxLayout(self)

        # --- Top Controls ---
        top_controls_layout = QHBoxLayout()
        self.view_switcher = SegmentedWidget(self)
        self.view_switcher.addItem('history', '全部统计')
        self.view_switcher.addItem('today', '今日统计')
        self.view_switcher.addItem('date', '日期统计')
        self.view_switcher.setCurrentItem('history')
        self.view_switcher.currentItemChanged.connect(self._on_view_changed)
        top_controls_layout.addWidget(self.view_switcher)
        
        # Date selector (initially hidden)
        self.date_selector_layout = QHBoxLayout()
        self.date_selector_label = QLabel("选择日期:")
        # Use PrimaryPushButton to make it more prominent
        self.date_selector_button = PrimaryPushButton("选择日期")
        self.date_selector_button.setFixedWidth(120)
        self.date_selector_button.clicked.connect(self._show_date_dialog)
        
        # Add label to display current selected date
        self.current_date_label = QLabel("")
        self.current_date_label.setFixedWidth(120)
        self.current_date_label.setStyleSheet("font-weight: bold; color: #3BA5D8; font-size: 14px;")
        
        # Add some spacing between components
        self.date_selector_layout.addWidget(self.date_selector_label)
        self.date_selector_layout.addSpacing(8)
        self.date_selector_layout.addWidget(self.date_selector_button)
        self.date_selector_layout.addSpacing(12)
        self.date_selector_layout.addWidget(self.current_date_label)
        self.date_selector_layout.addStretch(1)
        self.date_selector_layout.setContentsMargins(15, 0, 0, 0)
        top_controls_layout.addLayout(self.date_selector_layout)
        
        top_controls_layout.addStretch(1)
        self.filter_combo = ComboBox()
        self.filter_combo.addItems(['全部品质', '标准', '非凡', '稀有', '史诗', '传奇', '首次捕获'])
        self.filter_combo.currentTextChanged.connect(self._filter_table)
        self.filter_combo.setFixedWidth(150)
        top_controls_layout.addWidget(QLabel("筛选品质:"))
        top_controls_layout.addWidget(self.filter_combo)
        self.vBoxLayout.addLayout(top_controls_layout)
        
        # Initialize date selector as hidden
        self._toggle_date_selector(False)
        
        # Initialize selected date
        from datetime import datetime
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
        self.table.setHorizontalHeaderLabels(['时间', '名称', '重量', '品质'])
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.setWordWrap(False)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        bottom_layout.addWidget(self.table, 3) # Table takes 3/5 of space

        # Pie Chart
        self._init_pie_chart()
        bottom_layout.addWidget(self.chart_view, 2) # Chart takes 2/5 of space

        self.vBoxLayout.addLayout(bottom_layout)

        # --- Data Storage ---
        self.all_records = []
        self.current_qualities_in_view = [] # To refresh chart theme
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
        chart.setTheme(QChart.ChartTheme.ChartThemeDark if is_dark_theme else QChart.ChartTheme.ChartThemeLight)
        
        self.chart_view = QChartView(chart)
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

    def _on_view_changed(self, item):
        """Handle view change between different statistics views"""
        current_view = item
        if current_view == 'date':
            self._toggle_date_selector(True)
        else:
            self._toggle_date_selector(False)
        self._update_stats_and_table()
    
    def _toggle_date_selector(self, visible):
        """Show or hide the date selector layout"""
        for widget in [self.date_selector_label, self.date_selector_button, self.current_date_label]:
            widget.setVisible(visible)
    
    def _show_date_dialog(self):
        """Show a popup dialog for date selection"""
        from PySide6.QtGui import QTextCharFormat
        from PySide6.QtCore import QDate
        from PySide6.QtWidgets import QDialog, QVBoxLayout
        
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("选择日期")
        dialog.setModal(True)
        
        # Create calendar widget
        calendar = QCalendarWidget(dialog)
        calendar.setGridVisible(True)
        
        # Extract unique dates from all records
        available_dates = set()
        for record in self.all_records:
            date_str = record['timestamp'].split(' ')[0]  # Get YYYY-MM-DD part
            available_dates.add(date_str)
        
        # Convert available_dates to QDate objects for easier handling
        available_qdates = set()
        for date_str in available_dates:
            year, month, day = map(int, date_str.split('-'))
            available_qdates.add(QDate(year, month, day))
        
        # Create text formats
        # Format for available dates (with records) - extra black and bold
        available_format = QTextCharFormat()
        available_format.setForeground(QColor("#000000"))  # Pure black
        available_format.setFontWeight(100)  # Maximum bold
        available_format.setFontPointSize(12)  # Larger font size
        available_format.setFontItalic(False)
        available_format.setFontUnderline(False)
        
        # Format for unavailable dates (without records) - gray font
        unavailable_format = QTextCharFormat()
        unavailable_format.setForeground(QColor("gray"))
        unavailable_format.setFontWeight(50)  # Normal weight
        unavailable_format.setFontPointSize(10)  # Normal font size
        # Ensure font is gray for unavailable dates
        unavailable_format.setFontItalic(False)
        unavailable_format.setFontUnderline(False)
        
        # Set date range to limit calendar view
        if available_qdates:
            min_date = min(available_qdates)
            max_date = max(available_qdates)
            calendar.setMinimumDate(min_date)
            calendar.setMaximumDate(max_date)
            
            # First, apply unavailable format to all dates in the visible range
            # This ensures any default styles are overwritten
            start_date = min_date.addMonths(-1)  # Include previous month
            end_date = max_date.addMonths(1)  # Include next month
            current_date = start_date
            
            while current_date <= end_date:
                if current_date >= min_date and current_date <= max_date:
                    if current_date in available_qdates:
                        # Available date - black bold
                        calendar.setDateTextFormat(current_date, available_format)
                    else:
                        # Unavailable date within range - gray
                        calendar.setDateTextFormat(current_date, unavailable_format)
                else:
                    # Date outside range - gray
                    calendar.setDateTextFormat(current_date, unavailable_format)
                current_date = current_date.addDays(1)
        else:
            # If no records, set a very narrow range to make all dates unavailable
            today = QDate.currentDate()
            calendar.setMinimumDate(today)
            calendar.setMaximumDate(today)
            calendar.setDateTextFormat(today, unavailable_format)
        
        # Create a function to validate date selection
        def validate_selection():
            selected_date = calendar.selectedDate()
            if selected_date not in available_qdates:
                # Find the nearest available date
                if available_qdates:
                    # Set to first available date if current selection is invalid
                    calendar.setSelectedDate(next(iter(available_qdates)))
        
        # Connect selectionChanged signal to validate function
        calendar.selectionChanged.connect(validate_selection)
        
        # Set current selected date as default if it's available, otherwise use first available date
        year, month, day = map(int, self.selected_date.split('-'))
        default_qdate = QDate(year, month, day)
        if default_qdate in available_qdates:
            calendar.setSelectedDate(default_qdate)
        elif available_qdates:
            calendar.setSelectedDate(next(iter(available_qdates)))
        
        # Add OK/Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        
        # Layout
        layout = QVBoxLayout()
        layout.addWidget(calendar)
        layout.addWidget(button_box)
        dialog.setLayout(layout)
        
        # Show dialog and get result
        if dialog.exec() == QDialog.Accepted:
            selected_qdate = calendar.selectedDate()
            self.selected_date = selected_qdate.toString("yyyy-MM-dd")
            self.current_date_label.setText(self.selected_date)
            self._update_stats_and_table()
    
    def _on_date_changed(self):
        """Handle date selection change"""
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
        self.all_records = []
        
        data_path = cfg.records_file
        if not data_path.exists():
            self._update_stats_and_table()
            return

        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None) # Skip header
                
                for row in reader:
                    if len(row) >= 4:
                        record = {
                            'timestamp': row[0],
                            'name': row[1],
                            'quality': row[2],
                            'weight': row[3],
                            'is_new_record': False # Default value
                        }
                        
                        # Handle the new 'is_new_record' column if present
                        if len(row) >= 5:
                            record['is_new_record'] = (row[4] == 'Yes')
                        
                        self.all_records.append(record)
        except Exception as e:
            print(f"Error loading records: {e}")
        
        # Reverse records to show newest first by default
        self.all_records.reverse()
        self._update_stats_and_table()

    def _populate_table(self, records_to_display):
        """Populate the table with a given list of records"""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        
        for record in records_to_display:
            self._add_row_to_table(
                record['timestamp'],
                record['name'],
                record['quality'],
                record['weight'],
                record.get('is_new_record', False)
            )
        self.table.setSortingEnabled(True)

    def _add_row_to_table(self, timestamp, name, quality, weight, is_new_record=False):
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)
        
        items = [
            QTableWidgetItem(str(timestamp)),
            QTableWidgetItem(str(name)),
            NumericTableWidgetItem(str(weight)), # Use Numeric for weight
            QTableWidgetItem(str(quality))
        ]
        
        # Determine color based on quality and theme
        quality_str = str(quality)
        is_dark_theme = qconfig.theme.value == "Dark"
        color = None
        if quality_str in QUALITY_COLORS:
            color = QUALITY_COLORS[quality_str][1] if is_dark_theme else QUALITY_COLORS[quality_str][0]

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
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Filter records based on current view
        if current_view == '今日统计':
            display_records = [r for r in self.all_records if r['timestamp'].startswith(today_str)]
        elif current_view == '日期统计':
            # Use the selected date from the dialog
            display_records = [r for r in self.all_records if r['timestamp'].startswith(self.selected_date)]
        else: # All records (全部统计)
            display_records = self.all_records

        # --- Update Stats ---
        total_records = len(self.all_records)
        today_records = [r for r in self.all_records if r['timestamp'].startswith(today_str)]
        
        total_count = len(display_records)
        today_count = len(today_records)
        
        # Calculate unhook stats based on the current view
        total_attempts = len(display_records)
        unhook_count = [r['name'] for r in display_records].count('鱼跑了')

        # Calculate quality stats based on the current view
        self.current_qualities_in_view = [r['quality'] for r in display_records]
        # 统计传奇品质时兼容传说品质和繁体品质的数据
        legendary_count = self.current_qualities_in_view.count('传奇') + self.current_qualities_in_view.count('传说') 

        # Update labels - total_card shows dynamic count based on current view
        if current_view == '全部统计':
            # 全部统计 - show all records count
            self.total_card.value_label.setText(str(total_records))
        elif current_view == '今日统计':
            # 今日统计 - show today's records count
            self.total_card.value_label.setText(str(today_count))
        elif current_view == '日期统计':
            # 日期统计 - show selected date's records count
            self.total_card.value_label.setText(str(total_count))
        else:
            # Default to all records
            self.total_card.value_label.setText(str(total_records))
            
        self.today_card.value_label.setText(str(today_count))
        self.legendary_card.value_label.setText(str(legendary_count))
        self.unhook_rate_card.value_label.setText(str(unhook_count))

        # --- Update Table and Chart ---
        self._populate_table(display_records)
        self._update_pie_chart(self.current_qualities_in_view)
        self._filter_table() # Re-apply current filter

    def _update_pie_chart(self, qualities):
        """Updates the pie chart with the given quality data."""
        self.pie_series.clear()
        
        # 将传说品质的数据转换为传奇品质进行统计
        processed_qualities = ['传奇' if q == '传说' else q for q in qualities]
        quality_counts = Counter(processed_qualities)
        total_fish_caught = sum(quality_counts.values())

        if total_fish_caught == 0:
            return
        
        is_dark_theme = qconfig.theme.value == "Dark"
        
        # Ensure consistent order by iterating through QUALITY_COLORS
        for quality in QUALITY_COLORS:
            if quality in quality_counts:
                count = quality_counts[quality]
                slice_color = QUALITY_COLORS[quality][1] if is_dark_theme else QUALITY_COLORS[quality][0]
                
                pie_slice = QPieSlice(quality, count)
                pie_slice.setColor(slice_color)
                
                # Calculate ratio and set label (Percentage only)
                ratio = count / total_fish_caught
                pie_slice.setLabel(f"{ratio:.1%}")
                pie_slice.setLabelVisible(True)
                
                # Handle label position based on slice size
                if ratio < 0.1:
                    pie_slice.setLabelPosition(QPieSlice.LabelPosition.LabelOutside)
                else:
                    pie_slice.setLabelPosition(QPieSlice.LabelPosition.LabelInsideHorizontal)
                
                # Store data needed for tooltip and legend
                pie_slice.setProperty("count", count)
                pie_slice.setProperty("total_count", total_fish_caught)
                pie_slice.setProperty("quality_name", quality)
                
                # Connect hover effect
                pie_slice.hovered.connect(self._handle_slice_hover)
                
                self.pie_series.append(pie_slice)

        # Customizing Legend Markers to show only Quality Name
        # Note: Markers are generated after adding series to chart, 
        # but here we are just updating the series content.
        # We need to refresh the markers *after* the series has been processed by the chart.
        # However, since the series is already in the chart (in __init__), updating it should trigger updates.
        # We might need to process events or access markers directly.
        
        # Accessing markers requires the series to be added to the chart.
        # We iterate through the markers and set their label to the quality name.
        markers = self.chart_view.chart().legend().markers(self.pie_series)
        for marker in markers:
            # The marker's slice corresponds to one of the slices we just added
            # BUT, the order might be preserved. 
            # Safest way is to check the slice property.
            slice_obj = marker.slice()
            quality_name = slice_obj.property("quality_name")
            if quality_name:
                marker.setLabel(quality_name)

    def _handle_slice_hover(self, state):
        """Explode slice and show tooltip on hover."""
        pie_slice = self.sender()
        if not isinstance(pie_slice, QPieSlice):
            return

        # Explode/un-explode the slice
        pie_slice.setExploded(state)
        
        if state:
            # Calculate tooltip text
            count = pie_slice.property("count")
            total_count = pie_slice.property("total_count")
            quality = pie_slice.property("quality_name")
            percentage = (count / total_count) * 100 if total_count > 0 else 0
            
            tooltip_text = f"{quality}\n数量: {count}\n占比: {percentage:.2f}%"
            
            # Show tooltip at cursor position
            QToolTip.showText(QCursor.pos(), tooltip_text)
        else:
            # Hide tooltip
            QToolTip.hideText()

    def _filter_table(self, text=None):
        """Filter rows based on quality"""
        if text is None:
            text = self.filter_combo.currentText()
        
        filter_quality = text
        
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 3) # Quality column
            # We can retrieve the record object if needed, but here we just need to know if it's a new record
            # Since we populate table row by row from display_records, we might need a better way to check "is_new_record"
            # However, for simplicity, let's look at the underlying data.
            # Wait, the table item doesn't store the full record dict directly.
            # To handle "首次捕获" properly without adding a column, we need to map row index back to data or store data in item.
            
            # Let's use UserRole to store the is_new_record flag in the quality item
            is_new_record = item.data(QtCoreQt.ItemDataRole.UserRole)
            
            if not item: continue
            
            should_show = False
            if filter_quality == '全部品质':
                should_show = True
            elif filter_quality == '首次捕获':
                if is_new_record:
                    should_show = True
            else:
                # 搜索传奇品质时兼容传说品质的数据
                quality_text = item.text()
                if filter_quality == '传奇':
                    should_show = quality_text in ['传奇', '传说']
                elif filter_quality in quality_text:
                    should_show = True
            
            self.table.setRowHidden(row, not should_show)

    def add_record(self, record: dict):
        """
        添加一条记录到表格 (Called by worker signal)
        """
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record['timestamp'] = now_ts
        
        # Add to the beginning of the list to show newest first
        self.all_records.insert(0, record)
        
        # Refresh everything
        self._update_stats_and_table()
        self.table.scrollToTop()
            
    def refresh_table_colors(self):
        """
        Iterate over all rows and re-apply colors based on the current theme.
        Also, refresh the chart theme.
        """
        is_dark_theme = qconfig.theme.value == "Dark"
        
        # Refresh chart
        self.chart_view.chart().setTheme(QChart.ChartTheme.ChartThemeDark if is_dark_theme else QChart.ChartTheme.ChartThemeLight)
        self._update_pie_chart(self.current_qualities_in_view)

        # Refresh table
        for row in range(self.table.rowCount()):
            quality_item = self.table.item(row, 3) # Quality is in column 3
            if not quality_item:
                continue
            
            quality_str = quality_item.text()
            color = None
            if quality_str in QUALITY_COLORS:
                color = QUALITY_COLORS[quality_str][1] if is_dark_theme else QUALITY_COLORS[quality_str][0]

            if color:
                brush = QBrush(color)
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item.setForeground(brush)
