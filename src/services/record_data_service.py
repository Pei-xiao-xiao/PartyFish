"""
记录数据服务
负责 CSV 数据加载、记录管理、数据筛选
"""

import csv
from dataclasses import dataclass
from datetime import datetime
from typing import List, Set
from pathlib import Path
from src.config import cfg


@dataclass
class FishRecord:
    """鱼类记录数据"""

    timestamp: str
    name: str
    quality: str
    weight: str
    is_new_record: bool = False


class RecordDataService:
    """记录数据服务类"""

    def load_records(self) -> List[FishRecord]:
        """
        从 CSV 加载所有记录

        Returns:
            List[FishRecord]: 记录列表（按时间倒序）
        """
        records = []
        data_path = cfg.records_file

        if not data_path.exists():
            return records

        try:
            with open(data_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                next(reader, None)  # 跳过表头

                for row in reader:
                    if len(row) >= 4:
                        is_new = False
                        if len(row) >= 5:
                            is_new = row[4] == "Yes"

                        record = FishRecord(
                            timestamp=row[0],
                            name=row[1],
                            quality=row[2],
                            weight=row[3],
                            is_new_record=is_new,
                        )
                        records.append(record)
        except Exception as e:
            print(f"Error loading records: {e}")

        # 倒序排列（最新的在前）
        records.reverse()
        return records

    def filter_by_date(
        self, records: List[FishRecord], date_str: str
    ) -> List[FishRecord]:
        """
        按日期筛选记录

        Args:
            records: 记录列表
            date_str: 日期字符串（格式：YYYY-MM-DD）

        Returns:
            List[FishRecord]: 筛选后的记录
        """
        filtered = []
        for r in records:
            record_date = r.timestamp.split(" ")[0]
            # 标准化日期格式：支持 YYYY/MM/DD, YYYY/M/D, YYYY-MM-DD
            if "/" in record_date:
                parts = record_date.split("/")
                if len(parts) == 3:
                    record_date = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
            if record_date == date_str:
                filtered.append(r)
        return filtered

    def filter_by_today(self, records: List[FishRecord]) -> List[FishRecord]:
        """
        筛选今日记录

        Args:
            records: 记录列表

        Returns:
            List[FishRecord]: 今日记录
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        return self.filter_by_date(records, today_str)

    def get_available_dates(self, records: List[FishRecord]) -> Set[str]:
        """
        获取所有有记录的日期

        Args:
            records: 记录列表

        Returns:
            Set[str]: 日期集合（格式：YYYY-MM-DD）
        """
        dates = set()
        for record in records:
            date_str = record.timestamp.split(" ")[0]
            # 标准化日期格式：支持 YYYY/MM/DD, YYYY/M/D, YYYY-MM-DD
            if "/" in date_str:
                parts = date_str.split("/")
                if len(parts) == 3:
                    date_str = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
            dates.add(date_str)
        return dates
