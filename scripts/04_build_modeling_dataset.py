from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import (  # noqa: E402
    column_stats,
    ensure_project_dirs,
    format_number,
    month_key,
    parse_date,
    parse_float,
    read_csv_auto,
    safe_divide,
    write_csv,
)


OIL_PATH = ROOT / "data" / "processed" / "oil_price_daily.csv"
FUEL_PATH = ROOT / "data" / "processed" / "fuel_adjustments_clean.csv"
CPI_PPI_PATH = ROOT / "data" / "raw" / "china_cpi_ppi_monthly.csv"
PMI_PATH = ROOT / "data" / "raw" / "china_pmi_monthly.csv"
IMPORT_PATH = ROOT / "data" / "raw" / "china_crude_oil_import_monthly.csv"
OUT_PATH = ROOT / "data" / "processed" / "modeling_dataset.csv"
QUALITY_PATH = ROOT / "outputs" / "tables" / "modeling_dataset_quality.csv"


OIL_VALUE_COLUMNS = [
    "basket_usd_per_bbl",
    "brent_usd_per_bbl",
    "wti_usd_per_bbl",
    "brent_wti_avg_usd_per_bbl",
    "brent_wti_weighted_usd_per_bbl",
]

WINDOW_SPECS = [
    ("basket_usd_per_bbl", "basket_window_avg", "basket_window_change", "basket_window_change_pct"),
    ("brent_usd_per_bbl", "brent_window_avg", "brent_window_change", "brent_window_change_pct"),
    ("wti_usd_per_bbl", "wti_window_avg", "wti_window_change", "wti_window_change_pct"),
    (
        "brent_wti_avg_usd_per_bbl",
        "brent_wti_avg_window_avg",
        "brent_wti_avg_window_change",
        "brent_wti_avg_window_change_pct",
    ),
    (
        "brent_wti_weighted_usd_per_bbl",
        "brent_wti_weighted_window_avg",
        "brent_wti_weighted_window_change",
        "brent_wti_weighted_window_change_pct",
    ),
]


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    headers, rows, _ = read_csv_auto(path)
    return headers, rows


def load_monthly_map(path: Path, columns: list[str]) -> dict[str, dict[str, str]]:
    _, rows = load_csv(path)
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        month = month_key(row.get("date", ""))
        if not month:
            continue
        result[month] = {column: format_number(parse_float(row.get(column, ""))) for column in columns}
    return result


def compute_recent_average(
    oil_rows: list[dict[str, object]],
    notice_date,
    column: str,
    window_size: int = 10,
) -> tuple[float | None, int]:
    values: list[float] = []
    for row in reversed(oil_rows):
        row_date = row["date"]
        if row_date >= notice_date:
            continue
        value = row.get(column)
        if value is not None:
            values.append(value)
        if len(values) == window_size:
            break
    if not values:
        return None, 0
    return sum(values) / len(values), len(values)


def quality_rows(rows: list[dict[str, object]], fieldnames: list[str]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    total = len(rows)
    for column in fieldnames:
        values = [row.get(column, "") for row in rows]
        missing = sum(1 for value in values if value in ("", None))
        numeric = [parse_float(value) for value in values]
        clean = [value for value in numeric if value is not None]
        stats = column_stats(clean)
        result.append(
            {
                "column": column,
                "row_count": total,
                "missing_count": missing,
                "missing_pct": format_number(100 * missing / total if total else None),
                "numeric_count": stats["count"],
                "numeric_min": format_number(stats["min"]),
                "numeric_mean": format_number(stats["mean"]),
                "numeric_max": format_number(stats["max"]),
            }
        )
    notice_dates = [row.get("notice_date", "") for row in rows if row.get("notice_date", "")]
    duplicate_notice_dates = len(notice_dates) - len(set(notice_dates))
    result.append(
        {
            "column": "__duplicate_notice_date_count__",
            "row_count": total,
            "missing_count": duplicate_notice_dates,
            "missing_pct": "",
            "numeric_count": "",
            "numeric_min": "",
            "numeric_mean": "",
            "numeric_max": "",
        }
    )
    return result


def main() -> None:
    ensure_project_dirs(ROOT)
    _, oil_raw = load_csv(OIL_PATH)
    _, fuel_rows = load_csv(FUEL_PATH)

    oil_rows: list[dict[str, object]] = []
    for row in oil_raw:
        parsed_date = parse_date(row.get("date", ""))
        if parsed_date is None:
            continue
        converted: dict[str, object] = {"date": parsed_date}
        for column in OIL_VALUE_COLUMNS:
            converted[column] = parse_float(row.get(column, ""))
        oil_rows.append(converted)
    oil_rows.sort(key=lambda item: item["date"])

    cpi_ppi = load_monthly_map(CPI_PPI_PATH, ["cpi_yoy_pct", "ppi_yoy_pct"])
    pmi = load_monthly_map(PMI_PATH, ["nbs_manufacturing_pmi", "non_manufacturing_pmi", "nbs_general_pmi"])
    crude_import = load_monthly_map(
        IMPORT_PATH,
        ["import_volume_10k_tons", "import_amount_10k_usd", "average_price_usd_per_ton"],
    )

    output_rows: list[dict[str, object]] = []
    previous_window_values: dict[str, float | None] = defaultdict(lambda: None)
    fuel_rows.sort(key=lambda item: (item.get("notice_date", ""), item.get("date", "")))

    for row in fuel_rows:
        notice_date = parse_date(row.get("notice_date", "")) or parse_date(row.get("date", ""))
        output: dict[str, object] = dict(row)
        if notice_date is None:
            for _, avg_col, change_col, pct_col in WINDOW_SPECS:
                output[avg_col] = ""
                output[f"{avg_col}_valid_days"] = ""
                output[change_col] = ""
                output[pct_col] = ""
        else:
            for source_col, avg_col, change_col, pct_col in WINDOW_SPECS:
                avg, valid_days = compute_recent_average(oil_rows, notice_date, source_col)
                output[avg_col] = format_number(avg)
                output[f"{avg_col}_valid_days"] = valid_days

                previous = previous_window_values[avg_col]
                change = None if previous is None or avg is None else avg - previous
                pct = None if previous is None or avg is None else safe_divide(change, previous)
                output[change_col] = format_number(change)
                output[pct_col] = format_number(pct * 100 if pct is not None else None)
                previous_window_values[avg_col] = avg

        month = row.get("month", "") or month_key(row.get("date", ""))
        output["month"] = month
        for source in (cpi_ppi, pmi, crude_import):
            output.update(source.get(month, {}))
        output_rows.append(output)

    original_headers = list(fuel_rows[0].keys()) if fuel_rows else []
    generated_headers = []
    for _, avg_col, change_col, pct_col in WINDOW_SPECS:
        generated_headers.extend(
            [
                avg_col,
                f"{avg_col}_valid_days",
                change_col,
                pct_col,
            ]
        )
    monthly_headers = [
        "cpi_yoy_pct",
        "ppi_yoy_pct",
        "nbs_manufacturing_pmi",
        "non_manufacturing_pmi",
        "nbs_general_pmi",
        "import_volume_10k_tons",
        "import_amount_10k_usd",
        "average_price_usd_per_ton",
    ]
    fieldnames = original_headers + [name for name in generated_headers + monthly_headers if name not in original_headers]
    write_csv(OUT_PATH, output_rows, fieldnames)
    write_csv(
        QUALITY_PATH,
        quality_rows(output_rows, fieldnames),
        [
            "column",
            "row_count",
            "missing_count",
            "missing_pct",
            "numeric_count",
            "numeric_min",
            "numeric_mean",
            "numeric_max",
        ],
    )
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {QUALITY_PATH}")


if __name__ == "__main__":
    main()
