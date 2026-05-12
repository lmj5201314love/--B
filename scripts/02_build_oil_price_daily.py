from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import (  # noqa: E402
    column_stats,
    date_columns,
    ensure_project_dirs,
    format_date,
    format_number,
    numeric_columns,
    parse_date,
    parse_float,
    read_csv_auto,
    write_csv,
)


RAW_DIR = ROOT / "data" / "raw"
OUT_PATH = ROOT / "data" / "processed" / "oil_price_daily.csv"
SUMMARY_PATH = ROOT / "outputs" / "tables" / "oil_price_daily_summary.csv"


def choose_date_col(headers: list[str], rows: list[dict[str, str]], file_name: str) -> str:
    dates = date_columns(headers, rows)
    if not dates:
        raise ValueError(f"Cannot identify date column in {file_name}. Headers: {headers}")
    return dates[0]


def choose_price_col(headers: list[str], rows: list[dict[str, str]], date_col: str, file_name: str) -> str:
    for header in headers:
        if header != date_col and header.lower() == "price":
            return header
    nums = [header for header in numeric_columns(headers, rows) if header != date_col]
    if not nums:
        raise ValueError(f"Cannot identify price column in {file_name}. Headers: {headers}")
    return nums[0]


def load_price_series(file_name: str, output_col: str) -> dict[str, float]:
    headers, rows, _ = read_csv_auto(RAW_DIR / file_name)
    date_col = choose_date_col(headers, rows, file_name)
    price_col = choose_price_col(headers, rows, date_col, file_name)
    series: dict[str, float] = {}
    for row in rows:
        parsed_date = parse_date(row.get(date_col, ""))
        price = parse_float(row.get(price_col, ""))
        if parsed_date is None or price is None:
            continue
        series[format_date(parsed_date)] = price
    if not series:
        raise ValueError(f"No valid date/price rows found in {file_name} for {output_col}.")
    return series


def main() -> None:
    ensure_project_dirs(ROOT)
    basket = load_price_series("basket_oil_daily.csv", "basket_usd_per_bbl")
    brent = load_price_series("brent_daily.csv", "brent_usd_per_bbl")
    wti = load_price_series("wti_daily.csv", "wti_usd_per_bbl")

    all_dates = sorted(set(basket) | set(brent) | set(wti))
    output_rows: list[dict[str, object]] = []
    for date_text in all_dates:
        brent_value = brent.get(date_text)
        wti_value = wti.get(date_text)
        avg_value = None
        weighted_value = None
        if brent_value is not None and wti_value is not None:
            avg_value = (brent_value + wti_value) / 2
            weighted_value = 0.7 * brent_value + 0.3 * wti_value
        output_rows.append(
            {
                "date": date_text,
                "basket_usd_per_bbl": format_number(basket.get(date_text)),
                "brent_usd_per_bbl": format_number(brent_value),
                "wti_usd_per_bbl": format_number(wti_value),
                "brent_wti_avg_usd_per_bbl": format_number(avg_value),
                "brent_wti_weighted_usd_per_bbl": format_number(weighted_value),
            }
        )

    fieldnames = [
        "date",
        "basket_usd_per_bbl",
        "brent_usd_per_bbl",
        "wti_usd_per_bbl",
        "brent_wti_avg_usd_per_bbl",
        "brent_wti_weighted_usd_per_bbl",
    ]
    write_csv(OUT_PATH, output_rows, fieldnames)

    summary_rows: list[dict[str, object]] = []
    for column in fieldnames[1:]:
        values = [parse_float(row[column]) for row in output_rows]
        clean = [value for value in values if value is not None]
        stats = column_stats(clean)
        dates_with_values = [row["date"] for row in output_rows if parse_float(row[column]) is not None]
        summary_rows.append(
            {
                "series": column,
                "non_missing_count": stats["count"],
                "missing_count": len(output_rows) - int(stats["count"]),
                "date_min": min(dates_with_values) if dates_with_values else "",
                "date_max": max(dates_with_values) if dates_with_values else "",
                "mean": format_number(stats["mean"]),
                "min": format_number(stats["min"]),
                "max": format_number(stats["max"]),
            }
        )
    write_csv(
        SUMMARY_PATH,
        summary_rows,
        ["series", "non_missing_count", "missing_count", "date_min", "date_max", "mean", "min", "max"],
    )
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
