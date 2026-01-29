"""
状态机服务
负责管理钓鱼流程的状态转换
"""

from enum import Enum


class FishingState(Enum):
    """钓鱼状态枚举"""

    FINDING_PROMPT = "finding_prompt"
    WAITING_FOR_BITE = "waiting_for_bite"
    REELING_IN = "reeling_in"


class FishingStateMachine:
    """钓鱼状态机"""

    def __init__(self):
        self.state = FishingState.FINDING_PROMPT

    def reset(self):
        """重置到初始状态"""
        self.state = FishingState.FINDING_PROMPT

    def transition_to_waiting(self):
        """转换到等待咬钩状态"""
        self.state = FishingState.WAITING_FOR_BITE

    def transition_to_reeling(self):
        """转换到收杆状态"""
        self.state = FishingState.REELING_IN

    def is_finding_prompt(self) -> bool:
        """是否在寻找抛竿提示状态"""
        return self.state == FishingState.FINDING_PROMPT

    def is_waiting_for_bite(self) -> bool:
        """是否在等待咬钩状态"""
        return self.state == FishingState.WAITING_FOR_BITE

    def is_reeling_in(self) -> bool:
        """是否在收杆状态"""
        return self.state == FishingState.REELING_IN
