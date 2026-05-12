from __future__ import annotations

import html
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import ensure_project_dirs, format_number, parse_date, parse_float, read_csv_auto, write_csv  # noqa: E402
from src.strategy_utils import ACTION_COL, threshold_action  # noqa: E402
from src.svg_utils import (  # noqa: E402
    HEIGHT,
    MARGIN_BOTTOM,
    MARGIN_LEFT,
    MARGIN_RIGHT,
    MARGIN_TOP,
    WIDTH,
    add_axes,
    add_legend,
    extent,
    line_chart_date,
    scale,
    svg_header,
    write_svg,
)
from src.welfare_loss import compute_loss_components, compute_total_welfare_loss, format_loss_row  # noqa: E402


INPUT_PATH = ROOT / "data" / "processed" / "modeling_dataset_policy_band.csv"
OUT_DATA_PATH = ROOT / "data" / "processed" / "policy_constrained_strategy_results.csv"
OUT_TABLE_PATH = ROOT / "outputs" / "tables" / "policy_constrained_strategy_comparison.csv"
FIGURE_DIR = ROOT / "outputs" / "figures"
THEORY_COL = "theory_adjust_band_rule_cny_per_ton"

STRATEGY_COLORS = {
    "S0_current": "#222222",
    "S1_full_pass_policy_band": "#4c78a8",
    "S5_segmented_policy_band": "#59a14f",
    "S6_policy_acceptability_rule": "#e45756",
}

COMPONENTS = [
    ("consumer_loss_sum", "Consumer", "#4c78a8"),
    ("refinery_loss_sum", "Refinery", "#f58518"),
    ("cpi_loss_sum", "CPI", "#e45756"),
    ("volatility_loss_sum", "Volatility", "#72b7b2"),
    ("security_loss_sum", "Security", "#54a24b"),
]


def segmented_policy_action(theory: float, large_lambda: float = 0.65) -> float:
    abs_theory = abs(theory)
    if abs_theory < 50:
        return 0.0
    if abs_theory < 300:
        return threshold_action(0.9 * theory)
    if abs_theory < 800:
        return threshold_action(0.8 * theory)
    if abs_theory < 1500:
        return threshold_action(large_lambda * theory)
    return threshold_action(0.4 * theory)


def acceptability_action(row: dict[str, Any]) -> float:
    theory = parse_float(row.get(THEORY_COL)) or 0.0
    action = segmented_policy_action(theory)
    cpi = parse_float(row.get("cpi_yoy_pct"))
    if cpi is not None and cpi > 3 and action > 300:
        action = min(action, 300.0)
    if action > 800:
        action = 800.0
    if action < -800:
        action = -800.0
    return threshold_action(action)


def apply_strategy(rows: list[dict[str, Any]], strategy: str, action_values: list[float], notes: str) -> list[dict[str, Any]]:
    strategy_rows = []
    for row, action in zip(rows, action_values):
        output = dict(row)
        output["strategy"] = strategy
        output[ACTION_COL] = action
        output["strategy_notes"] = notes
        strategy_rows.append(output)
    loss_rows = compute_loss_components(strategy_rows, ACTION_COL, THEORY_COL)
    return compute_total_welfare_loss(loss_rows)


def summarize_strategy(strategy_rows: list[dict[str, Any]]) -> dict[str, Any]:
    strategy = str(strategy_rows[0].get("strategy", "")) if strategy_rows else ""
    actions = [parse_float(row.get(ACTION_COL)) for row in strategy_rows]
    action_values = [value for value in actions if value is not None]
    up_values = [value for value in action_values if value > 0]
    down_values = [value for value in action_values if value < 0]
    total = lambda col: sum(parse_float(row.get(col)) or 0.0 for row in strategy_rows)
    final_gap = parse_float(strategy_rows[-1].get("cumulative_unmet_gap")) if strategy_rows else None
    return {
        "strategy": strategy,
        "total_loss_sum": total("total_loss"),
        "consumer_loss_sum": total("consumer_loss"),
        "refinery_loss_sum": total("refinery_loss"),
        "cpi_loss_sum": total("cpi_loss"),
        "volatility_loss_sum": total("volatility_loss"),
        "security_loss_sum": total("security_loss"),
        "mean_abs_action": sum(abs(value) for value in action_values) / len(action_values) if action_values else None,
        "max_up_action": max(up_values) if up_values else None,
        "max_down_action": min(down_values) if down_values else None,
        "no_adjust_rate": sum(1 for value in action_values if abs(value) < 1e-9) / len(action_values) if action_values else None,
        "large_up_count": sum(1 for value in action_values if value >= 300),
        "extreme_up_count": sum(1 for value in action_values if value >= 800),
        "final_cumulative_unmet_gap": final_gap,
    }


def simulate(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    all_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    strategy_specs = [
        (
            "S0_current",
            [parse_float(row.get("avg_adjust_cny_per_ton")) or 0.0 for row in rows],
            "actual historical adjustment",
        ),
        (
            "S1_full_pass_policy_band",
            [parse_float(row.get(THEORY_COL)) or 0.0 for row in rows],
            "full pass-through after 40/80/130 policy bands",
        ),
        (
            "S5_segmented_policy_band",
            [segmented_policy_action(parse_float(row.get(THEORY_COL)) or 0.0) for row in rows],
            "segmented smoothing after policy bands",
        ),
        (
            "S6_policy_acceptability_rule",
            [acceptability_action(row) for row in rows],
            "S5 plus CPI/high-adjustment caps",
        ),
    ]
    for strategy, actions, notes in strategy_specs:
        strategy_rows = apply_strategy(rows, strategy, actions, notes)
        all_rows.extend(strategy_rows)
        summaries.append(summarize_strategy(strategy_rows))
    summaries.sort(key=lambda item: item["total_loss_sum"])
    return all_rows, summaries


def write_outputs(headers: list[str], rows: list[dict[str, Any]], summaries: list[dict[str, Any]]) -> None:
    new_fields = [
        "strategy",
        ACTION_COL,
        "strategy_notes",
        "consumer_loss_raw",
        "refinery_loss_raw",
        "cpi_loss_raw",
        "volatility_loss_raw",
        "unmet_gap",
        "cumulative_unmet_gap",
        "security_loss_raw",
        "consumer_loss",
        "refinery_loss",
        "cpi_loss",
        "volatility_loss",
        "security_loss",
        "total_loss",
    ]
    write_csv(OUT_DATA_PATH, [format_loss_row(row) for row in rows], headers + [field for field in new_fields if field not in headers])
    summary_rows = []
    for row in summaries:
        summary_rows.append({key: (format_number(parse_float(value)) if key != "strategy" else value) for key, value in row.items()})
    write_csv(
        OUT_TABLE_PATH,
        summary_rows,
        [
            "strategy",
            "total_loss_sum",
            "consumer_loss_sum",
            "refinery_loss_sum",
            "cpi_loss_sum",
            "volatility_loss_sum",
            "security_loss_sum",
            "mean_abs_action",
            "max_up_action",
            "max_down_action",
            "no_adjust_rate",
            "large_up_count",
            "extreme_up_count",
            "final_cumulative_unmet_gap",
        ],
    )


def total_bar_chart(path: Path, summaries: list[dict[str, Any]], value_col: str, title: str, y_label: str) -> None:
    values = [parse_float(row.get(value_col)) or 0.0 for row in summaries]
    y_min, y_max = extent(values, include_zero=True)
    left = MARGIN_LEFT
    right = WIDTH - MARGIN_RIGHT
    top = MARGIN_TOP
    bottom = HEIGHT - MARGIN_BOTTOM
    lines = svg_header(title)
    add_axes(lines, y_min, y_max, "Strategy", y_label)
    slot = (right - left) / max(len(summaries), 1)
    bar_width = min(125, slot * 0.58)
    for index, row in enumerate(summaries):
        value = parse_float(row.get(value_col)) or 0.0
        x_center = left + slot * (index + 0.5)
        y = scale(value, y_min, y_max, bottom, top)
        strategy = row["strategy"]
        color = STRATEGY_COLORS.get(strategy, "#4c78a8")
        lines.append(f'<rect x="{x_center - bar_width / 2:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bottom - y:.1f}" fill="{color}" opacity="0.86"/>')
        lines.append(f'<text x="{x_center:.1f}" y="{bottom + 18}" text-anchor="middle" font-family="Arial" font-size="10">{html.escape(strategy)}</text>')
        lines.append(f'<text x="{x_center:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-family="Arial" font-size="10">{value:.2f}</text>')
    write_svg(path, lines)


def component_chart(path: Path, summaries: list[dict[str, Any]]) -> None:
    totals = [sum(parse_float(row.get(col)) or 0.0 for col, _, _ in COMPONENTS) for row in summaries]
    y_min, y_max = extent(totals, include_zero=True)
    left = MARGIN_LEFT
    right = WIDTH - MARGIN_RIGHT
    top = MARGIN_TOP
    bottom = HEIGHT - MARGIN_BOTTOM
    lines = svg_header("Policy-constrained Loss Components")
    add_axes(lines, y_min, y_max, "Strategy", "Component loss")
    slot = (right - left) / max(len(summaries), 1)
    bar_width = min(125, slot * 0.58)
    for index, row in enumerate(summaries):
        x_center = left + slot * (index + 0.5)
        cumulative = 0.0
        for col, _, color in COMPONENTS:
            value = parse_float(row.get(col)) or 0.0
            y1 = scale(cumulative, y_min, y_max, bottom, top)
            y2 = scale(cumulative + value, y_min, y_max, bottom, top)
            lines.append(f'<rect x="{x_center - bar_width / 2:.1f}" y="{y2:.1f}" width="{bar_width:.1f}" height="{abs(y1-y2):.1f}" fill="{color}" opacity="0.86"/>')
            cumulative += value
        lines.append(f'<text x="{x_center:.1f}" y="{bottom + 18}" text-anchor="middle" font-family="Arial" font-size="10">{html.escape(row["strategy"])}</text>')
    add_legend(lines, [(label, color) for _, label, color in COMPONENTS])
    write_svg(path, lines)


def action_series(rows: list[dict[str, Any]]) -> None:
    series = []
    for strategy, color in STRATEGY_COLORS.items():
        points = []
        for row in rows:
            if row.get("strategy") != strategy:
                continue
            parsed = parse_date(row.get("date", ""))
            action = parse_float(row.get(ACTION_COL))
            if parsed is not None and action is not None:
                points.append((parsed, action))
        series.append((strategy, points, color))
    line_chart_date(
        FIGURE_DIR / "policy_constrained_actions_over_time.svg",
        "Policy-constrained Strategy Actions over Time",
        series,
        "CNY per ton",
    )


def build_figures(rows: list[dict[str, Any]], summaries: list[dict[str, Any]]) -> None:
    total_bar_chart(FIGURE_DIR / "policy_constrained_total_loss.svg", summaries, "total_loss_sum", "Policy-constrained Total Loss", "Total loss")
    component_chart(FIGURE_DIR / "policy_constrained_loss_components.svg", summaries)
    action_series(rows)
    total_bar_chart(FIGURE_DIR / "policy_constrained_large_up_count.svg", summaries, "large_up_count", "Large Up-count by Policy Strategy", "Count of action >= 300")


def main() -> None:
    ensure_project_dirs(ROOT)
    headers, rows, _ = read_csv_auto(INPUT_PATH)
    rows.sort(key=lambda item: (item.get("date", ""), item.get("notice_date", "")))
    result_rows, summaries = simulate(rows)
    write_outputs(headers, result_rows, summaries)
    build_figures(result_rows, summaries)
    print(f"Wrote {OUT_DATA_PATH}")
    print(f"Wrote {OUT_TABLE_PATH}")
    print(f"Wrote policy-constrained figures to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
