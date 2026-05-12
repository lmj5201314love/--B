from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import (  # noqa: E402
    direction_accuracy,
    ensure_project_dirs,
    format_number,
    linear_regression,
    mae,
    parse_date,
    parse_float,
    read_csv_auto,
    rmse,
    write_csv,
)


DATA_PATH = ROOT / "data" / "processed" / "modeling_dataset.csv"
COMPARISON_PATH = ROOT / "outputs" / "tables" / "mechanism_baseline_comparison.csv"
OUT_PATH = ROOT / "data" / "processed" / "modeling_dataset_with_theory_adjust.csv"
START_DATE = parse_date("2016-01-01")

PROXY_COLUMNS = [
    "basket_window_change",
    "brent_window_change",
    "wti_window_change",
    "brent_wti_avg_window_change",
    "brent_wti_weighted_window_change",
]


def fit_model(rows: list[dict[str, str]], proxy: str) -> dict[str, object]:
    xs: list[float] = []
    ys: list[float] = []
    for row in rows:
        parsed = parse_date(row.get("date", ""))
        if parsed is None or START_DATE is None or parsed < START_DATE:
            continue
        x = parse_float(row.get(proxy, ""))
        y = parse_float(row.get("avg_adjust_cny_per_ton", ""))
        if x is None or y is None:
            continue
        xs.append(x)
        ys.append(y)
    slope, intercept = linear_regression(xs, ys)
    predictions = [slope * x + intercept for x in xs]
    return {
        "proxy_variable": proxy,
        "sample_size": len(xs),
        "k": slope,
        "b": intercept,
        "MAE": mae(ys, predictions),
        "RMSE": rmse(ys, predictions),
        "direction_accuracy": direction_accuracy(ys, predictions),
    }


def main() -> None:
    ensure_project_dirs(ROOT)
    headers, rows, _ = read_csv_auto(DATA_PATH)
    results = [fit_model(rows, proxy) for proxy in PROXY_COLUMNS]
    ranked = sorted(results, key=lambda item: (item["RMSE"], item["MAE"], -item["direction_accuracy"]))
    best = ranked[0]
    for row in results:
        row["is_selected_proxy"] = 1 if row["proxy_variable"] == best["proxy_variable"] else 0

    write_csv(
        COMPARISON_PATH,
        [
            {
                "proxy_variable": row["proxy_variable"],
                "sample_size": row["sample_size"],
                "k": format_number(row["k"]),
                "b": format_number(row["b"]),
                "MAE": format_number(row["MAE"]),
                "RMSE": format_number(row["RMSE"]),
                "direction_accuracy": format_number(row["direction_accuracy"]),
                "is_selected_proxy": row["is_selected_proxy"],
            }
            for row in results
        ],
        ["proxy_variable", "sample_size", "k", "b", "MAE", "RMSE", "direction_accuracy", "is_selected_proxy"],
    )

    proxy = str(best["proxy_variable"])
    slope = float(best["k"])
    intercept = float(best["b"])
    output_rows: list[dict[str, object]] = []
    for row in rows:
        output = dict(row)
        x = parse_float(row.get(proxy, ""))
        y = parse_float(row.get("avg_adjust_cny_per_ton", ""))
        theory = None if x is None else slope * x + intercept
        error = None if theory is None or y is None else y - theory
        output["theory_adjust_cny_per_ton"] = format_number(theory)
        output["theory_error_cny_per_ton"] = format_number(error)
        output_rows.append(output)

    fieldnames = headers + ["theory_adjust_cny_per_ton", "theory_error_cny_per_ton"]
    write_csv(OUT_PATH, output_rows, fieldnames)
    print(f"Wrote {COMPARISON_PATH}")
    print(f"Selected proxy: {proxy}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
