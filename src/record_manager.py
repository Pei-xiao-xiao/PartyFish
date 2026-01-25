import csv
import re
from pathlib import Path
from datetime import datetime
from src.config import cfg


class RecordManager:
    """记录管理模块，负责导入导出钓鱼记录"""

    @staticmethod
    def export_records(file_path: Path, format_type: str) -> bool:
        """
        导出记录到指定文件

        Args:
            file_path: 导出文件路径
            format_type: 导出格式，可选 'csv' 或 'txt'

        Returns:
            bool: 导出是否成功
        """
        try:
            records_file = cfg.records_file
            if not records_file.exists():
                return False

            if format_type == "csv":
                # 流式导出为CSV格式
                with open(records_file, "r", encoding="utf-8-sig") as src, open(
                    file_path, "w", encoding="utf-8-sig", newline=""
                ) as dst:
                    reader = csv.DictReader(src)
                    writer = csv.DictWriter(dst, fieldnames=reader.fieldnames)
                    writer.writeheader()
                    writer.writerows(reader)

            elif format_type == "txt":
                # 流式导出为 |时间|鱼名|品质|重量 格式
                with open(records_file, "r", encoding="utf-8-sig") as src, open(
                    file_path, "w", encoding="utf-8"
                ) as dst:
                    reader = csv.DictReader(src)
                    for record in reader:
                        formatted = f"|{record['Timestamp']}|{record['Name']}|{record['Quality']}|{record['Weight']}|"
                        dst.write(formatted + "\n")

            return True
        except Exception as e:
            print(f"导出记录失败: {e}")
            return False

    @staticmethod
    def import_records(file_path: Path) -> tuple[bool, str]:
        """
        从指定文件导入记录

        Args:
            file_path: 导入文件路径

        Returns:
            tuple[bool, str]: (导入是否成功, 错误信息或成功信息)
        """
        try:
            records_file = cfg.records_file
            file_extension = file_path.suffix.lower()

            if file_extension == ".csv":
                # 检查文件是否存在（在打开前检查）
                file_exists = records_file.exists()

                # 读取现有记录的唯一标识
                existing_records = set()
                if file_exists:
                    with open(records_file, "r", encoding="utf-8-sig") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            key = (
                                row.get("Timestamp", "").strip(),
                                row.get("Name", "").strip(),
                                row.get("Quality", "").strip(),
                                row.get("Weight", "").strip(),
                            )
                            existing_records.add(key)

                # 从CSV文件导入并流式写入
                with open(file_path, "r", encoding="utf-8-sig") as src, open(
                    records_file, "a", encoding="utf-8-sig", newline=""
                ) as dst:
                    reader = csv.DictReader(src)
                    fieldnames = [
                        "Timestamp",
                        "Name",
                        "Quality",
                        "Weight",
                        "IsNewRecord",
                        "Bait",
                        "BaitCost",
                    ]
                    writer = csv.DictWriter(dst, fieldnames=fieldnames)

                    # 如果文件不存在，写入表头
                    if not file_exists:
                        writer.writeheader()

                    count = 0
                    skipped = 0
                    for row in reader:
                        # 验证必要字段
                        if not all(
                            field in row
                            for field in ["Timestamp", "Name", "Quality", "Weight"]
                        ):
                            return False, f"CSV文件格式不正确，缺少必要字段: {row}"

                        timestamp = row.get(
                            "Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ).strip()
                        name = row.get("Name", "").strip()
                        quality = row.get("Quality", "").strip()
                        weight = row.get("Weight", "").strip()
                        key = (timestamp, name, quality, weight)

                        # 跳过重复记录
                        if key in existing_records:
                            skipped += 1
                            continue

                        # 写入记录
                        writer.writerow(
                            {
                                "Timestamp": timestamp,
                                "Name": name,
                                "Quality": quality,
                                "Weight": weight,
                                "IsNewRecord": row.get("IsNewRecord", "No"),
                                "Bait": row.get("Bait", "蔓越莓"),
                                "BaitCost": row.get("BaitCost", "1"),
                            }
                        )
                        existing_records.add(key)
                        count += 1

                    if count == 0:
                        return False, "没有找到可导入的记录"

                    msg = f"成功导入 {count} 条记录"
                    if skipped > 0:
                        msg += f"，跳过 {skipped} 条重复记录"
                    return True, msg

            elif file_extension == ".txt":
                # 检查文件是否存在（在打开前检查）
                file_exists = records_file.exists()

                # 读取现有记录的唯一标识
                existing_records = set()
                if file_exists:
                    with open(records_file, "r", encoding="utf-8-sig") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            key = (
                                row.get("Timestamp", "").strip(),
                                row.get("Name", "").strip(),
                                row.get("Quality", "").strip(),
                                row.get("Weight", "").strip(),
                            )
                            existing_records.add(key)

                # 从TXT文件导入并流式写入
                with open(file_path, "r", encoding="utf-8") as src, open(
                    records_file, "a", encoding="utf-8-sig", newline=""
                ) as dst:
                    fieldnames = [
                        "Timestamp",
                        "Name",
                        "Quality",
                        "Weight",
                        "IsNewRecord",
                        "Bait",
                        "BaitCost",
                    ]
                    writer = csv.DictWriter(dst, fieldnames=fieldnames)

                    # 如果文件不存在，写入表头
                    if not file_exists:
                        writer.writeheader()

                    count = 0
                    skipped = 0
                    for line_num, line in enumerate(src, 1):
                        line = line.strip()
                        if not line:
                            continue

                        # 解析TXT格式记录
                        record = RecordManager._parse_txt_record(line)
                        if record:
                            key = (
                                record.get("Timestamp", "").strip(),
                                record.get("Name", "").strip(),
                                record.get("Quality", "").strip(),
                                record.get("Weight", "").strip(),
                            )

                            # 跳过重复记录
                            if key in existing_records:
                                skipped += 1
                                continue

                            writer.writerow(record)
                            existing_records.add(key)
                            count += 1
                        else:
                            return False, f"TXT文件格式不正确，第{line_num}行: {line}"

                    if count == 0:
                        return False, "没有找到可导入的记录"

                    msg = f"成功导入 {count} 条记录"
                    if skipped > 0:
                        msg += f"，跳过 {skipped} 条重复记录"
                    return True, msg

            else:
                return False, f"不支持的文件格式: {file_extension}"

        except Exception as e:
            return False, f"导入记录失败: {str(e)}"

    @staticmethod
    def _parse_txt_record(line: str) -> dict | None:
        """
        解析TXT格式的记录行
        支持格式: |时间|鱼名|品质|重量|

        Args:
            line: 记录行

        Returns:
            dict or None: 解析后的记录字典，解析失败返回None
        """
        try:
            line = line.strip()

            timestamp = name = quality = weight = None

            if line.startswith("|") and line.endswith("|"):
                content = line[1:-1]
                parts = content.split("|")
                if len(parts) != 4:
                    return None
                timestamp, name, quality, weight = parts
            else:
                parts = line.split("|")
                if len(parts) < 3:
                    return None

                if len(parts) == 5:
                    timestamp, name, quality, weight = (
                        parts[1],
                        parts[2],
                        parts[3],
                        parts[4],
                    )
                elif len(parts) == 4:
                    try:
                        datetime.strptime(parts[1], "%Y-%m-%d %H:%M:%S")
                        timestamp, name, quality, weight = (
                            parts[1],
                            parts[2],
                            parts[0],
                            parts[3],
                        )
                    except ValueError:
                        try:
                            datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S")
                            timestamp, name, quality, weight = parts
                        except ValueError:
                            return None
                elif len(parts) == 3:
                    try:
                        datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S")
                        timestamp, name, weight = parts
                        quality = "标准"
                    except ValueError:
                        return None
                else:
                    return None

            timestamp = timestamp.strip()
            name = name.strip()
            quality = quality.strip()
            weight = weight.strip()

            if " " not in timestamp:
                fixed_timestamp = re.sub(
                    r"(\d{4}-\d{2}-\d{2})(\d{2}:\d{2}:\d{2})", r"\1 \2", timestamp
                )
                datetime.strptime(fixed_timestamp, "%Y-%m-%d %H:%M:%S")
                timestamp = fixed_timestamp
            else:
                datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")

            if weight.endswith("kg"):
                weight = weight[:-2].strip()

            return {
                "Timestamp": timestamp,
                "Name": name,
                "Quality": quality,
                "Weight": weight,
                "IsNewRecord": "No",
                "Bait": "蔓越莓",
                "BaitCost": "1",
            }
        except Exception as e:
            print(f"解析记录失败: {line}, 错误: {e}")
            return None


# 实例化单例
record_manager = RecordManager()
