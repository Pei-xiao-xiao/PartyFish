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
        self.runtime_baits = list(self.sorted_baits)
        self.current_bait_index = 0 if self.runtime_baits else -1

    def configure_runtime_sequence(self, current_bait):
        """
        根据当前实际鱼饵生成运行时切换序列。

        规则:
        1. 当前鱼饵未勾选: 先用完当前鱼饵，再切到勾选列表。
        2. 当前鱼饵已勾选: 先继续用当前鱼饵，再按优先级切换剩余勾选鱼饵。
        """
        if not self.sorted_baits:
            self.runtime_baits = []
            self.current_bait_index = -1
            return []

        current_bait = current_bait if current_bait else None

        if current_bait and current_bait in self.sorted_baits:
            remaining = [bait for bait in self.sorted_baits if bait != current_bait]
            self.runtime_baits = [current_bait] + remaining
        elif current_bait:
            self.runtime_baits = [current_bait] + list(self.sorted_baits)
        else:
            self.runtime_baits = list(self.sorted_baits)

        self.current_bait_index = 0 if self.runtime_baits else -1
        return list(self.runtime_baits)

    def get_runtime_sequence(self):
        """获取当前运行时切换序列。"""
        return list(self.runtime_baits)

    def is_selected_bait(self, bait_name):
        """判断鱼饵是否在勾选列表中。"""
        return bait_name in self.sorted_baits

    def get_remaining_baits(self):
        """获取当前鱼饵之后待切换的鱼饵序列。"""
        if not self.runtime_baits or self.current_bait_index < 0:
            return []
        return self.runtime_baits[self.current_bait_index + 1 :]

    def get_current_bait(self):
        """获取当前应该使用的鱼饵"""
        if (
            not self.runtime_baits
            or self.current_bait_index < 0
            or self.current_bait_index >= len(self.runtime_baits)
        ):
            return None
        return self.runtime_baits[self.current_bait_index]

    def get_next_bait(self):
        """获取下一个鱼饵"""
        if (
            not self.runtime_baits
            or self.current_bait_index < 0
            or self.current_bait_index >= len(self.runtime_baits) - 1
        ):
            return None
        return self.runtime_baits[self.current_bait_index + 1]

    def switch_to_next_bait(self):
        """切换到下一个鱼饵"""
        if self.get_next_bait() is not None:
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
        return self.get_next_bait() is not None

    def set_current_bait(self, bait_name):
        """
        根据当前鱼饵设置起始索引

        Args:
            bait_name: 当前鱼饵名称
        """
        if bait_name in self.runtime_baits:
            self.current_bait_index = self.runtime_baits.index(bait_name)
            return True

        if bait_name:
            self.configure_runtime_sequence(bait_name)
            return bait_name in self.runtime_baits

        return False
