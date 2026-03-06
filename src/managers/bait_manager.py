"""
鱼饵管理器
负责鱼饵切换和管理
"""


class BaitManager:
    """鱼饵管理器类"""

    # 鱼饵顺序（从左到右）
    BAIT_ORDER = ["蔓越莓", "蓝莓", "橡果", "蘑菇", "蜂蜜"]

    def __init__(self, selected_baits):
        """
        初始化鱼饵管理器

        Args:
            selected_baits: 用户选择的鱼饵列表
        """
        self.selected_baits = selected_baits if selected_baits else []
        # 按优先级排序（从右到左，即反向）
        self.sorted_baits = sorted(
            self.selected_baits,
            key=lambda x: self.BAIT_ORDER.index(x) if x in self.BAIT_ORDER else -1,
            reverse=True,
        )
        self.current_bait_index = 0

    def get_current_bait(self):
        """获取当前应该使用的鱼饵"""
        if not self.sorted_baits:
            return None
        return self.sorted_baits[self.current_bait_index]

    def get_next_bait(self):
        """获取下一个鱼饵"""
        if (
            not self.sorted_baits
            or self.current_bait_index >= len(self.sorted_baits) - 1
        ):
            return None
        return self.sorted_baits[self.current_bait_index + 1]

    def switch_to_next_bait(self):
        """切换到下一个鱼饵"""
        if self.current_bait_index < len(self.sorted_baits) - 1:
            self.current_bait_index += 1
            return True
        return False

    def calculate_scroll_count(self, from_bait, to_bait):
        """
        计算从一个鱼饵切换到另一个鱼饵需要滚动的次数

        Args:
            from_bait: 当前鱼饵
            to_bait: 目标鱼饵

        Returns:
            int: 滚动次数（正数向上，负数向下）
        """
        if from_bait not in self.BAIT_ORDER or to_bait not in self.BAIT_ORDER:
            return 0

        from_index = self.BAIT_ORDER.index(from_bait)
        to_index = self.BAIT_ORDER.index(to_bait)

        # 向右切换需要向下滚动（负数）
        return from_index - to_index

    def has_more_baits(self):
        """是否还有更多鱼饵可以切换"""
        return self.current_bait_index < len(self.sorted_baits) - 1

    def set_current_bait(self, bait_name):
        """
        根据当前鱼饵设置起始索引

        Args:
            bait_name: 当前鱼饵名称
        """
        if bait_name in self.sorted_baits:
            self.current_bait_index = self.sorted_baits.index(bait_name)
            return True
        return False
