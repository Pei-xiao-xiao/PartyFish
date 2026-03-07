"""
记录服务
负责处理渔获记录、事件记录和销售记录的保存
"""

import time
import csv
from src.config import cfg
from src.services.record_schema import (
    RECORD_FIELDNAMES,
    build_record_row,
    ensure_record_schema,
)


class RecordService:
    """记录服务类"""

    @staticmethod
    def _detect_weather() -> str:
        """Best-effort weather capture for the current record."""
        try:
            from src.pokedex import pokedex

            return pokedex.detect_current_weather() or ""
        except Exception:
            return ""

    @staticmethod
    def _append_record_row(record_row: dict) -> dict | None:
        """Append one normalized record row to records.csv."""
        try:
            csv_file = cfg.records_file
            file_exists = csv_file.is_file()

            if not csv_file.parent.exists():
                csv_file.parent.mkdir(parents=True)

            if file_exists:
                ensure_record_schema(csv_file)

            encoding = "utf-8" if file_exists else "utf-8-sig"
            with open(csv_file, "a", encoding=encoding, newline="") as f:
                writer = csv.DictWriter(f, fieldnames=RECORD_FIELDNAMES)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(record_row)

            return record_row
        except Exception:
            return None

    @staticmethod
    def _get_inventory_baits(sale_amount: int) -> str:
        """
        获取用户选择的鱼饵组合

        Args:
            sale_amount: 本次卖出的鱼干数量（未使用，保留参数兼容性）

        Returns:
            鱼饵组合字符串，如 "蜂蜜+蘑菇"
        """
        selected_baits = cfg.global_settings.get("selected_baits", [])
        if selected_baits:
            return "+".join(selected_baits)
        return cfg.current_bait

    @staticmethod
    def save_catch_record(
        fish_name: str, quality: str, weight: float, is_new_record: bool
    ) -> dict | None:
        """
        保存渔获记录到 CSV

        Args:
            fish_name: 鱼名
            quality: 品质
            weight: 重量
            is_new_record: 是否新记录

        Returns:
            成功返回记录字典，失败返回 None
        """
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            bait_name = cfg.current_bait
            bait_cost = cfg.BAIT_PRICES.get(bait_name, 0)
            record_row = build_record_row(
                timestamp=timestamp,
                name=fish_name,
                quality=quality,
                weight=str(weight),
                is_new_record="Yes" if is_new_record else "No",
                bait=bait_name,
                bait_cost=str(bait_cost),
                weather=RecordService._detect_weather(),
            )
            return RecordService._append_record_row(record_row)
        except Exception:
            return None

    @staticmethod
    def save_event_record(event_type: str) -> dict | None:
        """
        保存事件记录到 CSV（例如"鱼跑了"）

        Args:
            event_type: 事件类型

        Returns:
            成功返回记录字典，失败返回 None
        """
        if not cfg.global_settings.get("enable_fish_recognition", True):
            return {"skipped": True}

        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            bait_name = cfg.current_bait
            bait_cost = cfg.BAIT_PRICES.get(bait_name, 0)
            record_row = build_record_row(
                timestamp=timestamp,
                name=event_type,
                quality="",
                weight="",
                is_new_record="No",
                bait=bait_name,
                bait_cost=str(bait_cost),
                weather=RecordService._detect_weather(),
            )
            return RecordService._append_record_row(record_row)
        except Exception:
            return None

    @staticmethod
    def save_sale_record(amount: int) -> bool:
        """
        保存销售记录到 CSV

        Args:
            amount: 销售金额

        Returns:
            成功返回 True，失败返回 False
        """
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

            # 统计本次卖出的鱼使用的鱼饵
            bait_used = RecordService._get_inventory_baits(amount)

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
            return False
