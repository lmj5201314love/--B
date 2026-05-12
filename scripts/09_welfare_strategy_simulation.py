from __future__ import annotations

import html
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import ensure_project_dirs, format_number, parse_date, parse_float, read_csv_auto, write_csv  # noqa: E402
from src.strategy_utils import ACTION_COL, load_main_sample, simulate_all_strategies  # noqa: E402
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
from src.welfare_loss import format_loss_row  # noqa: E402


INPUT_PATH = ROOT / "data" / "processed" / "modeling_dataset_pass_through.csv"
RESULT_PATH = ROOT / "data" / "processed" / "strategy_simulation_results.csv"
COMPARISON_PATH = ROOT / "outputs" / "tables" / "welfare_strategy_comparison.csv"
FIGURE_DIR = ROOT / "outputs" / "figures"

COMPONENTS = [
    ("consumer_loss_sum", "Consumer", "#4c78a8"),
    ("refinery_loss_sum", "Refinery", "#f58518"),
    ("cpi_loss_sum", "CPI", "#e45756"),
    ("volatility_loss_sum", "Volatility", "#72b7b2"),
    ("security_loss_sum", "Security", "#54a24b"),
]

STRATEGY_COLORS = {
    "S0_current": "#222222",
    "S1_full_pass": "#4c78a8",
    "S2_fixed_70": "#f58518",
    "S3_segmented_smoothing": "#59a14f",
    "S4_grid_best_fixed_lambda": "#b279a2",
    "S5_grid_best_segmented": "#e45756",
}


def format_summary_rows(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for summary in sorted(summaries, key=lambda item: item["total_loss_sum"]):
        formatted = {"strategy": summary["strategy"], "notes": summary["notes"]}
        for column in (
            "total_loss_sum",
            "consumer_loss_sum",
            "refinery_loss_sum",
            "cpi_loss_sum",
            "volatility_loss_sum",
            "security_loss_sum",
            "mean_action",
            "mean_abs_action",
            "max_up_action",
            "max_down_action",
            "no_adjust_rate",
            "final_cumulative_unmet_gap",
        ):
            formatted[column] = format_number(parse_float(summary.get(column)))
        rows.append(formatted)
    return rows


def collect_fieldnames(input_headers: list[str], result_rows: list[dict[str, Any]]) -> list[str]:
    preferred_new = [
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
    fieldnames = list(input_headers)
    for column in preferred_new:
        if column not in fieldnames:
            fieldnames.append(column)
    for row in result_rows:
        for column in row:
            if column not in fieldnames:
                fieldnames.append(column)
    return fieldnames


def bar_chart_total_loss(path: Path, summaries: list[dict[str, Any]]) -> None:
    rows = sorted(summaries, key=lambda item: item["total_loss_sum"])
    values = [parse_float(row["total_loss_sum"]) or 0.0 for row in rows]
    y_min, y_max = extent(values, include_zero=True)
    left = MARGIN_LEFT
    right = WIDTH - MARGIN_RIGHT
    top = MARGIN_TOP
    bottom = HEIGHT - MARGIN_BOTTOM
    lines = svg_header("Total Welfare Loss by Strategy")
    add_axes(lines, y_min, y_max, "Strategy", "Total welfare loss")
    slot = (right - left) / max(len(rows), 1)
    bar_width = min(92, slot * 0.58)
    for index, row in enumerate(rows):
        strategy = row["strategy"]
        value = parse_float(row["total_loss_sum"]) or 0.0
        x_center = left + slot * (index + 0.5)
        y = scale(value, y_min, y_max, bottom, top)
        height = bottom - y
        color = STRATEGY_COLORS.get(strategy, "#4c78a8")
        lines.append(f'<rect x="{x_center - bar_width / 2:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{height:.1f}" fill="{color}" opacity="0.86"/>')
        label = strategy.replace("S", "S ")
        lines.append(
            f'<text x="{x_center:.1f}" y="{bottom + 18}" text-anchor="middle" font-family="Arial" font-size="10">{html.escape(label)}</text>'
        )
        lines.append(
            f'<text x="{x_center:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-family="Arial" font-size="10" fill="#333">{value:.2f}</text>'
        )
    write_svg(path, lines)


def stacked_components_chart(path: Path, summaries: list[dict[str, Any]]) -> None:
    rows = sorted(summaries, key=lambda item: item["total_loss_sum"])
    totals = [
        sum(parse_float(row[column]) or 0.0 for column, _, _ in COMPONENTS)
        for row in rows
    ]
    y_min, y_max = extent(totals, include_zero=True)
    left = MARGIN_LEFT
    right = WIDTH - MARGIN_RIGHT
    top = MARGIN_TOP
    bottom = HEIGHT - MARGIN_BOTTOM
    lines = svg_header("Welfare Loss Components by Strategy")
    add_axes(lines, y_min, y_max, "Strategy", "Component loss sum")
    slot = (right - left) / max(len(rows), 1)
    bar_width = min(92, slot * 0.58)
    for index, row in enumerate(rows):
        x_center = left + slot * (index + 0.5)
        cumulative = 0.0
        for column, _, color in COMPONENTS:
            value = parse_float(row[column]) or 0.0
            y1 = scale(cumulative, y_min, y_max, bottom, top)
            y2 = scale(cumulative + value, y_min, y_max, bottom, top)
            lines.append(
                f'<rect x="{x_center - bar_width / 2:.1f}" y="{y2:.1f}" width="{bar_width:.1f}" height="{abs(y1 - y2):.1f}" fill="{color}" opacity="0.86"/>'
            )
            cumulative += value
        label = row["strategy"].replace("S", "S ")
        lines.append(
            f'<text x="{x_center:.1f}" y="{bottom + 18}" text-anchor="middle" font-family="Arial" font-size="10">{html.escape(label)}</text>'
        )
    add_legend(lines, [(label, color) for _, label, color in COMPONENTS])
    write_svg(path, lines)


def series_for_strategy(
    rows: list[dict[str, Any]],
    strategies: list[str],
    value_col: str,
) -> list[tuple[str, list[tuple[date, float]], str]]:
    output = []
    for strategy in strategies:
        points: list[tuple[date, float]] = []
        for row in rows:
            if row.get("strategy") != strategy:
                continue
            parsed = parse_date(row.get("date", ""))
            value = parse_float(row.get(value_col))
            if parsed is not None and value is not None:
                points.append((parsed, value))
        output.append((strategy, points, STRATEGY_COLORS.get(strategy, "#4c78a8")))
    return output


def build_figures(result_rows: list[dict[str, Any]], summaries: list[dict[str, Any]]) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    bar_chart_total_loss(FIGURE_DIR / "welfare_total_loss_by_strategy.svg", summaries)
    stacked_components_chart(FIGURE_DIR / "welfare_loss_components_by_strategy.svg", summaries)
    action_strategies = [
        "S0_current",
        "S1_full_pass",
        "S3_segmented_smoothing",
        "S5_grid_best_segmented",
    ]
    line_chart_date(
        FIGURE_DIR / "strategy_actions_over_time.svg",
        "Strategy Actions over Time",
        series_for_strategy(result_rows, action_strategies, ACTION_COL),
        "CNY per ton",
    )
    line_chart_date(
        FIGURE_DIR / "cumulative_unmet_gap_by_strategy.svg",
        "Cumulative Unmet Gap by Strategy",
        series_for_strategy(result_rows, list(STRATEGY_COLORS), "cumulative_unmet_gap"),
        "CNY per ton",
    )


def main() -> None:
    ensure_project_dirs(ROOT)
    headers, rows, _ = read_csv_auto(INPUT_PATH)
    main_rows = load_main_sample(rows)
    result_rows, summaries, _ = simulate_all_strategies(main_rows)
    formatted_result_rows = [format_loss_row(row) for row in result_rows]
    write_csv(RESULT_PATH, formatted_result_rows, collect_fieldnames(headers, formatted_result_rows))
    comparison_rows = format_summary_rows(summaries)
    write_csv(
        COMPARISON_PATH,
        comparison_rows,
        [
            "strategy",
            "total_loss_sum",
            "consumer_loss_sum",
            "refinery_loss_sum",
            "cpi_loss_sum",
            "volatility_loss_sum",
            "security_loss_sum",
            "mean_action",
            "mean_abs_action",
            "max_up_action",
            "max_down_action",
            "no_adjust_rate",
            "final_cumulative_unmet_gap",
            "notes",
        ],
    )
    build_figures(result_rows, summaries)
    print(f"Wrote {RESULT_PATH}")
    print(f"Wrote {COMPARISON_PATH}")
    print(f"Wrote welfare strategy figures to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
