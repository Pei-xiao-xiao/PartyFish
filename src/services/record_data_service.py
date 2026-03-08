"""
记录数据服务
负责 CSV 数据加载、记录管理、数据筛选
"""

import csv
from dataclasses import dataclass
from datetime import datetime
from typing import List, Set
from src.config import cfg
from src.services.record_schema import (
    RECORD_FIELDNAMES,
    ensure_record_schema,
    read_record_rows,
)


@dataclass
class FishRecord:
    """鱼类记录数据"""

    timestamp: str
    time_period: str
    weather: str
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
            for row in read_record_rows(data_path):
                record = FishRecord(
                    timestamp=row["Timestamp"],
                    time_period=row["TimePeriod"],
                    weather=row["Weather"],
                    name=row["Name"],
                    quality=row["Quality"],
                    weight=row["Weight"],
                    is_new_record=row["IsNewRecord"] == "Yes",
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

    def filter_by_date_range(
        self, records: List[FishRecord], start_date: str, end_date: str
    ) -> List[FishRecord]:
        """
        按日期范围筛选记录

        Args:
            records: 记录列表
            start_date: 开始日期（格式：YYYY-MM-DD）
            end_date: 结束日期（格式：YYYY-MM-DD）

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
            if start_date <= record_date <= end_date:
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

    def delete_record(
        self, timestamp: str, name: str, quality: str, weight: str
    ) -> bool:
        """
        删除一条钓鱼记录（按时间+名称+品质+重量精确匹配首条）。

        Returns:
            bool: 删除成功返回 True，否则 False
        """
        data_path = cfg.records_file
        if not data_path.exists():
            return False

        try:
            ensure_record_schema(data_path)

            with open(data_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            target_ts = str(timestamp).strip()
            target_name = str(name).strip()
            target_quality = str(quality).strip()
            target_weight = str(weight).strip().replace(" kg", "").replace("kg", "")

            deleted = False
            kept_rows = []
            for row in rows:
                row_ts = str(row.get("Timestamp", "")).strip()
                row_name = str(row.get("Name", "")).strip()
                row_quality = str(row.get("Quality", "")).strip()
                row_weight = (
                    str(row.get("Weight", ""))
                    .strip()
                    .replace(" kg", "")
                    .replace("kg", "")
                )

                is_match = (
                    row_ts == target_ts
                    and row_name == target_name
                    and row_quality == target_quality
                    and row_weight == target_weight
                )
                if not deleted and is_match:
                    deleted = True
                    continue

                kept_rows.append(row)

            if not deleted:
                return False

            with open(data_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=RECORD_FIELDNAMES)
                writer.writeheader()
                writer.writerows(kept_rows)

            return True
        except Exception as e:
            print(f"Error deleting record: {e}")
            return False
