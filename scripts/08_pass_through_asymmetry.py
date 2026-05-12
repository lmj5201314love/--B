from __future__ import annotations

import sys
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import ensure_project_dirs, format_number, parse_float, read_csv_auto, write_csv  # noqa: E402
from src.svg_utils import box_strip_chart, scatter_chart  # noqa: E402


MECHANISM_PATH = ROOT / "data" / "processed" / "modeling_dataset_mechanism.csv"
OUT_PATH = ROOT / "data" / "processed" / "modeling_dataset_pass_through.csv"
ASYMMETRY_PATH = ROOT / "outputs" / "tables" / "pass_through_asymmetry.csv"
REGIME_PATH = ROOT / "outputs" / "tables" / "oil_price_regime_analysis.csv"
FIGURE_DIR = ROOT / "outputs" / "figures"
THRESHOLD_CNY_PER_TON = 50.0


def clean_mean(values: list[float]) -> float | None:
    return mean(values) if values else None


def clean_median(values: list[float]) -> float | None:
    return median(values) if values else None


def compute_pass_through_rows(headers: list[str], rows: list[dict[str, str]]) -> tuple[list[str], list[dict[str, object]]]:
    output_rows: list[dict[str, object]] = []
    for row in rows:
        output: dict[str, object] = dict(row)
        actual = parse_float(row.get("avg_adjust_cny_per_ton"))
        theory = parse_float(row.get("theory_adjust_rule_cny_per_ton"))
        if actual is not None and theory is not None and abs(theory) >= THRESHOLD_CNY_PER_TON:
            ratio = actual / theory
            gap = theory - actual
            under = 1 if abs(actual) < abs(theory) else 0
            over = 1 if abs(actual) > abs(theory) else 0
        else:
            ratio = None
            gap = None
            under = None
            over = None
        output.update(
            {
                "pass_through_ratio": format_number(ratio),
                "pass_through_gap": format_number(gap),
                "is_under_transmitted": "" if under is None else under,
                "is_over_transmitted": "" if over is None else over,
            }
        )
        output_rows.append(output)
    new_fields = ["pass_through_ratio", "pass_through_gap", "is_under_transmitted", "is_over_transmitted"]
    return headers + [field for field in new_fields if field not in headers], output_rows


def eligible(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [row for row in rows if parse_float(row.get("pass_through_ratio")) is not None]


def group_summary(name: str, rows: list[dict[str, object]]) -> dict[str, object]:
    group_rows = eligible(rows)
    theory = [parse_float(row.get("theory_adjust_rule_cny_per_ton")) for row in group_rows]
    actual = [parse_float(row.get("avg_adjust_cny_per_ton")) for row in group_rows]
    ratios = [parse_float(row.get("pass_through_ratio")) for row in group_rows]
    gaps = [parse_float(row.get("pass_through_gap")) for row in group_rows]
    under = [parse_float(row.get("is_under_transmitted")) for row in group_rows]
    over = [parse_float(row.get("is_over_transmitted")) for row in group_rows]
    theory_values = [value for value in theory if value is not None]
    actual_values = [value for value in actual if value is not None]
    ratio_values = [value for value in ratios if value is not None]
    gap_values = [value for value in gaps if value is not None]
    under_values = [value for value in under if value is not None]
    over_values = [value for value in over if value is not None]
    return {
        "group": name,
        "sample_size": len(group_rows),
        "mean_theory_adjust": format_number(clean_mean(theory_values)),
        "mean_actual_adjust": format_number(clean_mean(actual_values)),
        "mean_pass_through_ratio": format_number(clean_mean(ratio_values)),
        "median_pass_through_ratio": format_number(clean_median(ratio_values)),
        "mean_pass_through_gap": format_number(clean_mean(gap_values)),
        "under_transmitted_rate": format_number(clean_mean(under_values)),
        "over_transmitted_rate": format_number(clean_mean(over_values)),
    }


def build_asymmetry_table(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    def value(row: dict[str, object], column: str) -> float | None:
        return parse_float(row.get(column))

    groups = [
        ("theory_up", [row for row in rows if (value(row, "theory_adjust_rule_cny_per_ton") or 0) > 0]),
        ("theory_down", [row for row in rows if (value(row, "theory_adjust_rule_cny_per_ton") or 0) < 0]),
        ("actual_up", [row for row in rows if (value(row, "avg_adjust_cny_per_ton") or 0) > 0]),
        ("actual_down", [row for row in rows if (value(row, "avg_adjust_cny_per_ton") or 0) < 0]),
        ("high_oil_price_ge_80", [row for row in rows if (value(row, "brent_wti_weighted_window_avg") or -9999) >= 80]),
        (
            "medium_oil_price_40_80",
            [
                row
                for row in rows
                if (value(row, "brent_wti_weighted_window_avg") is not None)
                and 40 <= value(row, "brent_wti_weighted_window_avg") < 80
            ],
        ),
        ("low_oil_price_lt_40", [row for row in rows if (value(row, "brent_wti_weighted_window_avg") or 9999) < 40]),
        ("large_theory_up_ge_300", [row for row in rows if (value(row, "theory_adjust_rule_cny_per_ton") or 0) >= 300]),
        ("large_theory_down_le_-300", [row for row in rows if (value(row, "theory_adjust_rule_cny_per_ton") or 0) <= -300]),
    ]
    return [group_summary(name, group_rows) for name, group_rows in groups]


def regime_label(oil_level: float | None) -> str | None:
    if oil_level is None:
        return None
    if oil_level < 40:
        return "low"
    if oil_level < 80:
        return "normal"
    if oil_level < 130:
        return "high"
    return "extreme_high"


def build_regime_analysis(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for regime in ("low", "normal", "high", "extreme_high"):
        group_rows = [
            row
            for row in rows
            if regime_label(parse_float(row.get("brent_wti_weighted_window_avg"))) == regime
        ]
        actual = [parse_float(row.get("avg_adjust_cny_per_ton")) for row in group_rows]
        theory = [parse_float(row.get("theory_adjust_rule_cny_per_ton")) for row in group_rows]
        ratios = [parse_float(row.get("pass_through_ratio")) for row in group_rows]
        errors = [parse_float(row.get("theory_error_rule_cny_per_ton")) for row in group_rows]
        actual_values = [value for value in actual if value is not None]
        theory_values = [value for value in theory if value is not None]
        ratio_values = [value for value in ratios if value is not None]
        error_values = [abs(value) for value in errors if value is not None]
        no_adjust_count = sum(1 for value in actual_values if value == 0)
        up_values = [value for value in actual_values if value > 0]
        down_values = [value for value in actual_values if value < 0]
        output.append(
            {
                "oil_price_regime": regime,
                "sample_size": len(group_rows),
                "mean_actual_adjust": format_number(clean_mean(actual_values)),
                "mean_theory_adjust": format_number(clean_mean(theory_values)),
                "mean_pass_through_ratio": format_number(clean_mean(ratio_values)),
                "no_adjust_rate": format_number(no_adjust_count / len(actual_values) if actual_values else None),
                "mean_abs_error": format_number(clean_mean(error_values)),
                "max_up_adjust": format_number(max(up_values) if up_values else None),
                "max_down_adjust": format_number(min(down_values) if down_values else None),
            }
        )
    return output


def build_figures(rows: list[dict[str, object]]) -> None:
    eligible_rows = eligible(rows)
    theory_up_ratios = [
        parse_float(row.get("pass_through_ratio"))
        for row in eligible_rows
        if (parse_float(row.get("theory_adjust_rule_cny_per_ton")) or 0) > 0
    ]
    theory_down_ratios = [
        parse_float(row.get("pass_through_ratio"))
        for row in eligible_rows
        if (parse_float(row.get("theory_adjust_rule_cny_per_ton")) or 0) < 0
    ]
    box_strip_chart(
        FIGURE_DIR / "pass_through_ratio_by_direction.svg",
        "Pass-through Ratio by Theory Direction",
        [
            ("Theory up", [value for value in theory_up_ratios if value is not None], "#1b9e77"),
            ("Theory down", [value for value in theory_down_ratios if value is not None], "#d95f02"),
        ],
        "Pass-through ratio",
    )

    regime_specs = [
        ("Low <40", lambda oil: oil is not None and oil < 40, "#4c78a8"),
        ("Middle 40-80", lambda oil: oil is not None and 40 <= oil < 80, "#59a14f"),
        ("High >=80", lambda oil: oil is not None and oil >= 80, "#e15759"),
    ]
    gap_categories = []
    for label, predicate, color in regime_specs:
        gaps = []
        for row in eligible_rows:
            oil = parse_float(row.get("brent_wti_weighted_window_avg"))
            gap = parse_float(row.get("pass_through_gap"))
            if predicate(oil) and gap is not None:
                gaps.append(gap)
        gap_categories.append((label, gaps, color))
    box_strip_chart(
        FIGURE_DIR / "pass_through_gap_by_oil_regime.svg",
        "Pass-through Gap by Oil Price Regime",
        gap_categories,
        "Theory minus actual (CNY per ton)",
    )

    scatter_points = []
    for row in eligible_rows:
        theory = parse_float(row.get("theory_adjust_rule_cny_per_ton"))
        actual = parse_float(row.get("avg_adjust_cny_per_ton"))
        if theory is None or actual is None:
            continue
        group = "theory up" if theory > 0 else "theory down"
        scatter_points.append((theory, actual, group))
    scatter_chart(
        FIGURE_DIR / "theory_vs_actual_by_direction.svg",
        "Theory vs Actual by Direction",
        scatter_points,
        "Rule theory adjustment (CNY per ton)",
        "Actual adjustment (CNY per ton)",
        {"theory up": "#1b9e77", "theory down": "#d95f02"},
        draw_equal_line=True,
    )


def main() -> None:
    ensure_project_dirs(ROOT)
    headers, rows, _ = read_csv_auto(MECHANISM_PATH)
    fieldnames, output_rows = compute_pass_through_rows(headers, rows)
    write_csv(OUT_PATH, output_rows, fieldnames)
    asymmetry_rows = build_asymmetry_table(output_rows)
    write_csv(
        ASYMMETRY_PATH,
        asymmetry_rows,
        [
            "group",
            "sample_size",
            "mean_theory_adjust",
            "mean_actual_adjust",
            "mean_pass_through_ratio",
            "median_pass_through_ratio",
            "mean_pass_through_gap",
            "under_transmitted_rate",
            "over_transmitted_rate",
        ],
    )
    regime_rows = build_regime_analysis(output_rows)
    write_csv(
        REGIME_PATH,
        regime_rows,
        [
            "oil_price_regime",
            "sample_size",
            "mean_actual_adjust",
            "mean_theory_adjust",
            "mean_pass_through_ratio",
            "no_adjust_rate",
            "mean_abs_error",
            "max_up_adjust",
            "max_down_adjust",
        ],
    )
    build_figures(output_rows)
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {ASYMMETRY_PATH}")
    print(f"Wrote {REGIME_PATH}")
    print(f"Wrote pass-through figures to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
