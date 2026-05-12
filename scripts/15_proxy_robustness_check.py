from __future__ import annotations

import html
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import (  # noqa: E402
    direction_accuracy,
    ensure_project_dirs,
    format_number,
    linear_regression,
    mae,
    parse_float,
    read_csv_auto,
    rmse,
    sign,
    write_csv,
)
from src.strategy_utils import simulate_all_strategies  # noqa: E402
from src.svg_utils import HEIGHT, MARGIN_BOTTOM, MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, WIDTH, add_axes, extent, scale, svg_header, write_svg  # noqa: E402


INPUT_PATH = ROOT / "data" / "processed" / "modeling_dataset_pass_through.csv"
OUT_TABLE_PATH = ROOT / "outputs" / "tables" / "proxy_robustness_strategy_ranking.csv"
FIGURE_PATH = ROOT / "outputs" / "figures" / "proxy_robustness_s5_vs_current.svg"

PROXY_VARIABLES = [
    "brent_wti_weighted_window_change",
    "brent_wti_avg_window_change",
    "basket_window_change",
    "brent_window_change",
    "wti_window_change",
]


def fit_proxy_model(rows: list[dict[str, str]], proxy: str) -> tuple[float, float, list[float], list[float]]:
    xs: list[float] = []
    ys: list[float] = []
    for row in rows:
        x = parse_float(row.get(proxy))
        y = parse_float(row.get("avg_adjust_cny_per_ton"))
        if x is None or y is None:
            continue
        xs.append(x)
        ys.append(y)
    k, b = linear_regression(xs, ys)
    return k, b, xs, ys


def apply_rule_theory(rows: list[dict[str, str]], proxy: str, k: float, b: float) -> list[dict[str, Any]]:
    output_rows: list[dict[str, Any]] = []
    carry = 0.0
    for row in sorted(rows, key=lambda item: (item.get("date", ""), item.get("notice_date", ""))):
        output = dict(row)
        x = parse_float(row.get(proxy))
        raw = None if x is None else k * x + b
        if raw is None:
            rule = None
        else:
            carry += raw
            if abs(carry) < 50:
                rule = 0.0
            else:
                rule = carry
                carry = 0.0
        actual = parse_float(row.get("avg_adjust_cny_per_ton"))
        output["theory_adjust_raw_cny_per_ton"] = format_number(raw)
        output["theory_adjust_rule_cny_per_ton"] = format_number(rule)
        output["theory_error_rule_cny_per_ton"] = format_number(None if actual is None or rule is None else actual - rule)
        output_rows.append(output)
    return output_rows


def mechanism_metrics(rows: list[dict[str, Any]]) -> tuple[float, float, float]:
    actual_values: list[float] = []
    rule_values: list[float] = []
    for row in rows:
        actual = parse_float(row.get("avg_adjust_cny_per_ton"))
        rule = parse_float(row.get("theory_adjust_rule_cny_per_ton"))
        if actual is None or rule is None:
            continue
        actual_values.append(actual)
        rule_values.append(rule)
    return mae(actual_values, rule_values), rmse(actual_values, rule_values), direction_accuracy(actual_values, rule_values)


def strategy_loss_map(summaries: list[dict[str, Any]]) -> dict[str, float]:
    return {
        summary["strategy"]: parse_float(summary.get("total_loss_sum")) or 0.0
        for summary in summaries
    }


def build_proxy_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output_rows: list[dict[str, object]] = []
    for proxy in PROXY_VARIABLES:
        k, b, _, _ = fit_proxy_model(rows, proxy)
        proxy_rows = apply_rule_theory(rows, proxy, k, b)
        mechanism_mae, mechanism_rmse, mechanism_direction = mechanism_metrics(proxy_rows)
        _, summaries, _ = simulate_all_strategies(proxy_rows)
        losses = strategy_loss_map(summaries)
        best_strategy = min(losses, key=losses.get)
        s0_loss = losses.get("S0_current", 0.0)
        s5_loss = losses.get("S5_grid_best_segmented", 0.0)
        improvement = None if s0_loss == 0 else (s0_loss - s5_loss) / s0_loss * 100
        output_rows.append(
            {
                "proxy_variable": proxy,
                "k": k,
                "b": b,
                "mechanism_MAE": mechanism_mae,
                "mechanism_RMSE": mechanism_rmse,
                "direction_accuracy": mechanism_direction,
                "best_strategy": best_strategy,
                "S1_total_loss": losses.get("S1_full_pass"),
                "S5_total_loss": s5_loss,
                "S0_total_loss": s0_loss,
                "S5_vs_S0_improvement_pct": improvement,
            }
        )
    return output_rows


def build_proxy_figure(rows: list[dict[str, object]]) -> None:
    values = [parse_float(row.get("S5_vs_S0_improvement_pct")) or 0.0 for row in rows]
    y_min, y_max = extent(values, include_zero=True)
    left = MARGIN_LEFT
    right = WIDTH - MARGIN_RIGHT
    top = MARGIN_TOP
    bottom = HEIGHT - MARGIN_BOTTOM
    lines = svg_header("S5 Improvement over Current by Oil Proxy")
    add_axes(lines, y_min, y_max, "Proxy", "S5 vs S0 improvement (%)")
    slot = (right - left) / max(len(rows), 1)
    bar_width = min(130, slot * 0.58)
    for index, row in enumerate(rows):
        value = parse_float(row.get("S5_vs_S0_improvement_pct")) or 0.0
        x_center = left + slot * (index + 0.5)
        y = scale(value, y_min, y_max, bottom, top)
        zero_y = scale(0, y_min, y_max, bottom, top)
        top_y = min(y, zero_y)
        height = abs(zero_y - y)
        color = "#1b9e77" if value >= 0 else "#d95f02"
        label = str(row["proxy_variable"]).replace("_window_change", "").replace("_", " ")
        lines.append(f'<rect x="{x_center - bar_width / 2:.1f}" y="{top_y:.1f}" width="{bar_width:.1f}" height="{height:.1f}" fill="{color}" opacity="0.86"/>')
        lines.append(f'<text x="{x_center:.1f}" y="{bottom + 18}" text-anchor="middle" font-family="Arial" font-size="10">{html.escape(label)}</text>')
        lines.append(f'<text x="{x_center:.1f}" y="{top_y - 6:.1f}" text-anchor="middle" font-family="Arial" font-size="10">{value:.1f}%</text>')
    write_svg(FIGURE_PATH, lines)


def main() -> None:
    ensure_project_dirs(ROOT)
    _, rows, _ = read_csv_auto(INPUT_PATH)
    output_rows = build_proxy_rows(rows)
    formatted_rows = []
    for row in output_rows:
        formatted = {"proxy_variable": row["proxy_variable"], "best_strategy": row["best_strategy"]}
        for column in (
            "k",
            "b",
            "mechanism_MAE",
            "mechanism_RMSE",
            "direction_accuracy",
            "S1_total_loss",
            "S5_total_loss",
            "S0_total_loss",
            "S5_vs_S0_improvement_pct",
        ):
            formatted[column] = format_number(parse_float(row.get(column)))
        formatted_rows.append(formatted)
    write_csv(
        OUT_TABLE_PATH,
        formatted_rows,
        [
            "proxy_variable",
            "k",
            "b",
            "mechanism_MAE",
            "mechanism_RMSE",
            "direction_accuracy",
            "best_strategy",
            "S1_total_loss",
            "S5_total_loss",
            "S0_total_loss",
            "S5_vs_S0_improvement_pct",
        ],
    )
    build_proxy_figure(output_rows)
    print(f"Wrote {OUT_TABLE_PATH}")
    print(f"Wrote {FIGURE_PATH}")


if __name__ == "__main__":
    main()
