"""
游戏相关配置
包含游戏窗口、鱼饵、按钮位置等游戏相关的配置
"""


class GameConfig:
    """游戏配置类"""

    def __init__(self):
        # 游戏窗口标题列表（按优先级尝试，包含简体、繁体和英文）
        self.game_window_titles = ["猛兽派对", "猛獸派對", "Party Animals"]

        # 游戏窗口句柄（运行时设置）
        self.game_hwnd = None

        # 鱼饵价格
        self.BAIT_PRICES = {"蔓越莓": 1, "蓝莓": 2, "橡果": 3, "蘑菇": 4, "蜂蜜": 5}

        # 当前鱼饵（运行时设置）
        self.current_bait = "蔓越莓"

        # 按钮位置常量（相对于 2560x1440）
        self.BAIT_CROP_WIDTH1_BASE = 15
        self.BTN_JIASHI_NO = (1175, 778)
        self.BTN_JIASHI_YES = (1390, 778)
