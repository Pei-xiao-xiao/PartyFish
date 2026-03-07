import csv
import re
from datetime import datetime
from pathlib import Path

from src.config import cfg
from src.pokedex import pokedex
from src.services.record_schema import (
    RECORD_FIELDNAMES,
    RECORD_REQUIRED_FIELDS,
    build_record_row,
    ensure_record_schema,
    normalize_record_row,
    read_record_rows,
)


class RecordManager:
    """记录管理模块，负责导入导出钓鱼记录"""

    @staticmethod
    def _make_record_key(record: dict) -> tuple[str, str, str, str]:
        return (
            record.get("Timestamp", "").strip(),
            record.get("Name", "").strip(),
            record.get("Quality", "").strip(),
            record.get("Weight", "").strip(),
        )

    @staticmethod
    def _load_existing_record_keys(
        records_file: Path,
    ) -> set[tuple[str, str, str, str]]:
        return {
            RecordManager._make_record_key(record)
            for record in read_record_rows(records_file)
        }

    @staticmethod
    def _update_pokedex_from_record(record: dict) -> tuple[int, bool]:
        """Update collection status in memory from one imported record."""
        name = record.get("Name", "").strip()
        quality = record.get("Quality", "").strip()
        weight = record.get("Weight", "").strip()

        if not name or not quality:
            return 0, False

        new_collected = 0 if pokedex.is_collected(name, quality) else 1
        try:
            weight_float = float(weight.replace("g", "").replace("kg", "").strip())
        except ValueError:
            weight_float = 0

        if name not in pokedex._collection:
            pokedex._collection[name] = {}

        current = pokedex._collection[name].get(quality)
        if current is None or weight_float > current:
            pokedex._collection[name][quality] = weight_float
            return new_collected, True

        return new_collected, False

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

            records = read_record_rows(records_file)

            if format_type == "csv":
                with open(file_path, "w", encoding="utf-8-sig", newline="") as dst:
                    writer = csv.DictWriter(dst, fieldnames=RECORD_FIELDNAMES)
                    writer.writeheader()
                    writer.writerows(records)

            elif format_type == "txt":
                # 保持旧版 TXT 导出格式不变，确保历史导入链路可用。
                with open(file_path, "w", encoding="utf-8") as dst:
                    for record in records:
                        formatted = (
                            f"|{record['Timestamp']}|{record['Name']}|"
                            f"{record['Quality']}|{record['Weight']}|"
                        )
                        dst.write(formatted + "\n")
            else:
                return False

            return True
        except Exception as e:
            print(f"导出记录失败: {e}")
            return False

    @staticmethod
    def import_records(file_path: Path, progress_callback=None) -> tuple[bool, str]:
        """
        从指定文件导入记录

        Args:
            file_path: 导入文件路径
            progress_callback: 进度回调函数 callback(current, total)

        Returns:
            tuple[bool, str]: (导入是否成功, 错误信息或成功信息)
        """
        try:
            records_file = cfg.records_file
            file_extension = file_path.suffix.lower()
            file_exists = records_file.exists()

            if file_exists:
                ensure_record_schema(records_file)

            existing_records = (
                RecordManager._load_existing_record_keys(records_file)
                if file_exists
                else set()
            )

            if file_extension == ".csv":
                return RecordManager._import_csv_records(
                    file_path,
                    records_file,
                    file_exists,
                    existing_records,
                    progress_callback,
                )

            if file_extension == ".txt":
                return RecordManager._import_txt_records(
                    file_path,
                    records_file,
                    file_exists,
                    existing_records,
                    progress_callback,
                )

            return False, f"不支持的文件格式: {file_extension}"
        except Exception as e:
            return False, f"导入记录失败: {str(e)}"

    @staticmethod
    def _import_csv_records(
        file_path: Path,
        records_file: Path,
        file_exists: bool,
        existing_records: set[tuple[str, str, str, str]],
        progress_callback=None,
    ) -> tuple[bool, str]:
        records_file.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            source_fieldnames = reader.fieldnames or []
            if any(field not in source_fieldnames for field in RECORD_REQUIRED_FIELDS):
                return False, f"CSV文件格式不正确，缺少必要字段: {source_fieldnames}"

        with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
            total_rows = sum(1 for _ in csv.DictReader(f))

        encoding = "utf-8" if file_exists else "utf-8-sig"
        with open(file_path, "r", encoding="utf-8-sig", newline="") as src, open(
            records_file, "a", encoding=encoding, newline=""
        ) as dst:
            reader = csv.DictReader(src)
            writer = csv.DictWriter(dst, fieldnames=RECORD_FIELDNAMES)

            if not file_exists:
                writer.writeheader()

            count = 0
            skipped = 0
            processed = 0
            new_collected = 0
            collection_changed = False

            for row in reader:
                processed += 1
                if progress_callback and processed % 500 == 0:
                    progress_callback(processed, total_rows)

                record = normalize_record_row(row)
                key = RecordManager._make_record_key(record)

                if key in existing_records:
                    skipped += 1
                    continue

                writer.writerow(record)
                existing_records.add(key)
                count += 1

                collected_delta, changed = RecordManager._update_pokedex_from_record(
                    record
                )
                new_collected += collected_delta
                collection_changed = collection_changed or changed

        if count == 0:
            return False, "没有找到可导入的记录"

        if collection_changed:
            pokedex._save_collection()
            pokedex.data_changed.emit()

        msg = f"成功导入 {count} 条记录"
        if skipped > 0:
            msg += f"，跳过 {skipped} 条重复记录"
        if new_collected > 0:
            msg += f"，图鉴新增 {new_collected} 条"
        return True, msg

    @staticmethod
    def _import_txt_records(
        file_path: Path,
        records_file: Path,
        file_exists: bool,
        existing_records: set[tuple[str, str, str, str]],
        progress_callback=None,
    ) -> tuple[bool, str]:
        records_file.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "r", encoding="utf-8") as f:
            total_lines = sum(1 for _ in f)

        encoding = "utf-8" if file_exists else "utf-8-sig"
        with open(file_path, "r", encoding="utf-8") as src, open(
            records_file, "a", encoding=encoding, newline=""
        ) as dst:
            writer = csv.DictWriter(dst, fieldnames=RECORD_FIELDNAMES)

            if not file_exists:
                writer.writeheader()

            count = 0
            skipped = 0
            new_collected = 0
            collection_changed = False

            for line_num, line in enumerate(src, 1):
                if progress_callback and line_num % 500 == 0:
                    progress_callback(line_num, total_lines)

                line = line.strip()
                if not line:
                    continue

                record = RecordManager._parse_txt_record(line)
                if not record:
                    return False, f"TXT文件格式不正确，第{line_num}行: {line}"

                key = RecordManager._make_record_key(record)
                if key in existing_records:
                    skipped += 1
                    continue

                writer.writerow(record)
                existing_records.add(key)
                count += 1

                collected_delta, changed = RecordManager._update_pokedex_from_record(
                    record
                )
                new_collected += collected_delta
                collection_changed = collection_changed or changed

        if count == 0:
            return False, "没有找到可导入的记录"

        if collection_changed:
            pokedex._save_collection()
            pokedex.data_changed.emit()

        msg = f"成功导入 {count} 条记录"
        if skipped > 0:
            msg += f"，跳过 {skipped} 条重复记录"
        if new_collected > 0:
            msg += f"，图鉴新增 {new_collected} 条"
        return True, msg

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

            return build_record_row(
                timestamp=timestamp,
                name=name,
                quality=quality,
                weight=weight,
                is_new_record="No",
            )
        except Exception as e:
            print(f"解析记录失败: {line}, 错误: {e}")
            return None


# 实例化单例
record_manager = RecordManager()
