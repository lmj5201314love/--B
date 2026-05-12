from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import ensure_project_dirs, format_number, parse_float, read_csv_auto, write_csv  # noqa: E402
from src.svg_utils import HEIGHT, MARGIN_BOTTOM, MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, WIDTH, add_axes, extent, scale, svg_header, write_svg  # noqa: E402


COMPARISON_PATH = ROOT / "outputs" / "tables" / "welfare_strategy_comparison.csv"
SENSITIVITY_PATH = ROOT / "outputs" / "tables" / "welfare_sensitivity_ranking.csv"
STRATEGY_RESULTS_PATH = ROOT / "data" / "processed" / "strategy_simulation_results.csv"
OUT_TABLE_PATH = ROOT / "outputs" / "tables" / "simplified_policy_rule.csv"
FIGURE_PATH = ROOT / "outputs" / "figures" / "simplified_policy_rule_curve.svg"


def parse_s5_baseline_note() -> dict[str, float]:
    _, rows, _ = read_csv_auto(COMPARISON_PATH)
    for row in rows:
        if row.get("strategy") == "S5_grid_best_segmented":
            note = row.get("notes", "")
            values = {}
            for key in ("small", "medium", "large", "extreme"):
                match = re.search(rf"{key}=([0-9.]+)", note)
                if match:
                    values[key] = float(match.group(1))
            return values
    return {}


def s5_frequency_summary() -> dict[str, Counter[str]]:
    _, rows, _ = read_csv_auto(SENSITIVITY_PATH)
    counters = {
        "small": Counter(),
        "medium": Counter(),
        "large": Counter(),
        "extreme": Counter(),
    }
    for row in rows:
        if row.get("strategy") != "S5_grid_best_segmented":
            continue
        counters["small"][row.get("best_lambda_small", "")] += 1
        counters["medium"][row.get("best_lambda_medium", "")] += 1
        counters["large"][row.get("best_lambda_large", "")] += 1
        counters["extreme"][row.get("best_lambda_extreme", "")] += 1
    return counters


def format_counter(counter: Counter[str]) -> str:
    total = sum(counter.values())
    parts = [f"{key}: {value}/{total}" for key, value in sorted(counter.items()) if key]
    return "; ".join(parts)


def build_rule_rows() -> list[dict[str, str]]:
    baseline = parse_s5_baseline_note()
    counters = s5_frequency_summary()
    large_values = set(counters["large"].keys())
    large_recommendation = "0.6-0.7" if {"0.6", "0.7"}.issubset(large_values) else format_number(baseline.get("large"))
    return [
        {
            "theory_adjust_abs_range": "0-50",
            "recommended_lambda": "0",
            "policy_meaning": "No immediate adjustment; enter stranded carry term",
            "reason": "Below 50 CNY/ton threshold, frequent tiny adjustments are not policy-efficient",
            "robustness_evidence": "Rule inherited from refined-oil adjustment threshold",
        },
        {
            "theory_adjust_abs_range": "50-300",
            "recommended_lambda": "0.9-1.0",
            "policy_meaning": "Near-full pass-through for small shocks",
            "reason": "Small changes have limited CPI/volatility impact and should avoid cost accumulation",
            "robustness_evidence": f"Baseline small={format_number(baseline.get('small'))}; sensitivity {format_counter(counters['small'])}",
        },
        {
            "theory_adjust_abs_range": "300-800",
            "recommended_lambda": "0.8",
            "policy_meaning": "Moderate smoothing for medium shocks",
            "reason": "Balances cost pass-through and consumer/CPI pressure",
            "robustness_evidence": f"Baseline medium={format_number(baseline.get('medium'))}; sensitivity {format_counter(counters['medium'])}",
        },
        {
            "theory_adjust_abs_range": "800-1500",
            "recommended_lambda": large_recommendation,
            "policy_meaning": "Strong smoothing for large shocks",
            "reason": "Large one-off adjustments create visible policy acceptability pressure",
            "robustness_evidence": f"Baseline large={format_number(baseline.get('large'))}; sensitivity {format_counter(counters['large'])}",
        },
        {
            "theory_adjust_abs_range": ">=1500",
            "recommended_lambda": "0.4",
            "policy_meaning": "Extreme-shock cap with substantial smoothing",
            "reason": "Extreme shocks should be split over time to protect expectations and CPI stability",
            "robustness_evidence": f"Baseline extreme={format_number(baseline.get('extreme'))}; sensitivity {format_counter(counters['extreme'])}",
        },
    ]


def build_rule_curve() -> None:
    x_min, x_max = 0, 1800
    y_min, y_max = extent([0, 1], include_zero=True)
    left = MARGIN_LEFT
    right = WIDTH - MARGIN_RIGHT
    top = MARGIN_TOP
    bottom = HEIGHT - MARGIN_BOTTOM
    lines = svg_header("Simplified Policy Rule Curve")
    add_axes(lines, y_min, y_max, "Absolute theoretical adjustment (CNY per ton)", "Recommended pass-through ratio")
    segments = [
        (0, 50, 0.0),
        (50, 300, 0.95),
        (300, 800, 0.8),
        (800, 1500, 0.65),
        (1500, 1800, 0.4),
    ]
    for start, end, ratio in segments:
        x1 = scale(start, x_min, x_max, left, right)
        x2 = scale(end, x_min, x_max, left, right)
        y = scale(ratio, y_min, y_max, bottom, top)
        lines.append(f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" stroke="#e45756" stroke-width="4"/>')
        lines.append(f'<line x1="{x1:.1f}" y1="{bottom:.1f}" x2="{x1:.1f}" y2="{top:.1f}" stroke="#dddddd" stroke-dasharray="4 4"/>')
        lines.append(f'<text x="{(x1 + x2) / 2:.1f}" y="{y - 10:.1f}" text-anchor="middle" font-family="Arial" font-size="12">{ratio:.2f}</text>')
    for cutoff in (50, 300, 800, 1500):
        x = scale(cutoff, x_min, x_max, left, right)
        lines.append(f'<text x="{x:.1f}" y="{bottom + 22}" text-anchor="middle" font-family="Arial" font-size="11">{cutoff}</text>')
    write_svg(FIGURE_PATH, lines)


def main() -> None:
    ensure_project_dirs(ROOT)
    # Read the long strategy table as a sanity check that S5 windows exist.
    _, result_rows, _ = read_csv_auto(STRATEGY_RESULTS_PATH)
    if not any(row.get("strategy") == "S5_grid_best_segmented" for row in result_rows):
        raise ValueError("S5_grid_best_segmented not found in strategy_simulation_results.csv")
    rule_rows = build_rule_rows()
    write_csv(
        OUT_TABLE_PATH,
        rule_rows,
        ["theory_adjust_abs_range", "recommended_lambda", "policy_meaning", "reason", "robustness_evidence"],
    )
    build_rule_curve()
    print(f"Wrote {OUT_TABLE_PATH}")
    print(f"Wrote {FIGURE_PATH}")


if __name__ == "__main__":
    main()
