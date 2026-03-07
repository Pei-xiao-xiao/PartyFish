import os
from datetime import datetime

from PySide6.QtCharts import QChart, QChartView, QPieSeries
from PySide6.QtCore import (
    QDate,
    QEvent,
    QPersistentModelIndex,
    QRect,
    QTimer,
    QUrl,
    Signal,
    Qt as QtCoreQt,
)
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QPainter
from PySide6.QtWidgets import (
    QCalendarWidget,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QStyledItemDelegate,
    QStyle,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    ComboBox,
    FluentIcon,
    PrimaryPushButton,
    SearchLineEdit,
    SegmentedWidget,
    TableWidget,
    TitleLabel,
    qconfig,
)

from src.config import cfg
from src.gui.components import QUALITY_COLORS
from src.services.record_chart_service import RecordChartService
from src.services.record_data_service import FishRecord, RecordDataService
from src.services.record_schema import infer_time_period_from_timestamp
from src.services.record_stats_service import RecordStatsService


TIME_COLUMN = 0
TIME_PERIOD_COLUMN = 1
WEATHER_COLUMN = 2
NAME_COLUMN = 3
WEIGHT_COLUMN = 4
QUALITY_COLUMN = 5
ACTION_COLUMN = 6
DETAIL_COLUMN_WIDTH = 72


class NumericTableWidgetItem(QTableWidgetItem):
    """Ensure numeric ordering works for the weight column."""

    def __lt__(self, other):
        try:
            return float(self.text().replace(" kg", "")) < float(
                other.text().replace(" kg", "")
            )
        except ValueError:
            return super().__lt__(other)


class DeleteButtonDelegate(QStyledItemDelegate):
    """Paint the delete action without creating a widget per row."""

    BUTTON_SIZE = 24
    ICON_SIZE = 14

    def __init__(self, table: "HoverDeleteTableWidget"):
        super().__init__(table)
        self.table = table
        self._pressed_index: QPersistentModelIndex | None = None

    def _button_rect(self, option) -> QRect:
        x = option.rect.x() + (option.rect.width() - self.BUTTON_SIZE) // 2
        y = option.rect.y() + (option.rect.height() - self.BUTTON_SIZE) // 2
        return QRect(x, y, self.BUTTON_SIZE, self.BUTTON_SIZE)

    def paint(self, painter, option, index):
        if index.column() != ACTION_COLUMN:
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        button_rect = self._button_rect(option)
        is_hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        is_pressed = (
            self._pressed_index is not None
            and self._pressed_index == QPersistentModelIndex(index)
        )

        if is_pressed:
            bg_color = QColor(224, 62, 62, 64)
        elif is_hover:
            bg_color = QColor(224, 62, 62, 36)
        else:
            bg_color = QColor(0, 0, 0, 0)

        painter.setPen(QtCoreQt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(button_rect, 6, 6)

        icon_color = QColor("#ff4d4f") if is_hover or is_pressed else QColor("#b3b3b3")
        icon = FluentIcon.DELETE.icon(color=icon_color)
        icon.paint(painter, button_rect.adjusted(5, 5, -5, -5))
        painter.restore()

    def editorEvent(self, event, model, option, index):
        if index.column() != ACTION_COLUMN:
            return super().editorEvent(event, model, option, index)

        button_rect = self._button_rect(option)

        if event.type() == QEvent.Type.MouseButtonPress:
            if button_rect.contains(event.pos()):
                self._pressed_index = QPersistentModelIndex(index)
                self.table.viewport().update(option.rect)
                return True
            return False

        if event.type() == QEvent.Type.MouseButtonRelease:
            was_pressed = (
                self._pressed_index is not None
                and self._pressed_index == QPersistentModelIndex(index)
            )
            self._pressed_index = None
            self.table.viewport().update(option.rect)

            if was_pressed and button_rect.contains(event.pos()):
                self.table.delete_row_signal.emit(index.row())
                return True
            return False

        if event.type() == QEvent.Type.MouseMove:
            self.table.viewport().update(option.rect)

        if event.type() in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
            self._pressed_index = None
            self.table.viewport().update(option.rect)

        return False


class HoverDeleteTableWidget(TableWidget):
    delete_row_signal = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self._delete_delegate = DeleteButtonDelegate(self)
        self.setItemDelegateForColumn(ACTION_COLUMN, self._delete_delegate)


class RecordsInterface(QWidget):
    SEARCH_REFRESH_DELAY_MS = 180
    TABLE_BATCH_SIZE = 30
    TIME_PERIOD_SORT_ORDER = {
        "凌晨": 0,
        "清晨": 1,
        "上午": 2,
        "下午": 3,
        "黄昏": 4,
        "深夜": 5,
    }
    WEATHER_SORT_ORDER = {
        "晴天": 0,
        "雾天": 1,
        "小雨": 2,
        "大雨": 3,
        "小雪": 4,
        "大雪": 5,
    }
    QUALITY_SORT_ORDER = {
        "标准": 0,
        "非凡": 1,
        "稀有": 2,
        "史诗": 3,
        "传说": 4,
        "传奇": 4,
    }
    QUALITY_ALIASES = {
        "传说": "传奇",
        "傳說": "传奇",
        "傳奇": "传奇",
        "標準": "标准",
        "史詩": "史诗",
    }
    TIME_PERIOD_ALIASES = {
        "淩晨": "凌晨",
        "黃昏": "黄昏",
    }

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("recordsInterface")

        self.data_service = RecordDataService()
        self.stats_service = RecordStatsService()
        self.chart_service = RecordChartService()

        self.all_records: list[FishRecord] = []
        self.cached_filtered_records: list[FishRecord] = []
        self._pending_table_records: list[FishRecord] = []
        self.batch_size = self.TABLE_BATCH_SIZE
        self.current_loaded_count = 0
        self.is_loading = False
        self.sort_column = 0
        self.sort_order = QtCoreQt.SortOrder.DescendingOrder
        self._current_view_key = "history"

        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.timeout.connect(self._flush_pending_records)

        self._search_refresh_timer = QTimer(self)
        self._search_refresh_timer.setSingleShot(True)
        self._search_refresh_timer.timeout.connect(self._reset_and_reload)

        self._load_more_timer = QTimer(self)
        self._load_more_timer.setSingleShot(True)
        self._load_more_timer.timeout.connect(self._load_more_data)

        self.vBoxLayout = QVBoxLayout(self)

        top_controls_layout = QHBoxLayout()
        self.view_switcher = SegmentedWidget(self)
        self.view_switcher.addItem("history", "全部统计")
        self.view_switcher.addItem("today", "今日统计")
        self.view_switcher.addItem("date", "日期统计")
        self.view_switcher.setCurrentItem("history")
        self.view_switcher.currentItemChanged.connect(self._on_view_changed)
        top_controls_layout.addWidget(self.view_switcher)

        self.data_dir_button = PrimaryPushButton("数据目录")
        self.data_dir_button.setFixedWidth(100)
        self.data_dir_button.clicked.connect(self._open_data_directory)
        top_controls_layout.addWidget(self.data_dir_button)

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

        self.search_input = SearchLineEdit()
        self.search_input.setPlaceholderText("鱼名/时段/天气")
        self.search_input.setFixedWidth(200)
        self.search_input.textChanged.connect(self._schedule_search_refresh)
        top_controls_layout.addWidget(QLabel("搜索:"))
        top_controls_layout.addWidget(self.search_input)

        top_controls_layout.addSpacing(20)

        self.filter_combo = ComboBox()
        self.filter_combo.addItems(
            ["全部品质", "标准", "非凡", "稀有", "史诗", "传奇", "首次捕获"]
        )
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        self.filter_combo.setFixedWidth(150)
        top_controls_layout.addWidget(QLabel("筛选品质:"))
        top_controls_layout.addWidget(self.filter_combo)
        self.vBoxLayout.addLayout(top_controls_layout)

        self._toggle_date_selector(False)

        self.selected_date = datetime.now().strftime("%Y-%m-%d")
        self.current_date_label.setText(self.selected_date)

        self.dashboard_layout_row1 = QHBoxLayout()
        self.dashboard_layout_row1.setSpacing(15)
        self.dashboard_layout_row1.setContentsMargins(0, 0, 40, 0)
        self.total_card = self._create_stat_card("总数", "0", FluentIcon.CALENDAR)
        self.today_card = self._create_stat_card("今日捕获", "0", FluentIcon.FLAG)
        self.legendary_card = self._create_stat_card("传奇数量", "0", FluentIcon.TAG)
        self.unhook_rate_card = self._create_stat_card("脱钩数", "0", FluentIcon.CLOSE)
        self.dashboard_layout_row1.addWidget(self.total_card)
        self.dashboard_layout_row1.addWidget(self.today_card)
        self.dashboard_layout_row1.addWidget(self.legendary_card)
        self.dashboard_layout_row1.addWidget(self.unhook_rate_card)
        self.vBoxLayout.addLayout(self.dashboard_layout_row1)

        bottom_layout = QHBoxLayout()

        self.table = HoverDeleteTableWidget(self)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["时间", "时段", "天气", "名称", "重量", "品质", "操作"]
        )
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.setWordWrap(False)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            TIME_COLUMN, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(TIME_PERIOD_COLUMN, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(WEATHER_COLUMN, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(NAME_COLUMN, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(WEIGHT_COLUMN, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(QUALITY_COLUMN, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(ACTION_COLUMN, QHeaderView.ResizeMode.Fixed)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(self.sort_column, self.sort_order)
        header.sectionClicked.connect(self._on_header_clicked)
        self.table.setColumnWidth(TIME_PERIOD_COLUMN, DETAIL_COLUMN_WIDTH)
        self.table.setColumnWidth(WEATHER_COLUMN, DETAIL_COLUMN_WIDTH)
        self.table.setColumnWidth(QUALITY_COLUMN, DETAIL_COLUMN_WIDTH)
        self.table.setColumnWidth(ACTION_COLUMN, DETAIL_COLUMN_WIDTH)
        self.table.verticalScrollBar().valueChanged.connect(self._check_scroll_load)
        self.table.delete_row_signal.connect(self._on_delete_row)
        bottom_layout.addWidget(self.table, 3)

        self._init_pie_chart()
        bottom_layout.addWidget(self.chart_view, 2)

        self.vBoxLayout.addLayout(bottom_layout)
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
        self.chart_view.setStyleSheet("background: transparent; border: none;")
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

    def _on_view_changed(self, item):
        """Handle switching between total, today, and date views."""
        self._current_view_key = item
        self._toggle_date_selector(item == "date")
        self._reset_and_reload()

    def _toggle_date_selector(self, visible: bool):
        for widget in (
            self.date_selector_label,
            self.date_selector_button,
            self.current_date_label,
        ):
            widget.setVisible(visible)

    def _schedule_search_refresh(self, _text: str):
        self._update_stats_and_table(rebuild_table=False)
        self._search_refresh_timer.start(self.SEARCH_REFRESH_DELAY_MS)

    def _on_filter_changed(self, *_):
        self._reset_and_reload()

    def _on_header_clicked(self, logical_index: int):
        if logical_index == ACTION_COLUMN:
            return

        if self.sort_column == logical_index:
            self.sort_order = (
                QtCoreQt.SortOrder.AscendingOrder
                if self.sort_order == QtCoreQt.SortOrder.DescendingOrder
                else QtCoreQt.SortOrder.DescendingOrder
            )
        else:
            self.sort_column = logical_index
            self.sort_order = (
                QtCoreQt.SortOrder.DescendingOrder
                if logical_index in (TIME_COLUMN, WEIGHT_COLUMN)
                else QtCoreQt.SortOrder.AscendingOrder
            )

        self.table.horizontalHeader().setSortIndicator(
            self.sort_column, self.sort_order
        )
        self._reset_and_reload()

    def _show_date_dialog(self):
        """Show a popup dialog for date selection."""
        from PySide6.QtGui import QTextCharFormat

        dialog = QDialog(self)
        dialog.setWindowTitle("选择日期")
        dialog.setModal(True)

        calendar = QCalendarWidget(dialog)
        calendar.setGridVisible(True)

        available_dates = self.data_service.get_available_dates(self.all_records)
        available_qdates = set()
        for date_str in available_dates:
            year, month, day = map(int, date_str.split("-"))
            available_qdates.add(QDate(year, month, day))

        available_format = QTextCharFormat()
        available_format.setForeground(QColor("#000000"))
        available_format.setFontWeight(100)
        available_format.setFontPointSize(12)

        unavailable_format = QTextCharFormat()
        unavailable_format.setForeground(QColor("gray"))
        unavailable_format.setFontWeight(50)
        unavailable_format.setFontPointSize(10)

        if available_qdates:
            min_date = min(available_qdates)
            max_date = max(available_qdates)
            calendar.setMinimumDate(min_date)
            calendar.setMaximumDate(max_date)

            start_date = min_date.addMonths(-1)
            end_date = max_date.addMonths(1)
            current_date = start_date

            while current_date <= end_date:
                if min_date <= current_date <= max_date:
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
            selected_qdate = calendar.selectedDate()
            if selected_qdate not in available_qdates and available_qdates:
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
            self._reset_and_reload()

    def _open_data_directory(self):
        """Open the Partyfish app data directory in the system file manager."""
        data_dir = cfg.user_data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(str(data_dir))
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir)))

    def _create_stat_card(self, title: str, value: str, icon):
        """Helper to create a more appealing stat card."""
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

    def _reset_and_reload(self):
        self._update_stats_and_table(rebuild_table=True)

    def _load_data(self):
        """Load data from CSV and rebuild the current view."""
        self._flush_timer.stop()
        self._search_refresh_timer.stop()
        self._load_more_timer.stop()
        self._pending_table_records.clear()
        self.all_records = self.data_service.load_records()
        self._update_stats_and_table(rebuild_table=True)

    def _normalize_record_date(self, date_text: str) -> str:
        normalized = str(date_text).strip()
        if "/" in normalized:
            parts = normalized.split("/")
            if len(parts) == 3:
                normalized = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
        return normalized

    def _normalize_weight_text(self, weight) -> str:
        return str(weight).strip().replace(" kg", "").replace("kg", "")

    def _normalize_quality_text(self, quality) -> str:
        quality_text = str(quality).strip()
        return self.QUALITY_ALIASES.get(quality_text, quality_text)

    def _normalize_time_period_text(self, time_period, timestamp: str = "") -> str:
        period_text = str(time_period).strip()
        period_text = self.TIME_PERIOD_ALIASES.get(period_text, period_text)
        if period_text:
            return period_text
        return infer_time_period_from_timestamp(timestamp)

    def _normalize_weather_text(self, weather) -> str:
        return str(weather).strip()

    def _record_matches_quality(self, record: FishRecord, filter_quality: str) -> bool:
        record_quality = self._normalize_quality_text(record.quality)

        if filter_quality == "全部品质":
            return True
        if filter_quality == "首次捕获":
            return record.is_new_record
        if filter_quality == "传奇":
            return record_quality == "传奇"
        return filter_quality in record_quality

    def _record_matches_search(self, record: FishRecord, search_text: str) -> bool:
        if not search_text:
            return True

        time_period = self._normalize_time_period_text(
            record.time_period, record.timestamp
        )
        weather = self._normalize_weather_text(record.weather)

        searchable_fields = (
            str(record.name).lower(),
            str(time_period).lower(),
            str(weather).lower(),
        )
        return any(search_text in field for field in searchable_fields if field)

    def _get_filtered_records(self) -> list[FishRecord]:
        if self._current_view_key == "today":
            view_records = self.data_service.filter_by_today(self.all_records)
        elif self._current_view_key == "date":
            view_records = self.data_service.filter_by_date(
                self.all_records, self.selected_date
            )
        else:
            view_records = self.all_records

        filter_quality = self.filter_combo.currentText().strip()
        search_text = self.search_input.text().strip().lower()

        filtered_records = []
        for record in view_records:
            if not self._record_matches_quality(record, filter_quality):
                continue
            if not self._record_matches_search(record, search_text):
                continue
            filtered_records.append(record)

        return filtered_records

    def _timestamp_sort_key(self, timestamp: str):
        normalized = str(timestamp).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(normalized, fmt)
            except ValueError:
                continue
        return datetime.min

    def _quality_sort_key(self, quality: str):
        normalized_quality = self._normalize_quality_text(quality)
        return self.QUALITY_SORT_ORDER.get(normalized_quality, -1), normalized_quality

    def _time_period_sort_key(self, time_period: str, timestamp: str):
        normalized_period = self._normalize_time_period_text(time_period, timestamp)
        return (
            self.TIME_PERIOD_SORT_ORDER.get(normalized_period, 999),
            normalized_period,
        )

    def _weather_sort_key(self, weather: str):
        normalized_weather = self._normalize_weather_text(weather)
        return self.WEATHER_SORT_ORDER.get(normalized_weather, 999), normalized_weather

    def _sort_records(self, records: list[FishRecord]) -> list[FishRecord]:
        reverse = self.sort_order == QtCoreQt.SortOrder.DescendingOrder

        if self.sort_column == TIME_COLUMN:
            key_func = lambda record: self._timestamp_sort_key(record.timestamp)
        elif self.sort_column == TIME_PERIOD_COLUMN:
            key_func = lambda record: self._time_period_sort_key(
                record.time_period, record.timestamp
            )
        elif self.sort_column == WEATHER_COLUMN:
            key_func = lambda record: self._weather_sort_key(record.weather)
        elif self.sort_column == NAME_COLUMN:
            key_func = lambda record: record.name
        elif self.sort_column == WEIGHT_COLUMN:
            key_func = lambda record: float(
                self._normalize_weight_text(record.weight) or 0
            )
        elif self.sort_column == QUALITY_COLUMN:
            key_func = lambda record: self._quality_sort_key(record.quality)
        else:
            return records

        return sorted(records, key=key_func, reverse=reverse)

    def _update_stats_and_table(self, rebuild_table: bool = False):
        """Update stats/cards/chart from the full filtered dataset."""
        filtered_records = self._sort_records(self._get_filtered_records())
        self.cached_filtered_records = filtered_records

        stats = self.stats_service.calculate_stats(filtered_records, self.all_records)
        self.total_card.value_label.setText(str(len(filtered_records)))
        self.today_card.value_label.setText(str(stats.today_count))
        self.legendary_card.value_label.setText(str(stats.legendary_count))
        self.unhook_rate_card.value_label.setText(str(stats.unhook_count))

        self.chart_service.update_pie_chart(
            self.pie_series, stats.quality_counts, qconfig.theme.value == "Dark"
        )
        self._update_legend_markers()

        if rebuild_table:
            self._load_more_timer.stop()
            self._pending_table_records.clear()
            self.current_loaded_count = 0
            self.is_loading = False
            self.table.setUpdatesEnabled(False)
            self.table.setRowCount(0)
            self.table.setUpdatesEnabled(True)
            self._load_more_data()
            self.table.scrollToTop()

    def _update_legend_markers(self):
        markers = self.chart_view.chart().legend().markers(self.pie_series)
        for marker in markers:
            slice_obj = marker.slice()
            quality_name = slice_obj.property("quality_name")
            if quality_name:
                marker.setLabel(quality_name)

    def _check_scroll_load(self, value: int):
        if self.is_loading or self._load_more_timer.isActive():
            return

        maximum = self.table.verticalScrollBar().maximum()
        if maximum <= 0:
            return

        if value >= int(maximum * 0.75):
            self._load_more_timer.start(0)

    def _load_more_data(self):
        if self.is_loading:
            return
        if self.current_loaded_count >= len(self.cached_filtered_records):
            return

        self.is_loading = True
        start_idx = self.current_loaded_count
        end_idx = min(start_idx + self.batch_size, len(self.cached_filtered_records))
        records_to_add = self.cached_filtered_records[start_idx:end_idx]

        self.table.setUpdatesEnabled(False)
        try:
            for record in records_to_add:
                self._add_row_to_table(
                    record.timestamp,
                    record.time_period,
                    record.weather,
                    record.name,
                    record.quality,
                    record.weight,
                    record.is_new_record,
                )
            self.current_loaded_count = end_idx
        finally:
            self.table.setUpdatesEnabled(True)
            self.is_loading = False

    def _add_row_to_table(
        self,
        timestamp,
        time_period,
        weather,
        name,
        quality,
        weight,
        is_new_record: bool = False,
    ):
        row_index = self.table.rowCount()
        self.table.insertRow(row_index)

        raw_quality = str(quality).strip()
        raw_time_period = self._normalize_time_period_text(time_period, str(timestamp))
        raw_weather = self._normalize_weather_text(weather)
        display_quality = self._normalize_quality_text(raw_quality)
        display_time_period = raw_time_period or "-"
        display_weather = raw_weather or "-"
        normalized_weight = self._normalize_weight_text(weight)
        display_weight = f"{normalized_weight} kg" if normalized_weight else "-"
        items = [
            QTableWidgetItem(str(timestamp)),
            QTableWidgetItem(display_time_period),
            QTableWidgetItem(display_weather),
            QTableWidgetItem(str(name)),
            NumericTableWidgetItem(display_weight),
            QTableWidgetItem(display_quality),
            QTableWidgetItem(""),
        ]

        items[0].setData(
            QtCoreQt.ItemDataRole.UserRole,
            (str(timestamp), str(name), raw_quality, normalized_weight),
        )

        items[TIME_PERIOD_COLUMN].setTextAlignment(QtCoreQt.AlignmentFlag.AlignCenter)
        items[WEATHER_COLUMN].setTextAlignment(QtCoreQt.AlignmentFlag.AlignCenter)
        items[NAME_COLUMN].setTextAlignment(QtCoreQt.AlignmentFlag.AlignCenter)
        items[WEIGHT_COLUMN].setTextAlignment(QtCoreQt.AlignmentFlag.AlignCenter)
        items[QUALITY_COLUMN].setTextAlignment(QtCoreQt.AlignmentFlag.AlignCenter)
        items[QUALITY_COLUMN].setData(QtCoreQt.ItemDataRole.UserRole, is_new_record)

        color = None
        if display_quality in QUALITY_COLORS:
            color = (
                QUALITY_COLORS[display_quality][1]
                if qconfig.theme.value == "Dark"
                else QUALITY_COLORS[display_quality][0]
            )

        if color:
            brush = QBrush(color)
            for item in items:
                item.setForeground(brush)

        items[ACTION_COLUMN].setFlags(
            items[ACTION_COLUMN].flags() & ~QtCoreQt.ItemFlag.ItemIsEditable
        )

        for col_index, item in enumerate(items):
            self.table.setItem(row_index, col_index, item)

    def _remove_record_from_memory(
        self, timestamp: str, name: str, quality: str, weight: str
    ) -> bool:
        target_weight = self._normalize_weight_text(weight)

        for index, record in enumerate(self.all_records):
            if (
                record.timestamp == timestamp
                and record.name == name
                and record.quality == quality
                and self._normalize_weight_text(record.weight) == target_weight
            ):
                del self.all_records[index]
                return True
        return False

    def _on_delete_row(self, row: int):
        """Delete the selected record and refresh the current lazy-loaded view."""
        ts_item = self.table.item(row, 0)
        if not ts_item:
            return

        record_key = ts_item.data(QtCoreQt.ItemDataRole.UserRole)
        if not record_key:
            return

        timestamp, name, quality, weight = record_key
        if self.data_service.delete_record(timestamp, name, quality, weight):
            self._remove_record_from_memory(timestamp, name, quality, weight)
            self._update_stats_and_table(rebuild_table=True)

    def add_record(self, record: dict):
        """Queue a UI refresh after a new record arrives from the worker."""
        timestamp = record.get(
            "timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        fish_record = FishRecord(
            timestamp=timestamp,
            time_period=self._normalize_time_period_text(
                record.get("time_period", ""), timestamp
            ),
            weather=self._normalize_weather_text(record.get("weather", "")),
            name=record["name"],
            quality=record["quality"],
            weight=str(record["weight"]),
            is_new_record=record.get("is_new_record", False),
        )
        self.all_records.insert(0, fish_record)
        self._pending_table_records.insert(0, fish_record)

        if self.isVisible() and not self._flush_timer.isActive():
            self._flush_timer.start(30)

    def _flush_pending_records(self):
        if not self._pending_table_records:
            return

        self._pending_table_records.clear()
        self._update_stats_and_table(rebuild_table=True)

    def showEvent(self, event):
        super().showEvent(event)
        if self._pending_table_records and not self._flush_timer.isActive():
            self._flush_timer.start(10)

    def refresh_table_colors(self):
        """Rebuild visible rows and chart using the current theme colors."""
        self.chart_service.apply_theme(
            self.chart_view.chart(), qconfig.theme.value == "Dark"
        )
        self._update_stats_and_table(rebuild_table=True)
