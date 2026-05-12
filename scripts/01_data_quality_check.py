from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import (  # noqa: E402
    column_stats,
    date_columns,
    ensure_project_dirs,
    format_date,
    format_number,
    iqr_outlier_count,
    numeric_columns,
    parse_date,
    parse_float,
    read_csv_auto,
    safe_divide,
    write_csv,
)


RAW_DIR = ROOT / "data" / "raw"
SUMMARY_PATH = ROOT / "outputs" / "tables" / "data_quality_summary.csv"
REPORT_PATH = ROOT / "reports" / "data_quality_report.md"


def missing_counts(headers: list[str], rows: list[dict[str, str]]) -> dict[str, int]:
    return {
        header: sum(1 for row in rows if str(row.get(header, "")).strip() == "")
        for header in headers
    }


def date_range(rows: list[dict[str, str]], date_col: str | None) -> tuple[str, str, int]:
    if not date_col:
        return "", "", 0
    parsed = [parse_date(row.get(date_col, "")) for row in rows]
    parsed = [value for value in parsed if value is not None]
    if not parsed:
        return "", "", 0
    counts = Counter(parsed)
    duplicate_count = sum(count - 1 for count in counts.values() if count > 1)
    return format_date(min(parsed)), format_date(max(parsed)), duplicate_count


def numeric_summary(headers: list[str], rows: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for column in numeric_columns(headers, rows):
        values = [parse_float(row.get(column, "")) for row in rows]
        clean = [value for value in values if value is not None]
        result[column] = column_stats(clean)
    return result


def detect_anomalies(headers: list[str], rows: list[dict[str, str]]) -> list[str]:
    hints: list[str] = []
    for column in numeric_columns(headers, rows):
        values = [parse_float(row.get(column, "")) for row in rows]
        clean = [value for value in values if value is not None]
        if not clean:
            continue
        lower_name = column.lower()
        if any(token in lower_name for token in ("price", "oil", "import", "ceiling", "volume", "amount")):
            non_positive = sum(value <= 0 for value in clean)
            if non_positive:
                hints.append(f"{column}: {non_positive} non-positive values")
        outlier_count, lower, upper = iqr_outlier_count(clean)
        if outlier_count:
            hints.append(
                f"{column}: {outlier_count} IQR outliers outside "
                f"[{format_number(lower)}, {format_number(upper)}]"
            )
    return hints


def crude_import_checks(rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], list[str]]:
    flagged: list[dict[str, object]] = []
    messages: list[str] = []
    avg_values: list[float] = []
    for row in rows:
        avg = parse_float(row.get("average_price_usd_per_ton", ""))
        if avg is not None:
            avg_values.append(avg)

    _, lower_bound, upper_bound = iqr_outlier_count(avg_values, multiplier=3.0)
    for row in rows:
        date_text = row.get("date", "")
        volume = parse_float(row.get("import_volume_10k_tons", ""))
        amount = parse_float(row.get("import_amount_10k_usd", ""))
        reported = parse_float(row.get("average_price_usd_per_ton", ""))
        recalculated = safe_divide(amount, volume)
        diff = None if recalculated is None or reported is None else reported - recalculated
        diff_abs = None if diff is None else abs(diff)
        flags: list[str] = []
        if diff_abs is not None and diff_abs > max(1.0, abs(recalculated or 0) * 0.005):
            flags.append("reported average price differs from recalculated value")
        if reported is None or reported <= 0:
            flags.append("reported average price is missing or non-positive")
        if (
            reported is not None
            and lower_bound is not None
            and upper_bound is not None
            and (reported < lower_bound or reported > upper_bound)
        ):
            flags.append("reported average price is an IQR outlier")
        if flags:
            flagged.append(
                {
                    "date": date_text,
                    "import_volume_10k_tons": format_number(volume),
                    "import_amount_10k_usd": format_number(amount),
                    "average_price_usd_per_ton": format_number(reported),
                    "recalc_avg_price_usd_per_ton": format_number(recalculated),
                    "difference": format_number(diff),
                    "flags": "; ".join(flags),
                }
            )

    if flagged:
        messages.append(f"china_crude_oil_import_monthly.csv: {len(flagged)} flagged monthly records")
    else:
        messages.append("china_crude_oil_import_monthly.csv: no large average-price discrepancies flagged")
    return flagged, messages


def markdown_table(rows: list[dict[str, object]], columns: list[str]) -> str:
    if not rows:
        return "_None._"
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    return "\n".join(lines)


def main() -> None:
    ensure_project_dirs(ROOT)
    summary_rows: list[dict[str, object]] = []
    report_lines: list[str] = ["# Data Quality Report", ""]
    crude_flagged_rows: list[dict[str, object]] = []
    crude_messages: list[str] = []

    for csv_path in sorted(RAW_DIR.glob("*.csv")):
        headers, rows, metadata = read_csv_auto(csv_path)
        dates = date_columns(headers, rows)
        primary_date_col = dates[0] if dates else None
        min_date, max_date, duplicate_dates = date_range(rows, primary_date_col)
        miss = missing_counts(headers, rows)
        nums = numeric_summary(headers, rows)
        anomalies = detect_anomalies(headers, rows)

        summary_rows.append(
            {
                "file": csv_path.name,
                "row_count": len(rows),
                "column_count": len(headers),
                "columns": "; ".join(headers),
                "metadata_lines": " | ".join(metadata),
                "date_columns": "; ".join(dates),
                "date_min": min_date,
                "date_max": max_date,
                "duplicate_primary_date_count": duplicate_dates,
                "missing_counts_json": json.dumps(miss, ensure_ascii=False),
                "numeric_columns": "; ".join(nums.keys()),
                "anomaly_hints": " | ".join(anomalies),
            }
        )

        report_lines.extend(
            [
                f"## {csv_path.name}",
                "",
                f"- Rows: {len(rows)}",
                f"- Columns: {len(headers)}",
                f"- Field names: {', '.join(headers) if headers else '(none)'}",
                f"- Metadata line(s): {' | '.join(metadata) if metadata else '(none)'}",
                f"- Date column recognition: {', '.join(dates) if dates else '(none)'}",
                f"- Date range: {min_date or '(not available)'} to {max_date or '(not available)'}",
                f"- Duplicate dates on primary date column: {duplicate_dates}",
                "",
                "Missing values:",
                "",
                markdown_table(
                    [{"column": key, "missing_count": value} for key, value in miss.items()],
                    ["column", "missing_count"],
                ),
                "",
            ]
        )

        if nums:
            stat_rows: list[dict[str, object]] = []
            for column, stats in nums.items():
                stat_rows.append(
                    {
                        "column": column,
                        "count": stats["count"],
                        "mean": format_number(stats["mean"]),
                        "std": format_number(stats["std"]),
                        "min": format_number(stats["min"]),
                        "q1": format_number(stats["q1"]),
                        "median": format_number(stats["median"]),
                        "q3": format_number(stats["q3"]),
                        "max": format_number(stats["max"]),
                    }
                )
            report_lines.extend(
                [
                    "Numeric summary:",
                    "",
                    markdown_table(stat_rows, ["column", "count", "mean", "std", "min", "q1", "median", "q3", "max"]),
                    "",
                ]
            )

        report_lines.extend(
            [
                "Anomaly hints:",
                "",
                "\n".join(f"- {hint}" for hint in anomalies) if anomalies else "_None._",
                "",
            ]
        )

        if csv_path.name == "china_crude_oil_import_monthly.csv":
            crude_flagged_rows, crude_messages = crude_import_checks(rows)

    write_csv(
        SUMMARY_PATH,
        summary_rows,
        [
            "file",
            "row_count",
            "column_count",
            "columns",
            "metadata_lines",
            "date_columns",
            "date_min",
            "date_max",
            "duplicate_primary_date_count",
            "missing_counts_json",
            "numeric_columns",
            "anomaly_hints",
        ],
    )

    report_lines.extend(["## Special Check: Crude Oil Import Average Price", ""])
    report_lines.extend(f"- {message}" for message in crude_messages)
    report_lines.append("")
    report_lines.append(
        markdown_table(
            crude_flagged_rows,
            [
                "date",
                "import_volume_10k_tons",
                "import_amount_10k_usd",
                "average_price_usd_per_ton",
                "recalc_avg_price_usd_per_ton",
                "difference",
                "flags",
            ],
        )
    )
    report_lines.append("")
    REPORT_PATH.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"Wrote {SUMMARY_PATH}")
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
