"""
区域定义配置
包含游戏中各个检测区域的坐标定义
"""


class RegionConfig:
    """区域配置类"""

    def __init__(self):
        # 预定义区域（基于 2560x1440 分辨率）
        # 注意：检测区域需要比模板稍大，给模板匹配留出缓冲空间（约+10像素）
        self.REGIONS = {
            "cast_rod": {"coords": (1087, 1318, 35, 42), "anchor": "bottom_center"},
            "cast_rod_ice": {"coords": (1198, 1318, 35, 42), "anchor": "bottom_center"},
            "wait_bite": {"coords": (975, 1318, 35, 42), "anchor": "bottom_center"},
            "shangyu": {"coords": (1143, 1313, 25, 28), "anchor": "bottom_center"},
            "reel_in_star": {"coords": (1167, 160, 44, 44), "anchor": "top_center"},
            "bait_count": {"coords": (2316, 1294, 32, 26), "anchor": "bottom_right"},
            "bait_icon": {"coords": (2252, 1291, 91, 90), "anchor": "bottom_right"},
            "jiashi_popup": {"coords": (1237, 669, 40, 40), "anchor": "center"},
            "afk_popup": {"coords": (1147, 678, 40, 40), "anchor": "center"},
            "popup_exclamation": {"coords": (1250, 420, 60, 110), "anchor": "center"},
            "ocr_area": {"coords": (915, 75, 725, 150), "anchor": "top_center"},
            "sell_price_area": {
                "coords": (2030, 1045, 200, 50),
                "anchor": "bottom_right",
            },
            "UNO卡牌": {"coords": (2242, 1314, 284, 100), "anchor": "bottom_right"},
            "fish_name_tooltip": {
                "coords": (1819, 436, 235, 96),
                "anchor": "bottom_right",
            },
            "bucket_close_button": {
                "coords": (2449, 435, 24, 23),
                "anchor": "top_right",
            },
            "fish_inventory_lock_slot_1": {
                "coords": (1903, 566, 60, 60),
                "anchor": "bottom_right",
            },
            "weather_icon": {
                "coords": (2430, 45, 75, 70),
                "anchor": "top_right",
            },
            "fish_inventory": {
                "anchor": "bottom_right",
                "zones": [
                    {
                        "id": 1,
                        "coords": (1857, 521, 608, 603),
                        "grid": {
                            "rows": 4,
                            "cols": 4,
                            "cell_width": 152,
                            "cell_height": 151,
                            "star_offset": (58, 112),
                            "star_size": (47, 33),
                        },
                    },
                ],
                "release_button_offset": (200, 107),
                "single_release_button_offset": (80, 150),
                "single_release_fish_pos": (1933, 600),
            },
        }
