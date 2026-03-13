"""
图表构建服务
负责图表创建、样式配置、数据格式化
"""

import math
from typing import Dict
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtCharts import (
    QChart,
    QSplineSeries,
    QScatterSeries,
    QBarSeries,
    QBarSet,
    QBarCategoryAxis,
    QValueAxis,
)
from qfluentwidgets import isDarkTheme


# 图表配色常量
CHART_COLORS = {
    "sales": "#e57373",  # 温暖的珊瑚红
    "cost": "#81c784",  # 柔和的绿色
    "net": "#64b5f6",  # 清爽的蓝色
    "accent": "#ffb74d",  # 温暖的橙色
}


class ChartBuilderService:
    """图表构建服务类"""

    def build_line_chart(
        self,
        chart: QChart,
        daily_sales: Dict[str, int],
        daily_cost: Dict[str, int],
        chart_view,
        scroll_container,
    ):
        """
        构建趋势图

        Args:
            chart: QChart 对象
            daily_sales: 每日销售数据
            daily_cost: 每日成本数据
            chart_view: QChartView 对象
            scroll_container: 滚动容器
        """
        chart.removeAllSeries()
        for axis in chart.axes():
            chart.removeAxis(axis)

        # 创建曲线系列
        series_sales = QSplineSeries()
        series_sales.setName("总收益")
        series_sales.setColor(QColor(CHART_COLORS["sales"]))
        series_sales.setPointsVisible(True)
        series_sales.setPointLabelsVisible(False)
        pen = series_sales.pen()
        pen.setWidth(3)
        series_sales.setPen(pen)

        series_cost = QSplineSeries()
        series_cost.setName("消耗成本")
        series_cost.setColor(QColor(CHART_COLORS["cost"]))
        series_cost.setPointsVisible(True)
        series_cost.setPointLabelsVisible(False)
        pen = series_cost.pen()
        pen.setWidth(3)
        series_cost.setPen(pen)

        series_net = QSplineSeries()
        series_net.setName("净收益")
        series_net.setColor(QColor(CHART_COLORS["net"]))
        series_net.setPointsVisible(True)
        series_net.setPointLabelsVisible(False)
        pen = series_net.pen()
        pen.setWidth(3)
        series_net.setPen(pen)

        sorted_dates = sorted(daily_sales.keys())
        if not sorted_dates:
            return sorted_dates

        min_val = 0
        max_val = 100
        for idx, date_str in enumerate(sorted_dates):
            sales = daily_sales[date_str]
            cost = daily_cost.get(date_str, 0)
            net = sales - cost

            series_sales.append(idx, sales)
            series_cost.append(idx, cost)
            series_net.append(idx, net)

            min_val = min(min_val, net)
            max_val = max(max_val, sales, cost, net)

        # 创建散点系列
        scatter_sales = QScatterSeries()
        scatter_sales.setName("")
        scatter_sales.setColor(QColor(CHART_COLORS["sales"]))
        scatter_sales.setMarkerSize(10)
        scatter_sales.setBorderColor(QColor("white"))

        scatter_cost = QScatterSeries()
        scatter_cost.setName("")
        scatter_cost.setColor(QColor(CHART_COLORS["cost"]))
        scatter_cost.setMarkerSize(10)
        scatter_cost.setBorderColor(QColor("white"))

        scatter_net = QScatterSeries()
        scatter_net.setName("")
        scatter_net.setColor(QColor(CHART_COLORS["net"]))
        scatter_net.setMarkerSize(10)
        scatter_net.setBorderColor(QColor("white"))

        for idx, date_str in enumerate(sorted_dates):
            sales = daily_sales[date_str]
            cost = daily_cost.get(date_str, 0)
            net = sales - cost
            scatter_sales.append(idx, sales)
            scatter_cost.append(idx, cost)
            scatter_net.append(idx, net)

        chart.addSeries(series_sales)
        chart.addSeries(series_cost)
        chart.addSeries(series_net)
        chart.addSeries(scatter_sales)
        chart.addSeries(scatter_cost)
        chart.addSeries(scatter_net)

        # 设置 X 轴
        axis_x = QBarCategoryAxis()
        categories = [d[5:] for d in sorted_dates]
        axis_x.append(categories)
        axis_x.setGridLineVisible(False)

        # 设置图表宽度
        points_count = len(sorted_dates)
        pixels_per_point = 80

        viewport_width = scroll_container.width()
        if viewport_width < 100:
            viewport_width = 800

        usable_width = viewport_width - 80
        capacity = max(1, int(usable_width / pixels_per_point))

        if points_count <= capacity:
            chart_view.setMinimumWidth(0)
        else:
            required_width = points_count * pixels_per_point + 100
            chart_view.setMinimumWidth(required_width)

        chart.addAxis(axis_x, Qt.AlignBottom)
        series_sales.attachAxis(axis_x)
        series_cost.attachAxis(axis_x)
        series_net.attachAxis(axis_x)
        scatter_sales.attachAxis(axis_x)
        scatter_cost.attachAxis(axis_x)
        scatter_net.attachAxis(axis_x)

        # 设置 Y 轴
        axis_y = QValueAxis()
        nice_min, nice_max = self.calculate_nice_range(min_val, max_val)
        axis_y.setRange(nice_min, nice_max)
        axis_y.setLabelFormat("%d")
        tick_count = self._calculate_tick_count(nice_min, nice_max)
        axis_y.setTickCount(tick_count)
        axis_y.setMinorTickCount(1)

        chart.addAxis(axis_y, Qt.AlignLeft)
        series_sales.attachAxis(axis_y)
        series_cost.attachAxis(axis_y)
        series_net.attachAxis(axis_y)
        scatter_sales.attachAxis(axis_y)
        scatter_cost.attachAxis(axis_y)
        scatter_net.attachAxis(axis_y)

        self.apply_theme(chart)

        # 隐藏散点系列的图例
        for marker in chart.legend().markers(scatter_sales):
            marker.setVisible(False)
        for marker in chart.legend().markers(scatter_cost):
            marker.setVisible(False)
        for marker in chart.legend().markers(scatter_net):
            marker.setVisible(False)

        return sorted_dates

    def build_bar_chart(
        self,
        chart: QChart,
        daily_sales: Dict[str, int],
        daily_cost: Dict[str, int],
        chart_view,
        scroll_container,
    ):
        """
        构建柱状图

        Args:
            chart: QChart 对象
            daily_sales: 每日销售数据
            daily_cost: 每日成本数据
            chart_view: QChartView 对象
            scroll_container: 滚动容器
        """
        chart.removeAllSeries()
        for axis in chart.axes():
            chart.removeAxis(axis)

        set_sales = QBarSet("总收益")
        set_sales.setColor(QColor(CHART_COLORS["sales"]))

        set_cost = QBarSet("消耗成本")
        set_cost.setColor(QColor(CHART_COLORS["cost"]))

        set_net = QBarSet("净收益")
        set_net.setColor(QColor(CHART_COLORS["net"]))

        sorted_dates = sorted(daily_sales.keys())
        if not sorted_dates:
            return sorted_dates

        categories = []
        min_val = 0
        max_val = 100

        for date_str in sorted_dates:
            sales = daily_sales[date_str]
            cost = daily_cost.get(date_str, 0)
            net = sales - cost

            set_sales.append(sales)
            set_cost.append(cost)
            set_net.append(net)

            categories.append(date_str[5:])
            min_val = min(min_val, net)
            max_val = max(max_val, sales, cost, net)

        series = QBarSeries()
        series.append(set_sales)
        series.append(set_cost)
        series.append(set_net)
        series.setBarWidth(0.85)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.setGridLineVisible(False)

        # 设置图表宽度
        points_count = len(sorted_dates)
        pixels_per_group = 80

        viewport_width = scroll_container.width()
        if viewport_width < 100:
            viewport_width = 800

        usable_width = viewport_width - 80
        capacity = max(1, int(usable_width / pixels_per_group))

        if points_count < capacity:
            padding_count = capacity - points_count
            padding_cats = [" " * i for i in range(padding_count)]
            axis_x.append(categories + padding_cats)
            chart_view.setMinimumWidth(0)
        else:
            required_width = points_count * pixels_per_group + 100
            chart_view.setMinimumWidth(required_width)
            axis_x.append(categories)

        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        nice_min, nice_max = self.calculate_nice_range(min_val, max_val)
        axis_y.setRange(nice_min, nice_max)
        axis_y.setLabelFormat("%d")
        tick_count = self._calculate_tick_count(nice_min, nice_max)
        axis_y.setTickCount(tick_count)
        axis_y.setMinorTickCount(1)
        axis_y.setGridLineVisible(True)

        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)

        self.apply_theme(chart)

        return sorted_dates

    def calculate_nice_max(self, value: float) -> float:
        """
        计算合适的坐标轴最大值（1000的倍数）

        Args:
            value: 数据最大值

        Returns:
            float: 合适的坐标轴最大值
        """
        if value <= 0:
            return 1000

        return math.ceil(value / 1000) * 1000

    def calculate_nice_range(
        self, min_val: float, max_val: float
    ) -> tuple[float, float]:
        """
        计算合适的坐标轴范围（支持负值）

        Args:
            min_val: 数据最小值（可能为负）
            max_val: 数据最大值

        Returns:
            tuple: (nice_min, nice_max)
        """
        if min_val >= 0:
            return (0, self.calculate_nice_max(max_val))

        if max_val <= 0:
            nice_min = -self.calculate_nice_max(abs(min_val))
            return (nice_min, 0)

        abs_max = max(abs(min_val), abs(max_val))
        nice_bound = self.calculate_nice_max(abs_max)
        return (-nice_bound, nice_bound)

    def _calculate_tick_count(self, nice_min: float, nice_max: float) -> int:
        """
        计算刻度数量，确保每1000一个刻度，0是中间刻度

        Args:
            nice_min: 范围最小值
            nice_max: 范围最大值

        Returns:
            int: 刻度数量
        """
        if nice_min >= 0:
            return int(nice_max / 1000) + 1

        if nice_max <= 0:
            return int(abs(nice_min) / 1000) + 1

        return int(nice_max / 1000) + int(abs(nice_min) / 1000) + 1

    def apply_theme(self, chart: QChart):
        """
        应用图表主题

        Args:
            chart: QChart 对象
        """
        is_dark = isDarkTheme()
        chart.setTheme(
            QChart.ChartTheme.ChartThemeDark
            if is_dark
            else QChart.ChartTheme.ChartThemeLight
        )

        chart.setBackgroundVisible(True)

        if is_dark:
            chart.setBackgroundBrush(QBrush(QColor(45, 45, 50, 80)))
            chart.setPlotAreaBackgroundVisible(True)
            chart.setPlotAreaBackgroundBrush(QBrush(QColor(35, 35, 40, 70)))
            axis_label_color = QColor(222, 226, 232)
            axis_line_color = QColor(180, 188, 199, 140)
            grid_color = QColor(220, 226, 234, 70)
            title_color = QColor(236, 240, 246)
        else:
            chart.setBackgroundBrush(QBrush(QColor(250, 248, 245, 180)))
            chart.setPlotAreaBackgroundVisible(True)
            chart.setPlotAreaBackgroundBrush(QBrush(QColor(255, 255, 255, 160)))
            axis_label_color = QColor(51, 65, 85)
            axis_line_color = QColor(100, 116, 139, 130)
            grid_color = QColor(148, 163, 184, 90)
            title_color = QColor(30, 41, 59)

        chart.setBackgroundRoundness(8)
        chart.setTitleBrush(QBrush(title_color))
        chart.legend().setLabelColor(title_color)

        # 确保坐标轴标签和网格在主题切换后保持可读
        for axis in chart.axes():
            axis.setLabelsColor(axis_label_color)

            line_pen = axis.linePen()
            line_pen.setColor(axis_line_color)
            axis.setLinePen(line_pen)

            grid_pen = axis.gridLinePen()
            grid_pen.setColor(grid_color)
            axis.setGridLinePen(grid_pen)
