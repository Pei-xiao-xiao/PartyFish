"""
利润分析服务
负责销售数据加载、成本计算、利润计算、数据聚合
"""

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
from src.config import cfg


@dataclass
class TodayStats:
    """今日统计数据"""

    total_sales: int
    total_cost: int
    net_profit: int
    remaining_limit: int
    sales_records: List[List[str]]
    limit_reached_time: Optional[datetime]


@dataclass
class HistoryStats:
    """历史统计数据"""

    daily_sales: Dict[str, int]
    daily_cost: Dict[str, int]
    total_income: int
    total_cost: int
    total_net: int
    avg_income: int
    max_income: int


class ProfitAnalysisService:
    """利润分析服务类"""

    @staticmethod
    def _normalize_date_text(date_text: str) -> str:
        normalized = str(date_text).strip()
        if "/" in normalized:
            parts = normalized.split("/")
            if len(parts) == 3:
                normalized = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
        return normalized

    @staticmethod
    def _parse_timestamp(timestamp: str) -> Optional[datetime]:
        normalized = str(timestamp).strip().replace("/", "-")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(normalized, fmt)
            except ValueError:
                continue
        return None

    def get_available_history_dates(self) -> Set[str]:
        available_dates: Set[str] = set()

        sales_path = cfg.sales_file
        if sales_path.exists():
            try:
                with open(sales_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if not row:
                            continue
                        parsed = self._parse_timestamp(row[0])
                        if parsed:
                            available_dates.add(parsed.strftime("%Y-%m-%d"))
            except Exception:
                pass

        records_path = cfg.records_file
        if records_path.exists():
            try:
                with open(records_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if not row:
                            continue
                        parsed = self._parse_timestamp(row.get("Timestamp", ""))
                        if parsed:
                            available_dates.add(parsed.strftime("%Y-%m-%d"))
            except Exception:
                pass

        return available_dates

    def get_current_cycle_start_time(self) -> datetime:
        """
        计算当前统计周期的起始时间
        CN: 当日 00:00
        Global: 当日 12:00 (若当前 >= 12:00) 或 昨日 12:00 (若当前 < 12:00)
        """
        region = cfg.get_current_account_server_region()
        now = datetime.now()

        if region == "CN":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            noon_today = now.replace(hour=12, minute=0, second=0, microsecond=0)
            if now >= noon_today:
                return noon_today
            else:
                return noon_today - timedelta(days=1)

    def load_today_stats(self, start_time: datetime) -> TodayStats:
        """
        加载今日统计数据

        Args:
            start_time: 统计周期起始时间

        Returns:
            TodayStats: 今日统计数据
        """
        sales_records = []
        total_sales = 0
        limit_reached_time = None

        sales_path = cfg.sales_file

        if sales_path.exists():
            try:
                with open(sales_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    rows = list(reader)

                    current_sum = 0
                    for row in rows:
                        if not row:
                            continue
                        ts_str = row[0]
                        try:
                            row_dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")

                            if row_dt >= start_time:
                                amount = int(row[1])
                                sales_records.append(row)
                                total_sales += amount
                                current_sum += amount

                                if current_sum >= 900 and limit_reached_time is None:
                                    limit_reached_time = row_dt
                        except ValueError:
                            continue
            except Exception as e:
                print(f"Error loading sales records: {e}")

        # 加载成本数据
        total_cost = 0
        records_path = cfg.records_file

        if records_path.exists():
            try:
                with open(records_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if not row:
                            continue
                        ts_str = row.get("Timestamp", "")
                        try:
                            row_dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                            if row_dt >= start_time:
                                try:
                                    total_cost += int(row.get("BaitCost", "0") or 0)
                                except ValueError:
                                    pass
                        except ValueError:
                            pass
            except Exception as e:
                print(f"Error loading fish records: {e}")

        net_profit = total_sales - total_cost
        remaining_limit = 900 - total_sales

        return TodayStats(
            total_sales=total_sales,
            total_cost=total_cost,
            net_profit=net_profit,
            remaining_limit=remaining_limit,
            sales_records=sales_records,
            limit_reached_time=limit_reached_time,
        )

    def load_history_stats(
        self,
        days: Optional[int] = 30,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> HistoryStats:
        """
        加载历史统计数据

        Args:
            days: 统计天数

        Returns:
            HistoryStats: 历史统计数据
        """
        daily_sales = defaultdict(int)
        daily_cost = defaultdict(int)
        cutoff_date = (
            datetime.now() - timedelta(days=days) if days is not None else None
        )
        normalized_start = self._normalize_date_text(start_date) if start_date else None
        normalized_end = self._normalize_date_text(end_date) if end_date else None

        # 加载销售历史
        sales_path = cfg.sales_file
        if sales_path.exists():
            try:
                with open(sales_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if not row:
                            continue
                        ts_str = row[0]
                        amount = int(row[1])
                        try:
                            dt = self._parse_timestamp(ts_str)
                            if not dt:
                                continue
                            date_str = dt.strftime("%Y-%m-%d")
                            in_range = True
                            if normalized_start and normalized_end:
                                in_range = (
                                    normalized_start <= date_str <= normalized_end
                                )
                            elif cutoff_date is not None:
                                in_range = dt >= cutoff_date
                            if in_range:
                                daily_sales[date_str] += amount
                        except ValueError:
                            pass
            except Exception:
                pass

        # 加载成本历史
        records_path = cfg.records_file
        if records_path.exists():
            try:
                with open(records_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if not row:
                            continue
                        ts_str = row.get("Timestamp", "")
                        try:
                            dt = self._parse_timestamp(ts_str)
                            if not dt:
                                continue
                            date_str = dt.strftime("%Y-%m-%d")
                            in_range = True
                            if normalized_start and normalized_end:
                                in_range = (
                                    normalized_start <= date_str <= normalized_end
                                )
                            elif cutoff_date is not None:
                                in_range = dt >= cutoff_date
                            if in_range:
                                daily_cost[date_str] += int(
                                    row.get("BaitCost", "0") or 0
                                )
                        except ValueError:
                            pass
            except Exception:
                pass

        # 计算统计数据
        all_dates = sorted(set(daily_sales) | set(daily_cost))
        normalized_daily_sales = {date: daily_sales.get(date, 0) for date in all_dates}
        normalized_daily_cost = {date: daily_cost.get(date, 0) for date in all_dates}

        total_income = sum(normalized_daily_sales.values())
        total_cost = sum(normalized_daily_cost.values())
        total_net = total_income - total_cost
        days_count = len(all_dates)
        avg_income = total_income // days_count if days_count > 0 else 0
        max_income = max(normalized_daily_sales.values()) if days_count > 0 else 0

        return HistoryStats(
            daily_sales=normalized_daily_sales,
            daily_cost=normalized_daily_cost,
            total_income=total_income,
            total_cost=total_cost,
            total_net=total_net,
            avg_income=avg_income,
            max_income=max_income,
        )

    def write_sale_record(self, amount: int, bait_used: str) -> bool:
        """
        写入销售记录

        Args:
            amount: 销售金额
            bait_used: 使用的鱼饵

        Returns:
            bool: 是否成功
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sales_path = cfg.sales_file

            if not sales_path.parent.exists():
                sales_path.parent.mkdir(parents=True)

            file_exists = sales_path.exists()

            with open(sales_path, "a", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Timestamp", "Amount", "BaitUsed"])
                writer.writerow([timestamp, amount, bait_used])
            return True
        except Exception as e:
            print(f"Failed to write sales record: {e}")
            return False

    def delete_sale_record(self, timestamp: str) -> bool:
        """
        删除销售记录

        Args:
            timestamp: 时间戳

        Returns:
            bool: 是否成功
        """
        sales_path = cfg.sales_file
        if not sales_path.exists():
            return False

        try:
            new_lines = []
            with open(sales_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header:
                    new_lines.append(header)
                for row in reader:
                    if row and row[0] == timestamp:
                        continue
                    new_lines.append(row)

            with open(sales_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(new_lines)
            return True
        except Exception as e:
            print(f"Failed to delete sales record: {e}")
            return False

    def update_sale_record(self, timestamp: str, new_amount: str) -> bool:
        """
        更新销售记录

        Args:
            timestamp: 时间戳
            new_amount: 新金额

        Returns:
            bool: 是否成功
        """
        if not new_amount.isdigit():
            return False

        sales_path = cfg.sales_file
        if not sales_path.exists():
            return False

        try:
            new_lines = []
            with open(sales_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header:
                    new_lines.append(header)
                for row in reader:
                    if row and row[0] == timestamp:
                        row[1] = new_amount
                    new_lines.append(row)

            with open(sales_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(new_lines)
            return True
        except Exception as e:
            print(f"Failed to update sales record: {e}")
            return False
