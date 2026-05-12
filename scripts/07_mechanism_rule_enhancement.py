from __future__ import annotations

import sys
from pathlib import Path

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
from src.svg_utils import line_chart_date, scatter_chart  # noqa: E402


MODEL_DATA_PATH = ROOT / "data" / "processed" / "modeling_dataset.csv"
BASELINE_PATH = ROOT / "outputs" / "tables" / "mechanism_baseline_comparison.csv"
OUT_PATH = ROOT / "data" / "processed" / "modeling_dataset_mechanism.csv"
VALIDATION_PATH = ROOT / "outputs" / "tables" / "mechanism_rule_validation.csv"
FIGURE_DIR = ROOT / "outputs" / "figures"

START_DATE = parse_date("2016-01-01")
END_DATE = parse_date("2026-05-09")
MAIN_PROXY = "brent_wti_weighted_window_change"
THRESHOLD_CNY_PER_TON = 50.0


def direction_label(value: float | None) -> str:
    value_sign = sign(value)
    if value_sign > 0:
        return "up"
    if value_sign < 0:
        return "down"
    return "no_adjust"


def is_adjusted(value: float | None) -> int:
    return 1 if value is not None and abs(value) > 1e-9 else 0


def load_selected_coefficients() -> tuple[float, float]:
    _, rows, _ = read_csv_auto(BASELINE_PATH)
    selected = None
    for row in rows:
        if row.get("proxy_variable") == MAIN_PROXY and row.get("is_selected_proxy") == "1":
            selected = row
            break
    if selected is None:
        for row in rows:
            if row.get("proxy_variable") == MAIN_PROXY:
                selected = row
                break
    if selected is None:
        raise ValueError(f"Cannot find baseline coefficients for {MAIN_PROXY}.")
    k = parse_float(selected.get("k"))
    b = parse_float(selected.get("b"))
    if k is None or b is None:
        raise ValueError(f"Invalid baseline coefficients for {MAIN_PROXY}: {selected}")
    return k, b


def in_main_sample(row: dict[str, str]) -> bool:
    parsed = parse_date(row.get("date", ""))
    return parsed is not None and START_DATE is not None and END_DATE is not None and START_DATE <= parsed <= END_DATE


def build_mechanism_rows() -> tuple[list[str], list[dict[str, object]]]:
    headers, rows, _ = read_csv_auto(MODEL_DATA_PATH)
    k, b = load_selected_coefficients()
    main_rows = [row for row in rows if in_main_sample(row)]
    main_rows.sort(key=lambda item: (item.get("date", ""), item.get("notice_date", "")))

    carry = 0.0
    output_rows: list[dict[str, object]] = []
    for row in main_rows:
        output: dict[str, object] = dict(row)
        oil_change = parse_float(row.get(MAIN_PROXY))
        actual_adjust = parse_float(row.get("avg_adjust_cny_per_ton"))
        raw_theory = None if oil_change is None else k * oil_change + b

        if raw_theory is None:
            carry_before = carry
            rule_theory = None
            carry_after = carry
        else:
            carry += raw_theory
            carry_before = carry
            if abs(carry) < THRESHOLD_CNY_PER_TON:
                rule_theory = 0.0
                carry_after = carry
            else:
                rule_theory = carry
                carry = 0.0
                carry_after = carry

        raw_error = None if actual_adjust is None or raw_theory is None else actual_adjust - raw_theory
        rule_error = None if actual_adjust is None or rule_theory is None else actual_adjust - rule_theory
        output.update(
            {
                "theory_adjust_raw_cny_per_ton": format_number(raw_theory),
                "carry_before_decision_cny_per_ton": format_number(carry_before),
                "theory_adjust_rule_cny_per_ton": format_number(rule_theory),
                "carry_after_decision_cny_per_ton": format_number(carry_after),
                "theory_error_raw_cny_per_ton": format_number(raw_error),
                "theory_error_rule_cny_per_ton": format_number(rule_error),
                "theory_direction_raw": direction_label(raw_theory),
                "theory_direction_rule": direction_label(rule_theory),
                "actual_direction": direction_label(actual_adjust),
                "is_theory_adjusted_rule": is_adjusted(rule_theory),
                "is_actual_adjusted": is_adjusted(actual_adjust),
            }
        )
        output_rows.append(output)

    new_fields = [
        "theory_adjust_raw_cny_per_ton",
        "carry_before_decision_cny_per_ton",
        "theory_adjust_rule_cny_per_ton",
        "carry_after_decision_cny_per_ton",
        "theory_error_raw_cny_per_ton",
        "theory_error_rule_cny_per_ton",
        "theory_direction_raw",
        "theory_direction_rule",
        "actual_direction",
        "is_theory_adjusted_rule",
        "is_actual_adjusted",
    ]
    return headers + [field for field in new_fields if field not in headers], output_rows


def rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def evaluate_model(rows: list[dict[str, object]], model_name: str, pred_col: str, group_name: str) -> dict[str, object]:
    actual_values: list[float] = []
    predicted_values: list[float] = []
    valid_rows: list[dict[str, object]] = []
    for row in rows:
        actual = parse_float(row.get("avg_adjust_cny_per_ton"))
        predicted = parse_float(row.get(pred_col))
        if actual is None or predicted is None:
            continue
        actual_values.append(actual)
        predicted_values.append(predicted)
        valid_rows.append(row)

    actual_adjust_flags = [is_adjusted(value) for value in actual_values]
    predicted_adjust_flags = [is_adjusted(value) for value in predicted_values]
    up_rows = [(actual, predicted) for actual, predicted in zip(actual_values, predicted_values) if actual > 0]
    down_rows = [(actual, predicted) for actual, predicted in zip(actual_values, predicted_values) if actual < 0]
    no_adjust_rows = [(actual, predicted) for actual, predicted in zip(actual_values, predicted_values) if actual == 0]

    return {
        "sample_group": group_name,
        "model": model_name,
        "MAE": format_number(mae(actual_values, predicted_values) if actual_values else None),
        "RMSE": format_number(rmse(actual_values, predicted_values) if actual_values else None),
        "direction_accuracy": format_number(direction_accuracy(actual_values, predicted_values) if actual_values else None),
        "adjustment_accuracy": format_number(
            rate(sum(a == p for a, p in zip(actual_adjust_flags, predicted_adjust_flags)), len(actual_adjust_flags))
        ),
        "up_direction_accuracy": format_number(rate(sum(sign(pred) == 1 for _, pred in up_rows), len(up_rows))),
        "down_direction_accuracy": format_number(rate(sum(sign(pred) == -1 for _, pred in down_rows), len(down_rows))),
        "no_adjust_recognition_accuracy": format_number(
            rate(sum(sign(pred) == 0 for _, pred in no_adjust_rows), len(no_adjust_rows))
        ),
        "sample_size": len(valid_rows),
    }


def build_validation_table(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    adjusted_rows = [row for row in rows if parse_float(row.get("avg_adjust_cny_per_ton")) not in (None, 0.0)]
    no_adjust_rows = [row for row in rows if parse_float(row.get("avg_adjust_cny_per_ton")) == 0.0]
    groups = [
        ("main_sample_2016_onward", rows),
        ("actual_adjusted_windows", adjusted_rows),
        ("actual_no_adjust_windows", no_adjust_rows),
    ]
    validation_rows: list[dict[str, object]] = []
    for group_name, group_rows in groups:
        validation_rows.append(evaluate_model(group_rows, "raw_linear", "theory_adjust_raw_cny_per_ton", group_name))
        validation_rows.append(evaluate_model(group_rows, "rule_threshold_carry", "theory_adjust_rule_cny_per_ton", group_name))
    return validation_rows


def build_figures(rows: list[dict[str, object]]) -> None:
    date_series = []
    for label, column, color in (
        ("Actual", "avg_adjust_cny_per_ton", "#222222"),
        ("Raw theory", "theory_adjust_raw_cny_per_ton", "#4c78a8"),
        ("Rule theory", "theory_adjust_rule_cny_per_ton", "#e45756"),
    ):
        points = []
        for row in rows:
            parsed = parse_date(row.get("date", ""))
            value = parse_float(row.get(column))
            if parsed is not None and value is not None:
                points.append((parsed, value))
        date_series.append((label, points, color))
    line_chart_date(
        FIGURE_DIR / "theory_vs_actual_adjust.svg",
        "Theory vs Actual Fuel Adjustment",
        date_series,
        "CNY per ton",
    )

    scatter_points = []
    for row in rows:
        x_value = parse_float(row.get("theory_adjust_rule_cny_per_ton"))
        y_value = parse_float(row.get("avg_adjust_cny_per_ton"))
        if x_value is not None and y_value is not None:
            scatter_points.append((x_value, y_value, "all windows"))
    scatter_chart(
        FIGURE_DIR / "theory_actual_scatter.svg",
        "Rule Theory vs Actual Adjustment",
        scatter_points,
        "Rule theory adjustment (CNY per ton)",
        "Actual adjustment (CNY per ton)",
        {"all windows": "#4c78a8"},
        draw_equal_line=True,
    )


def main() -> None:
    ensure_project_dirs(ROOT)
    fieldnames, rows = build_mechanism_rows()
    write_csv(OUT_PATH, rows, fieldnames)
    validation_rows = build_validation_table(rows)
    write_csv(
        VALIDATION_PATH,
        validation_rows,
        [
            "sample_group",
            "model",
            "MAE",
            "RMSE",
            "direction_accuracy",
            "adjustment_accuracy",
            "up_direction_accuracy",
            "down_direction_accuracy",
            "no_adjust_recognition_accuracy",
            "sample_size",
        ],
    )
    build_figures(rows)
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {VALIDATION_PATH}")
    print(f"Wrote mechanism figures to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
