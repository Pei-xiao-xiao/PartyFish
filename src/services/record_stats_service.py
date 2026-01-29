"""
记录统计服务
负责统计计算、数据聚合
"""

from dataclasses import dataclass
from typing import Dict, List
from collections import Counter
from datetime import datetime
from src.services.record_data_service import FishRecord


@dataclass
class RecordStats:
    """记录统计数据"""

    total_count: int
    today_count: int
    legendary_count: int
    unhook_count: int
    quality_counts: Dict[str, int]


class RecordStatsService:
    """记录统计服务类"""

    def calculate_stats(
        self, display_records: List[FishRecord], all_records: List[FishRecord]
    ) -> RecordStats:
        """
        计算统计数据

        Args:
            display_records: 当前显示的记录
            all_records: 所有记录

        Returns:
            RecordStats: 统计数据
        """
        # 今日记录
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_records = [r for r in all_records if r.timestamp.startswith(today_str)]

        # 统计数量
        total_count = len(display_records)
        today_count = len(today_records)

        # 脱钩数量
        unhook_count = sum(1 for r in display_records if r.name == "鱼跑了")

        # 品质统计
        qualities = [r.quality for r in display_records]
        # 将传说转换为传奇
        processed_qualities = ["传奇" if q == "传说" else q for q in qualities]
        quality_counts = dict(Counter(processed_qualities))

        # 传奇数量（兼容传说和传奇）
        legendary_count = qualities.count("传奇") + qualities.count("传说")

        return RecordStats(
            total_count=total_count,
            today_count=today_count,
            legendary_count=legendary_count,
            unhook_count=unhook_count,
            quality_counts=quality_counts,
        )
