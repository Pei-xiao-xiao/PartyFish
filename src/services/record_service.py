"""
记录服务
负责处理渔获记录、事件记录和销售记录的保存
"""

import time
import csv
from pathlib import Path
from src.config import cfg


class RecordService:
    """记录服务类"""

    @staticmethod
    def save_catch_record(
        fish_name: str, quality: str, weight: float, is_new_record: bool
    ) -> bool:
        """
        保存渔获记录到 CSV

        Args:
            fish_name: 鱼名
            quality: 品质
            weight: 重量
            is_new_record: 是否新记录

        Returns:
            成功返回 True，失败返回 False
        """
        try:
            csv_file = cfg.records_file
            file_exists = csv_file.is_file()

            if not csv_file.parent.exists():
                csv_file.parent.mkdir(parents=True)

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            bait_name = cfg.current_bait
            bait_cost = cfg.BAIT_PRICES.get(bait_name, 0)

            encoding = "utf-8-sig" if not file_exists else "utf-8"
            with open(csv_file, "a", encoding=encoding) as f:
                if not file_exists:
                    f.write("Timestamp,Name,Quality,Weight,IsNewRecord,Bait,BaitCost\n")

                is_new_record_str = "Yes" if is_new_record else "No"
                f.write(
                    f"{timestamp},{fish_name},{quality},{weight},"
                    f"{is_new_record_str},{bait_name},{bait_cost}\n"
                )

            return True
        except Exception as e:
            return False

    @staticmethod
    def save_event_record(event_type: str) -> bool:
        """
        保存事件记录到 CSV（例如"鱼跑了"）

        Args:
            event_type: 事件类型

        Returns:
            成功返回 True，失败返回 False
        """
        if not cfg.global_settings.get("enable_fish_recognition", True):
            return True

        try:
            csv_file = cfg.records_file
            file_exists = csv_file.is_file()

            if not csv_file.parent.exists():
                csv_file.parent.mkdir(parents=True)

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            bait_name = cfg.current_bait
            bait_cost = cfg.BAIT_PRICES.get(bait_name, 0)

            encoding = "utf-8-sig" if not file_exists else "utf-8"
            with open(csv_file, "a", encoding=encoding) as f:
                if not file_exists:
                    f.write("Timestamp,Name,Quality,Weight,IsNewRecord,Bait,BaitCost\n")
                f.write(f"{timestamp},{event_type},,,No,{bait_name},{bait_cost}\n")

            return True
        except Exception as e:
            return False

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
            bait_used = cfg.current_bait

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
