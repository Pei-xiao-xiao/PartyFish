"""
记录字段兼容辅助
统一处理 records.csv 的新旧字段、默认值和时段推导。
"""

import csv
from datetime import datetime
from pathlib import Path


RECORD_FIELDNAMES = [
    "Timestamp",
    "Name",
    "Quality",
    "Weight",
    "IsNewRecord",
    "Bait",
    "BaitCost",
    "TimePeriod",
    "Weather",
]
RECORD_REQUIRED_FIELDS = ("Timestamp", "Name", "Quality", "Weight")
DEFAULT_BAIT = "蔓越莓"
DEFAULT_BAIT_COST = "1"


def parse_record_timestamp(timestamp: str) -> datetime | None:
    """Parse supported record timestamps from old and current formats."""
    normalized = str(timestamp).strip()
    if not normalized:
        return None

    normalized = normalized.replace("/", "-")

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue

    try:
        date_part, time_part = normalized.split()
        year, month, day = [int(part) for part in date_part.split("-")]
        hour, minute, second = [int(part) for part in time_part.split(":")]
        return datetime(year, month, day, hour, minute, second)
    except (TypeError, ValueError):
        return None


def infer_time_period_from_timestamp(timestamp: str) -> str:
    """Infer game time period from the saved timestamp minute."""
    dt = parse_record_timestamp(timestamp)
    if dt is None:
        return ""

    minute = dt.minute
    if 0 <= minute < 10:
        return "凌晨"
    if 10 <= minute < 20:
        return "清晨"
    if 20 <= minute < 30:
        return "上午"
    if 30 <= minute < 40:
        return "下午"
    if 40 <= minute < 50:
        return "黄昏"
    return "深夜"


def build_record_row(
    timestamp: str,
    name: str,
    quality: str,
    weight: str,
    is_new_record: str = "No",
    bait: str = DEFAULT_BAIT,
    bait_cost: str = DEFAULT_BAIT_COST,
    time_period: str = "",
    weather: str = "",
) -> dict:
    """Build a normalized record row matching the current schema."""
    return normalize_record_row(
        {
            "Timestamp": timestamp,
            "Name": name,
            "Quality": quality,
            "Weight": weight,
            "IsNewRecord": is_new_record,
            "Bait": bait,
            "BaitCost": bait_cost,
            "TimePeriod": time_period,
            "Weather": weather,
        }
    )


def normalize_record_row(row: dict) -> dict:
    """Normalize a record row from any supported schema into the current one."""
    timestamp = str(row.get("Timestamp", "")).strip()
    return {
        "Timestamp": timestamp,
        "Name": str(row.get("Name", "")).strip(),
        "Quality": str(row.get("Quality", "")).strip(),
        "Weight": str(row.get("Weight", "")).strip(),
        "IsNewRecord": str(row.get("IsNewRecord", "No")).strip() or "No",
        "Bait": str(row.get("Bait", DEFAULT_BAIT)).strip() or DEFAULT_BAIT,
        "BaitCost": str(row.get("BaitCost", DEFAULT_BAIT_COST)).strip()
        or DEFAULT_BAIT_COST,
        "TimePeriod": str(row.get("TimePeriod", "")).strip()
        or infer_time_period_from_timestamp(timestamp),
        "Weather": str(row.get("Weather", "")).strip(),
    }


def read_record_rows(records_file: Path) -> list[dict]:
    """Read and normalize all rows from records.csv."""
    if not records_file.exists():
        return []

    with open(records_file, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return []

        rows = []
        for row in reader:
            if not row:
                continue

            has_content = False
            for value in row.values():
                if isinstance(value, list):
                    if any(str(item).strip() for item in value):
                        has_content = True
                        break
                elif str(value or "").strip():
                    has_content = True
                    break

            if not has_content:
                continue
            rows.append(normalize_record_row(row))
        return rows


def read_record_fieldnames(records_file: Path) -> list[str]:
    """Read the current header row from records.csv."""
    if not records_file.exists():
        return []

    with open(records_file, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        return next(reader, [])


def ensure_record_schema(records_file: Path) -> bool:
    """
    Upgrade legacy records.csv headers in place.
    Old rows are preserved and backfilled with inferred time period values.
    """
    if not records_file.exists():
        return True

    fieldnames = read_record_fieldnames(records_file)
    if fieldnames == RECORD_FIELDNAMES:
        return True

    rows = read_record_rows(records_file)
    with open(records_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RECORD_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    return True
