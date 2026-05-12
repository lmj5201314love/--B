from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import (  # noqa: E402
    ensure_project_dirs,
    format_date,
    format_number,
    month_key,
    parse_date,
    parse_float,
    read_csv_auto,
    write_csv,
)


RAW_PATH = ROOT / "data" / "raw" / "china_refined_oil_adjustments_2013_2026.csv"
OUT_PATH = ROOT / "data" / "processed" / "fuel_adjustments_clean.csv"
SUMMARY_PATH = ROOT / "outputs" / "tables" / "fuel_adjustment_summary.csv"


def main() -> None:
    ensure_project_dirs(ROOT)
    headers, rows, _ = read_csv_auto(RAW_PATH)
    required = {
        "date",
        "notice_date",
        "gasoline_adjust_cny_per_ton",
        "diesel_adjust_cny_per_ton",
        "beijing_gasoline_ceiling_after_cny_per_ton",
        "beijing_diesel_ceiling_after_cny_per_ton",
    }
    missing = required - set(headers)
    if missing:
        raise ValueError(f"Missing required columns in {RAW_PATH.name}: {sorted(missing)}")

    output_rows: list[dict[str, object]] = []
    for row in rows:
        adjust_date = parse_date(row.get("date", ""))
        notice_date = parse_date(row.get("notice_date", ""))
        gasoline_adjust = parse_float(row.get("gasoline_adjust_cny_per_ton", ""))
        diesel_adjust = parse_float(row.get("diesel_adjust_cny_per_ton", ""))
        gas_ceiling = parse_float(row.get("beijing_gasoline_ceiling_after_cny_per_ton", ""))
        diesel_ceiling = parse_float(row.get("beijing_diesel_ceiling_after_cny_per_ton", ""))
        avg_adjust = None
        if gasoline_adjust is not None and diesel_adjust is not None:
            avg_adjust = (gasoline_adjust + diesel_adjust) / 2
        avg_ceiling = None
        if gas_ceiling is not None and diesel_ceiling is not None:
            avg_ceiling = (gas_ceiling + diesel_ceiling) / 2
        is_adjusted = 1 if (gasoline_adjust not in (None, 0) or diesel_adjust not in (None, 0)) else 0
        if avg_adjust is None or avg_adjust == 0:
            direction = "no_adjust"
        elif avg_adjust > 0:
            direction = "up"
        else:
            direction = "down"

        output = dict(row)
        output.update(
            {
                "date": format_date(adjust_date),
                "notice_date": format_date(notice_date),
                "avg_adjust_cny_per_ton": format_number(avg_adjust),
                "avg_ceiling_after_cny_per_ton": format_number(avg_ceiling),
                "is_adjusted": is_adjusted,
                "adjust_direction": direction,
                "abs_adjust_cny_per_ton": format_number(abs(avg_adjust) if avg_adjust is not None else None),
                "month": month_key(adjust_date),
            }
        )
        output_rows.append(output)

    output_rows.sort(key=lambda item: (item.get("notice_date", ""), item.get("date", "")))
    fieldnames = headers + [
        "avg_adjust_cny_per_ton",
        "avg_ceiling_after_cny_per_ton",
        "is_adjusted",
        "adjust_direction",
        "abs_adjust_cny_per_ton",
        "month",
    ]
    write_csv(OUT_PATH, output_rows, fieldnames)

    avg_adjusts = [parse_float(row.get("avg_adjust_cny_per_ton", "")) for row in output_rows]
    up_values = [value for value in avg_adjusts if value is not None and value > 0]
    down_values = [value for value in avg_adjusts if value is not None and value < 0]
    no_adjust_count = sum(1 for value in avg_adjusts if value == 0)
    summary = [
        {"metric": "total_windows", "value": len(output_rows)},
        {"metric": "up_count", "value": len(up_values)},
        {"metric": "down_count", "value": len(down_values)},
        {"metric": "no_adjust_count", "value": no_adjust_count},
        {"metric": "average_up_adjust_cny_per_ton", "value": format_number(sum(up_values) / len(up_values) if up_values else None)},
        {
            "metric": "average_down_adjust_cny_per_ton",
            "value": format_number(sum(down_values) / len(down_values) if down_values else None),
        },
        {"metric": "max_up_adjust_cny_per_ton", "value": format_number(max(up_values) if up_values else None)},
        {"metric": "max_down_adjust_cny_per_ton", "value": format_number(min(down_values) if down_values else None)},
    ]
    write_csv(SUMMARY_PATH, summary, ["metric", "value"])
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
