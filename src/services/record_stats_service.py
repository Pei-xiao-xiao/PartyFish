"""
记录统计服务
负责统计计算、数据聚合
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

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

    @staticmethod
    def _normalize_record_date(timestamp: str) -> str:
        date_str = str(timestamp).split(" ")[0].strip()
        if "/" in date_str:
            parts = date_str.split("/")
            if len(parts) == 3:
                return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
        return date_str

    def calculate_stats(
        self, display_records: List[FishRecord], all_records: List[FishRecord]
    ) -> RecordStats:
        """计算统计数据。"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_records = [
            r
            for r in all_records
            if self._normalize_record_date(r.timestamp) == today_str
        ]

        total_count = len(display_records)
        today_count = len(today_records)
        unhook_count = sum(1 for r in display_records if r.name == "鱼跑了")

        qualities = [r.quality for r in display_records]
        processed_qualities = ["传奇" if q == "传说" else q for q in qualities]
        quality_counts = dict(Counter(processed_qualities))
        legendary_count = qualities.count("传奇") + qualities.count("传说")

        return RecordStats(
            total_count=total_count,
            today_count=today_count,
            legendary_count=legendary_count,
            unhook_count=unhook_count,
            quality_counts=quality_counts,
        )
