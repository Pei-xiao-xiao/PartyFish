import csv

from src.services.record_schema import (
    RECORD_FIELDNAMES,
    ensure_record_schema,
    infer_time_period_from_timestamp,
    normalize_record_row,
    parse_record_timestamp,
)


def test_parse_record_timestamp_supports_legacy_formats():
    assert parse_record_timestamp("2026-03-13 12:34:56") is not None
    assert parse_record_timestamp("2026-03-13 12:34") is not None
    assert parse_record_timestamp("2026/03/13 12:34:56") is not None
    assert parse_record_timestamp("") is None


def test_infer_time_period_from_timestamp_uses_minute_ranges():
    assert infer_time_period_from_timestamp("2026-03-13 12:05:00") == "凌晨"
    assert infer_time_period_from_timestamp("2026-03-13 12:15:00") == "清晨"
    assert infer_time_period_from_timestamp("2026-03-13 12:25:00") == "上午"
    assert infer_time_period_from_timestamp("2026-03-13 12:35:00") == "下午"
    assert infer_time_period_from_timestamp("2026-03-13 12:45:00") == "黄昏"
    assert infer_time_period_from_timestamp("2026-03-13 12:55:00") == "深夜"


def test_normalize_record_row_backfills_defaults_and_time_period():
    row = normalize_record_row(
        {
            "Timestamp": "2026-03-13 12:25:00",
            "Name": "鲈鱼",
            "Quality": "稀有",
            "Weight": "2.5",
        }
    )

    assert row["Bait"] == "蔓越莓"
    assert row["BaitCost"] == "1"
    assert row["IsNewRecord"] == "No"
    assert row["TimePeriod"] == "上午"


def test_ensure_record_schema_rewrites_legacy_records_file(tmp_path):
    records_file = tmp_path / "records.csv"
    records_file.write_text(
        "Timestamp,Name,Quality,Weight\n" "2026-03-13 12:45:00,鲈鱼,稀有,2.5\n",
        encoding="utf-8-sig",
    )

    assert ensure_record_schema(records_file) is True

    with open(records_file, "r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows
    assert list(rows[0].keys()) == RECORD_FIELDNAMES
    assert rows[0]["Bait"] == "蔓越莓"
    assert rows[0]["BaitCost"] == "1"
    assert rows[0]["TimePeriod"] == "黄昏"
