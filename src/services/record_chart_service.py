"""
记录图表服务
负责饼图创建、样式配置、交互处理
"""

from typing import Dict
from functools import partial
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import QToolTip
from PySide6.QtCharts import QChart, QPieSeries, QPieSlice
from src.gui.components import QUALITY_COLORS


class RecordChartService:
    """记录图表服务类"""

    def update_pie_chart(
        self, pie_series: QPieSeries, quality_counts: Dict[str, int], is_dark: bool
    ):
        """
        更新饼图数据

        Args:
            pie_series: 饼图系列对象
            quality_counts: 品质统计数据 {quality: count}
            is_dark: 是否为暗色主题
        """
        pie_series.clear()

        total_count = sum(quality_counts.values())
        if total_count == 0:
            return

        # 按 QUALITY_COLORS 顺序遍历，确保顺序一致
        for quality in QUALITY_COLORS:
            if quality not in quality_counts:
                continue

            count = quality_counts[quality]
            slice_color = (
                QUALITY_COLORS[quality][1] if is_dark else QUALITY_COLORS[quality][0]
            )

            pie_slice = QPieSlice(quality, count)
            pie_slice.setColor(slice_color)

            # 计算百分比并设置标签
            ratio = count / total_count
            pie_slice.setLabel(f"{ratio:.1%}")
            pie_slice.setLabelVisible(True)

            # 根据切片大小设置标签位置
            if ratio < 0.1:
                pie_slice.setLabelPosition(QPieSlice.LabelPosition.LabelOutside)
            else:
                pie_slice.setLabelPosition(
                    QPieSlice.LabelPosition.LabelInsideHorizontal
                )

            # 存储数据用于工具提示
            pie_slice.setProperty("count", count)
            pie_slice.setProperty("total_count", total_count)
            pie_slice.setProperty("quality_name", quality)

            # 连接悬停事件
            pie_slice.hovered.connect(partial(self._handle_slice_hover, pie_slice))

            pie_series.append(pie_slice)

    def _handle_slice_hover(self, pie_slice: QPieSlice, state: bool):
        """
        处理切片悬停事件

        Args:
            pie_slice: 饼图切片对象
            state: 悬停状态
        """

        # 切片爆炸效果
        pie_slice.setExploded(state)

        if state:
            # 显示工具提示
            count = pie_slice.property("count")
            total_count = pie_slice.property("total_count")
            quality = pie_slice.property("quality_name")
            percentage = (count / total_count) * 100 if total_count > 0 else 0

            tooltip_text = f"{quality}\n数量: {count}\n占比: {percentage:.2f}%"
            QToolTip.showText(QCursor.pos(), tooltip_text)
        else:
            QToolTip.hideText()

    def apply_theme(self, chart: QChart, is_dark: bool):
        """
        应用图表主题

        Args:
            chart: 图表对象
            is_dark: 是否为暗色主题
        """
        chart.setTheme(
            QChart.ChartTheme.ChartThemeDark
            if is_dark
            else QChart.ChartTheme.ChartThemeLight
        )
