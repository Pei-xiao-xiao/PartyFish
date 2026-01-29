"""
周期重置管理器
负责管理每日/周期重置的定时器和相关逻辑
"""

from datetime import datetime, timedelta
from PySide6.QtCore import QTimer


class CycleResetManager:
    """周期重置管理器类"""

    def __init__(self, main_window):
        """
        初始化周期重置管理器

        Args:
            main_window: MainWindow 实例
        """
        self.window = main_window
        self._reset_timer = QTimer(self.window)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self._on_cycle_reset)

    def start(self):
        """启动周期重置定时器"""
        self.schedule_next_reset()

    def schedule_next_reset(self):
        """计算并安排下一次重置触发"""
        from src.config import cfg

        region = cfg.global_settings.get("server_region", "CN")
        now = datetime.now()

        if region == "CN":
            next_reset = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            noon_today = now.replace(hour=12, minute=0, second=0, microsecond=0)
            next_reset = (
                noon_today if now < noon_today else noon_today + timedelta(days=1)
            )

        ms_until_reset = max(1000, int((next_reset - now).total_seconds() * 1000))

        self._reset_timer.stop()
        self._reset_timer.setInterval(ms_until_reset)
        self._reset_timer.start()

        print(
            f"下次重置: {next_reset.strftime('%H:%M')} ({ms_until_reset // 3600000}h {(ms_until_reset % 3600000) // 60000}m 后)"
        )

    def _on_cycle_reset(self):
        """周期重置时触发"""
        self.window.profit_interface.reload_data()
        self.window._update_overlay_limit()
        self.window.append_log("新的一天开始了，今日统计数据已重置。")
        self.schedule_next_reset()

    def on_server_region_changed(self, new_region: str):
        """服务器区域切换时，重新安排重置时间"""
        self.schedule_next_reset()
