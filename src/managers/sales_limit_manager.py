"""
销售额度管理器
负责计算和更新销售额度相关信息
"""

import csv
from datetime import datetime


class SalesLimitManager:
    """销售额度管理器类"""

    def __init__(self, main_window):
        """
        初始化销售额度管理器

        Args:
            main_window: MainWindow 实例
        """
        self.window = main_window

    def update_overlay_limit(self, _=None):
        """更新悬浮窗和首页的销售额度显示"""
        total_sales = self._calculate_total_sales()
        remaining = 899 - total_sales

        # 更新悬浮窗
        self.window.overlay.update_limit(remaining, total_sales)

        # 更新首页
        if hasattr(self.window, "home_interface"):
            self.window.home_interface.update_sales_progress(total_sales, 899)
            self.window.home_interface.update_pokedex_progress()

    def _calculate_total_sales(self):
        """
        计算当前周期的总销售额

        Returns:
            int: 总销售额
        """
        from src.config import cfg

        total_sales = 0
        try:
            path = cfg.sales_file
            if path.exists():
                start_time = self._get_cycle_start_time()

                with open(path, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if row:
                            try:
                                row_dt = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                                if row_dt >= start_time:
                                    total_sales += int(row[1])
                            except ValueError:
                                pass
        except:
            pass

        return total_sales

    def _get_cycle_start_time(self):
        """
        获取当前周期的开始时间

        Returns:
            datetime: 周期开始时间
        """
        start_time_func = getattr(
            self.window.profit_interface,
            "_get_current_cycle_start_time",
            lambda: datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
        )
        return start_time_func()
