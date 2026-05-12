from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import (  # noqa: E402
    direction_accuracy,
    ensure_project_dirs,
    format_number,
    mae,
    parse_date,
    parse_float,
    read_csv_auto,
    rmse,
    sign,
    write_csv,
)
from src.policy_rules import (  # noqa: E402
    apply_oil_price_band_policy,
    apply_threshold_and_carry,
    oil_price_band,
    profit_deduction_factor,
)
from src.svg_utils import line_chart_date, scatter_chart, box_strip_chart  # noqa: E402


MODEL_DATA_PATH = ROOT / "data" / "processed" / "modeling_dataset.csv"
BASELINE_PATH = ROOT / "outputs" / "tables" / "mechanism_baseline_comparison.csv"
OUT_PATH = ROOT / "data" / "processed" / "modeling_dataset_policy_band.csv"
VALIDATION_PATH = ROOT / "outputs" / "tables" / "policy_band_mechanism_validation.csv"
FIGURE_DIR = ROOT / "outputs" / "figures"

START_DATE = parse_date("2016-01-01")
END_DATE = parse_date("2026-05-09")
PROXY_COL = "brent_wti_weighted_window_change"
OIL_LEVEL_COL = "brent_wti_weighted_window_avg"


def in_main_sample(row: dict[str, str]) -> bool:
    parsed = parse_date(row.get("date", ""))
    return parsed is not None and START_DATE is not None and END_DATE is not None and START_DATE <= parsed <= END_DATE


def load_coefficients() -> tuple[float, float]:
    _, rows, _ = read_csv_auto(BASELINE_PATH)
    for row in rows:
        if row.get("proxy_variable") == PROXY_COL:
            k = parse_float(row.get("k"))
            b = parse_float(row.get("b"))
            if k is None or b is None:
                break
            return k, b
    raise ValueError(f"Cannot find coefficients for {PROXY_COL}")


def is_adjusted(value: float | None) -> int:
    return 1 if value is not None and abs(value) > 1e-9 else 0


def build_policy_band_rows() -> tuple[list[str], list[dict[str, Any]]]:
    headers, rows, _ = read_csv_auto(MODEL_DATA_PATH)
    k, b = load_coefficients()
    main_rows = [dict(row) for row in rows if in_main_sample(row)]
    main_rows.sort(key=lambda item: (item.get("date", ""), item.get("notice_date", "")))

    raw_adjusts: list[float | None] = []
    band_adjusts: list[float | None] = []
    for row in main_rows:
        oil_change = parse_float(row.get(PROXY_COL))
        oil_level = parse_float(row.get(OIL_LEVEL_COL))
        raw_adjust = None if oil_change is None else k * oil_change + b
        band_adjust = apply_oil_price_band_policy(raw_adjust, oil_level)
        raw_adjusts.append(raw_adjust)
        band_adjusts.append(band_adjust)

    original_rule, original_carry_before, original_carry_after = apply_threshold_and_carry(raw_adjusts)
    band_rule, band_carry_before, band_carry_after = apply_threshold_and_carry(band_adjusts)

    output_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(main_rows):
        oil_level = parse_float(row.get(OIL_LEVEL_COL))
        raw_adjust = raw_adjusts[idx]
        band_adjust = band_adjusts[idx]
        actual = parse_float(row.get("avg_adjust_cny_per_ton"))
        band = oil_price_band(oil_level)
        factor = profit_deduction_factor(oil_level)
        output = dict(row)
        output.update(
            {
                "oil_price_band": band,
                "profit_deduction_factor": format_number(factor),
                "is_low_floor_binding": 1 if oil_level is not None and oil_level <= 40 and raw_adjust is not None and raw_adjust < 0 else 0,
                "is_profit_deduction_binding": 1 if oil_level is not None and 80 < oil_level < 130 and raw_adjust is not None and raw_adjust > 0 else 0,
                "is_extreme_high_binding": 1 if oil_level is not None and oil_level >= 130 and raw_adjust is not None and raw_adjust > 0 else 0,
                "theory_adjust_raw_cny_per_ton": format_number(raw_adjust),
                "theory_adjust_rule_cny_per_ton": format_number(original_rule[idx]),
                "carry_before_rule_cny_per_ton": format_number(original_carry_before[idx]),
                "carry_after_rule_cny_per_ton": format_number(original_carry_after[idx]),
                "theory_adjust_band_cny_per_ton": format_number(band_adjust),
                "theory_adjust_band_rule_cny_per_ton": format_number(band_rule[idx]),
                "carry_before_band_cny_per_ton": format_number(band_carry_before[idx]),
                "carry_after_band_cny_per_ton": format_number(band_carry_after[idx]),
                "theory_error_band_rule_cny_per_ton": format_number(None if actual is None or band_rule[idx] is None else actual - band_rule[idx]),
            }
        )
        output_rows.append(output)

    new_fields = [
        "oil_price_band",
        "profit_deduction_factor",
        "is_low_floor_binding",
        "is_profit_deduction_binding",
        "is_extreme_high_binding",
        "theory_adjust_raw_cny_per_ton",
        "theory_adjust_rule_cny_per_ton",
        "carry_before_rule_cny_per_ton",
        "carry_after_rule_cny_per_ton",
        "theory_adjust_band_cny_per_ton",
        "theory_adjust_band_rule_cny_per_ton",
        "carry_before_band_cny_per_ton",
        "carry_after_band_cny_per_ton",
        "theory_error_band_rule_cny_per_ton",
    ]
    return headers + [field for field in new_fields if field not in headers], output_rows


def model_metrics(rows: list[dict[str, Any]], model_name: str, pred_col: str) -> dict[str, Any]:
    paired: list[tuple[float, float, str]] = []
    for row in rows:
        actual = parse_float(row.get("avg_adjust_cny_per_ton"))
        pred = parse_float(row.get(pred_col))
        if actual is None or pred is None:
            continue
        paired.append((actual, pred, str(row.get("oil_price_band", ""))))
    actual_values = [item[0] for item in paired]
    pred_values = [item[1] for item in paired]
    no_adjust_rows = [(actual, pred) for actual, pred, _ in paired if actual == 0]
    low_rows = [(actual, pred) for actual, pred, band in paired if band == "low_floor"]
    normal_rows = [(actual, pred) for actual, pred, band in paired if band == "normal"]
    high_rows = [(actual, pred) for actual, pred, band in paired if band in {"profit_deduction", "extreme_high"}]

    def subgroup_mae(sub_rows: list[tuple[float, float]]) -> float | None:
        return mae([item[0] for item in sub_rows], [item[1] for item in sub_rows]) if sub_rows else None

    return {
        "model": model_name,
        "MAE": format_number(mae(actual_values, pred_values) if paired else None),
        "RMSE": format_number(rmse(actual_values, pred_values) if paired else None),
        "direction_accuracy": format_number(direction_accuracy(actual_values, pred_values) if paired else None),
        "adjustment_accuracy": format_number(
            sum(is_adjusted(actual) == is_adjusted(pred) for actual, pred, _ in paired) / len(paired) if paired else None
        ),
        "no_adjust_recognition_accuracy": format_number(
            sum(sign(pred) == 0 for _, pred in no_adjust_rows) / len(no_adjust_rows) if no_adjust_rows else None
        ),
        "low_oil_MAE": format_number(subgroup_mae(low_rows)),
        "normal_oil_MAE": format_number(subgroup_mae(normal_rows)),
        "high_oil_MAE": format_number(subgroup_mae(high_rows)),
        "low_oil_no_adjust_recognition_accuracy": format_number(
            sum(sign(pred) == 0 for actual, pred in low_rows if actual == 0) / sum(1 for actual, _ in low_rows if actual == 0)
            if sum(1 for actual, _ in low_rows if actual == 0)
            else None
        ),
        "sample_size": len(paired),
    }


def build_validation(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        model_metrics(rows, "raw_linear", "theory_adjust_raw_cny_per_ton"),
        model_metrics(rows, "rule_threshold_carry", "theory_adjust_rule_cny_per_ton"),
        model_metrics(rows, "policy_band_rule", "theory_adjust_band_rule_cny_per_ton"),
    ]


def build_figures(rows: list[dict[str, Any]], validation_rows: list[dict[str, Any]]) -> None:
    time_series = []
    for label, col, color in (
        ("Actual", "avg_adjust_cny_per_ton", "#222222"),
        ("Rule threshold/carry", "theory_adjust_rule_cny_per_ton", "#4c78a8"),
        ("Policy band rule", "theory_adjust_band_rule_cny_per_ton", "#e45756"),
    ):
        points = []
        for row in rows:
            parsed = parse_date(row.get("date", ""))
            value = parse_float(row.get(col))
            if parsed is not None and value is not None:
                points.append((parsed, value))
        time_series.append((label, points, color))
    line_chart_date(
        FIGURE_DIR / "policy_band_theory_vs_actual.svg",
        "Policy Band Theory vs Actual Adjustment",
        time_series,
        "CNY per ton",
    )

    categories = []
    model_colors = {
        "raw_linear": "#777777",
        "rule_threshold_carry": "#4c78a8",
        "policy_band_rule": "#e45756",
    }
    for row in validation_rows:
        values = [
            parse_float(row.get("low_oil_MAE")),
            parse_float(row.get("normal_oil_MAE")),
            parse_float(row.get("high_oil_MAE")),
        ]
        categories.append((row["model"], [value for value in values if value is not None], model_colors.get(row["model"], "#4c78a8")))
    box_strip_chart(
        FIGURE_DIR / "policy_band_error_by_oil_regime.svg",
        "MAE by Oil Regime and Model",
        categories,
        "MAE (low, normal, high points)",
        include_zero=True,
    )

    scatter_points = []
    for row in rows:
        x_value = parse_float(row.get("theory_adjust_band_rule_cny_per_ton"))
        y_value = parse_float(row.get("avg_adjust_cny_per_ton"))
        if x_value is not None and y_value is not None:
            scatter_points.append((x_value, y_value, str(row.get("oil_price_band", ""))))
    scatter_chart(
        FIGURE_DIR / "policy_band_scatter.svg",
        "Policy Band Rule vs Actual Adjustment",
        scatter_points,
        "Policy-band theory adjustment (CNY per ton)",
        "Actual adjustment (CNY per ton)",
        {
            "low_floor": "#4c78a8",
            "normal": "#59a14f",
            "profit_deduction": "#e45756",
            "extreme_high": "#b279a2",
        },
        draw_equal_line=True,
    )


def main() -> None:
    ensure_project_dirs(ROOT)
    fieldnames, rows = build_policy_band_rows()
    write_csv(OUT_PATH, rows, fieldnames)
    validation_rows = build_validation(rows)
    write_csv(
        VALIDATION_PATH,
        validation_rows,
        [
            "model",
            "MAE",
            "RMSE",
            "direction_accuracy",
            "adjustment_accuracy",
            "no_adjust_recognition_accuracy",
            "low_oil_MAE",
            "normal_oil_MAE",
            "high_oil_MAE",
            "low_oil_no_adjust_recognition_accuracy",
            "sample_size",
        ],
    )
    build_figures(rows, validation_rows)
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {VALIDATION_PATH}")
    print(f"Wrote policy-band figures to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
