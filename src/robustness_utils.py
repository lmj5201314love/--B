from __future__ import annotations

import html
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.data_utils import format_number, parse_float, write_csv
from src.svg_utils import (
    HEIGHT,
    MARGIN_BOTTOM,
    MARGIN_LEFT,
    MARGIN_RIGHT,
    MARGIN_TOP,
    WIDTH,
    add_axes,
    add_legend,
    extent,
    scale,
    svg_header,
    write_svg,
)


BASELINE_WEIGHTS = {
    "consumer": 0.25,
    "refinery": 0.20,
    "cpi": 0.25,
    "volatility": 0.15,
    "security": 0.15,
}

LOSS_COMPONENTS = [
    ("consumer", "consumer_loss_raw", "consumer_loss", "#4c78a8"),
    ("refinery", "refinery_loss_raw", "refinery_loss", "#f58518"),
    ("cpi", "cpi_loss_raw", "cpi_loss", "#e45756"),
    ("volatility", "volatility_loss_raw", "volatility_loss", "#72b7b2"),
    ("security", "security_loss_raw", "security_loss", "#54a24b"),
]

STRATEGY_COLORS = {
    "S0_current": "#222222",
    "S1_full_pass": "#4c78a8",
    "S2_fixed_70": "#f58518",
    "S3_segmented_smoothing": "#59a14f",
    "S4_grid_best_fixed_lambda": "#b279a2",
    "S5_grid_best_segmented": "#e45756",
}


def group_by_strategy(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("strategy", ""))].append(row)
    for strategy_rows in grouped.values():
        strategy_rows.sort(key=lambda item: (item.get("date", ""), item.get("notice_date", "")))
    return dict(grouped)


def min_max(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    return min(values), max(values)


def normalize_value(value: float | None, low: float, high: float) -> float:
    if value is None or high == low:
        return 0.0
    return (value - low) / (high - low)


def ensure_raw_losses(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure the strategy long table has raw loss columns.

    Existing values are preserved. Missing values are recomputed by strategy using
    strategy_action_cny_per_ton and theory_adjust_rule_cny_per_ton.
    """
    raw_columns = [raw_col for _, raw_col, _, _ in LOSS_COMPONENTS]
    if all(all(str(row.get(col, "")).strip() for col in raw_columns) for row in rows):
        return [dict(row) for row in rows]

    output_rows = [dict(row) for row in rows]
    grouped = group_by_strategy(output_rows)
    for strategy_rows in grouped.values():
        previous_action: float | None = None
        cumulative_unmet_gap = 0.0
        for row in strategy_rows:
            action = parse_float(row.get("strategy_action_cny_per_ton")) or 0.0
            theory = parse_float(row.get("theory_adjust_rule_cny_per_ton")) or 0.0
            cpi = parse_float(row.get("cpi_yoy_pct"))
            cpi_pressure_factor = 1.0 if cpi is None else 1.0 + max(cpi, 0.0) / 5.0
            unmet_gap = theory - action
            cumulative_unmet_gap += unmet_gap
            volatility_base = 0.0 if previous_action is None else action - previous_action
            row["consumer_loss_raw"] = max(action, 0.0) ** 2
            row["refinery_loss_raw"] = unmet_gap**2
            row["cpi_loss_raw"] = max(action, 0.0) ** 2 * cpi_pressure_factor
            row["volatility_loss_raw"] = volatility_base**2
            row["unmet_gap"] = unmet_gap
            row["cumulative_unmet_gap"] = cumulative_unmet_gap
            row["security_loss_raw"] = cumulative_unmet_gap**2
            previous_action = action
    return output_rows


def summarize_strategy_loss(
    rows: list[dict[str, Any]],
    total_col: str,
    component_cols: dict[str, str],
) -> list[dict[str, Any]]:
    summary_rows: list[dict[str, Any]] = []
    for strategy, strategy_rows in group_by_strategy(rows).items():
        actions = [parse_float(row.get("strategy_action_cny_per_ton")) for row in strategy_rows]
        action_values = [value for value in actions if value is not None]
        up_values = [value for value in action_values if value > 0]
        down_values = [value for value in action_values if value < 0]
        no_adjust_count = sum(1 for value in action_values if abs(value) < 1e-9)
        final_gap = parse_float(strategy_rows[-1].get("cumulative_unmet_gap")) if strategy_rows else None
        summary_rows.append(
            {
                "strategy": strategy,
                "total_loss_sum": sum(parse_float(row.get(total_col)) or 0.0 for row in strategy_rows),
                "consumer_loss_sum": sum(parse_float(row.get(component_cols["consumer"])) or 0.0 for row in strategy_rows),
                "refinery_loss_sum": sum(parse_float(row.get(component_cols["refinery"])) or 0.0 for row in strategy_rows),
                "cpi_loss_sum": sum(parse_float(row.get(component_cols["cpi"])) or 0.0 for row in strategy_rows),
                "volatility_loss_sum": sum(parse_float(row.get(component_cols["volatility"])) or 0.0 for row in strategy_rows),
                "security_loss_sum": sum(parse_float(row.get(component_cols["security"])) or 0.0 for row in strategy_rows),
                "mean_abs_action": sum(abs(value) for value in action_values) / len(action_values) if action_values else None,
                "max_up_action": max(up_values) if up_values else None,
                "max_down_action": min(down_values) if down_values else None,
                "no_adjust_rate": no_adjust_count / len(action_values) if action_values else None,
                "final_cumulative_unmet_gap": final_gap,
            }
        )
    summary_rows.sort(key=lambda item: item["total_loss_sum"])
    for rank, row in enumerate(summary_rows, start=1):
        row["rank"] = rank
    return summary_rows


def format_summary_rows(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    formatted_rows: list[dict[str, Any]] = []
    for row in summary_rows:
        formatted = {"strategy": row["strategy"], "rank": row.get("rank", "")}
        for column in (
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
            "final_cumulative_unmet_gap",
        ):
            formatted[column] = format_number(parse_float(row.get(column)))
        formatted_rows.append(formatted)
    return formatted_rows


def write_summary_csv(path: Path, summary_rows: list[dict[str, Any]]) -> None:
    write_csv(
        path,
        format_summary_rows(summary_rows),
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
            "final_cumulative_unmet_gap",
            "rank",
        ],
    )


def total_loss_bar_chart(path: Path, summary_rows: list[dict[str, Any]], title: str) -> None:
    rows = sorted(summary_rows, key=lambda item: item["total_loss_sum"])
    values = [parse_float(row.get("total_loss_sum")) or 0.0 for row in rows]
    y_min, y_max = extent(values, include_zero=True)
    left = MARGIN_LEFT
    right = WIDTH - MARGIN_RIGHT
    top = MARGIN_TOP
    bottom = HEIGHT - MARGIN_BOTTOM
    lines = svg_header(title)
    add_axes(lines, y_min, y_max, "Strategy", "Total loss")
    slot = (right - left) / max(len(rows), 1)
    bar_width = min(92, slot * 0.58)
    for index, row in enumerate(rows):
        strategy = row["strategy"]
        value = parse_float(row.get("total_loss_sum")) or 0.0
        x_center = left + slot * (index + 0.5)
        y = scale(value, y_min, y_max, bottom, top)
        color = STRATEGY_COLORS.get(strategy, "#4c78a8")
        lines.append(f'<rect x="{x_center - bar_width / 2:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bottom - y:.1f}" fill="{color}" opacity="0.86"/>')
        lines.append(f'<text x="{x_center:.1f}" y="{bottom + 18}" text-anchor="middle" font-family="Arial" font-size="10">{html.escape(strategy)}</text>')
        lines.append(f'<text x="{x_center:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-family="Arial" font-size="10">{value:.2f}</text>')
    write_svg(path, lines)


def component_stacked_bar_chart(path: Path, summary_rows: list[dict[str, Any]], title: str) -> None:
    rows = sorted(summary_rows, key=lambda item: item["total_loss_sum"])
    component_keys = [
        ("consumer_loss_sum", "Consumer", "#4c78a8"),
        ("refinery_loss_sum", "Refinery", "#f58518"),
        ("cpi_loss_sum", "CPI", "#e45756"),
        ("volatility_loss_sum", "Volatility", "#72b7b2"),
        ("security_loss_sum", "Security", "#54a24b"),
    ]
    totals = [sum(parse_float(row.get(key)) or 0.0 for key, _, _ in component_keys) for row in rows]
    y_min, y_max = extent(totals, include_zero=True)
    left = MARGIN_LEFT
    right = WIDTH - MARGIN_RIGHT
    top = MARGIN_TOP
    bottom = HEIGHT - MARGIN_BOTTOM
    lines = svg_header(title)
    add_axes(lines, y_min, y_max, "Strategy", "Component loss")
    slot = (right - left) / max(len(rows), 1)
    bar_width = min(92, slot * 0.58)
    for index, row in enumerate(rows):
        x_center = left + slot * (index + 0.5)
        cumulative = 0.0
        for key, _, color in component_keys:
            value = parse_float(row.get(key)) or 0.0
            y1 = scale(cumulative, y_min, y_max, bottom, top)
            y2 = scale(cumulative + value, y_min, y_max, bottom, top)
            lines.append(f'<rect x="{x_center - bar_width / 2:.1f}" y="{y2:.1f}" width="{bar_width:.1f}" height="{abs(y1 - y2):.1f}" fill="{color}" opacity="0.86"/>')
            cumulative += value
        lines.append(f'<text x="{x_center:.1f}" y="{bottom + 18}" text-anchor="middle" font-family="Arial" font-size="10">{html.escape(row["strategy"])}</text>')
    add_legend(lines, [(label, color) for _, label, color in component_keys])
    write_svg(path, lines)


def standard_deviation(values: list[float]) -> float | None:
    if not values:
        return None
    avg = sum(values) / len(values)
    if len(values) == 1:
        return 0.0
    return math.sqrt(sum((value - avg) ** 2 for value in values) / (len(values) - 1))
