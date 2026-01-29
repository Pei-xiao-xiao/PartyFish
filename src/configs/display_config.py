"""
显示相关配置
包含屏幕分辨率、缩放因子等显示相关的配置
"""


class DisplayConfig:
    """显示配置类"""

    def __init__(self):
        # 基准分辨率
        self.BASE_SCREEN_WIDTH = 2560
        self.BASE_SCREEN_HEIGHT = 1440

        # 当前屏幕分辨率（运行时更新）
        self.screen_width = self.BASE_SCREEN_WIDTH
        self.screen_height = self.BASE_SCREEN_HEIGHT

        # 缩放因子（运行时计算）
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.scale = 1.0

        # 游戏窗口偏移（用于截图定位）
        self.window_offset_x = 0
        self.window_offset_y = 0
