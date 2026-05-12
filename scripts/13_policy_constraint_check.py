from __future__ import annotations

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import ensure_project_dirs, format_number, parse_float, read_csv_auto, write_csv  # noqa: E402
from src.robustness_utils import (  # noqa: E402
    group_by_strategy,
    min_max,
    normalize_value,
    standard_deviation,
    STRATEGY_COLORS,
)
from src.svg_utils import HEIGHT, MARGIN_BOTTOM, MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, WIDTH, add_axes, add_legend, extent, scale, svg_header, write_svg  # noqa: E402


INPUT_PATH = ROOT / "data" / "processed" / "strategy_simulation_results.csv"
BASELINE_TABLE_PATH = ROOT / "outputs" / "tables" / "welfare_strategy_comparison.csv"
OUT_TABLE_PATH = ROOT / "outputs" / "tables" / "policy_constraint_comparison.csv"
FIGURE_PATH = ROOT / "outputs" / "figures" / "policy_constraint_comparison.svg"

SCORE_METRICS = [
    "large_up_count",
    "extreme_up_count",
    "max_up_action",
    "action_volatility",
    "cpi_pressure_up_count",
]


def load_baseline_losses() -> dict[str, float]:
    _, rows, _ = read_csv_auto(BASELINE_TABLE_PATH)
    return {
        row["strategy"]: parse_float(row.get("total_loss_sum")) or 0.0
        for row in rows
    }


def build_constraint_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    baseline_losses = load_baseline_losses()
    output_rows: list[dict[str, object]] = []
    for strategy, strategy_rows in group_by_strategy(rows).items():
        actions = [parse_float(row.get("strategy_action_cny_per_ton")) for row in strategy_rows]
        action_values = [value for value in actions if value is not None]
        cpi_pressure_up_count = 0
        for row in strategy_rows:
            cpi = parse_float(row.get("cpi_yoy_pct"))
            action = parse_float(row.get("strategy_action_cny_per_ton"))
            if cpi is not None and action is not None and cpi > 3 and action > 0:
                cpi_pressure_up_count += 1
        no_adjust_count = sum(1 for value in action_values if abs(value) < 1e-9)
        final_gap = parse_float(strategy_rows[-1].get("cumulative_unmet_gap")) if strategy_rows else None
        up_values = [value for value in action_values if value > 0]
        output_rows.append(
            {
                "strategy": strategy,
                "large_up_count": sum(1 for value in action_values if value >= 300),
                "extreme_up_count": sum(1 for value in action_values if value >= 800),
                "max_up_action": max(up_values) if up_values else 0.0,
                "action_volatility": standard_deviation(action_values),
                "cpi_pressure_up_count": cpi_pressure_up_count,
                "no_adjust_rate": no_adjust_count / len(action_values) if action_values else None,
                "final_cumulative_unmet_gap": final_gap,
                "total_loss_baseline": baseline_losses.get(strategy),
            }
        )

    bounds = {
        metric: min_max([parse_float(row.get(metric)) or 0.0 for row in output_rows])
        for metric in SCORE_METRICS
    }
    for row in output_rows:
        score = 0.0
        for metric in SCORE_METRICS:
            low, high = bounds[metric]
            score += 0.2 * normalize_value(parse_float(row.get(metric)) or 0.0, low, high)
        row["policy_acceptability_score"] = score
    output_rows.sort(key=lambda item: item["policy_acceptability_score"])
    return output_rows


def build_policy_figure(rows: list[dict[str, object]]) -> None:
    rows = sorted(rows, key=lambda item: item["policy_acceptability_score"])
    values = [parse_float(row.get("policy_acceptability_score")) or 0.0 for row in rows]
    y_min, y_max = extent(values, include_zero=True)
    left = MARGIN_LEFT
    right = WIDTH - MARGIN_RIGHT
    top = MARGIN_TOP
    bottom = HEIGHT - MARGIN_BOTTOM
    lines = svg_header("Policy Acceptability Score by Strategy")
    add_axes(lines, y_min, y_max, "Strategy", "Policy acceptability score")
    slot = (right - left) / max(len(rows), 1)
    bar_width = min(92, slot * 0.58)
    for index, row in enumerate(rows):
        strategy = row["strategy"]
        value = parse_float(row.get("policy_acceptability_score")) or 0.0
        x_center = left + slot * (index + 0.5)
        y = scale(value, y_min, y_max, bottom, top)
        color = STRATEGY_COLORS.get(strategy, "#4c78a8")
        lines.append(f'<rect x="{x_center - bar_width / 2:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bottom - y:.1f}" fill="{color}" opacity="0.86"/>')
        lines.append(f'<text x="{x_center:.1f}" y="{bottom + 18}" text-anchor="middle" font-family="Arial" font-size="10">{html.escape(strategy)}</text>')
        lines.append(f'<text x="{x_center:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-family="Arial" font-size="10">{value:.2f}</text>')
    add_legend(lines, [("lower is better", "#666666")])
    write_svg(FIGURE_PATH, lines)


def main() -> None:
    ensure_project_dirs(ROOT)
    _, rows, _ = read_csv_auto(INPUT_PATH)
    output_rows = build_constraint_rows(rows)
    formatted_rows = []
    for row in output_rows:
        formatted = {"strategy": row["strategy"]}
        for column in (
            "large_up_count",
            "extreme_up_count",
            "max_up_action",
            "action_volatility",
            "cpi_pressure_up_count",
            "no_adjust_rate",
            "final_cumulative_unmet_gap",
            "total_loss_baseline",
            "policy_acceptability_score",
        ):
            formatted[column] = format_number(parse_float(row.get(column)))
        formatted_rows.append(formatted)
    write_csv(
        OUT_TABLE_PATH,
        formatted_rows,
        [
            "strategy",
            "large_up_count",
            "extreme_up_count",
            "max_up_action",
            "action_volatility",
            "cpi_pressure_up_count",
            "no_adjust_rate",
            "final_cumulative_unmet_gap",
            "total_loss_baseline",
            "policy_acceptability_score",
        ],
    )
    build_policy_figure(output_rows)
    print(f"Wrote {OUT_TABLE_PATH}")
    print(f"Wrote {FIGURE_PATH}")


if __name__ == "__main__":
    main()
