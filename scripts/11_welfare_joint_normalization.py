from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import ensure_project_dirs, format_number, parse_float, read_csv_auto, write_csv  # noqa: E402
from src.robustness_utils import (  # noqa: E402
    BASELINE_WEIGHTS,
    LOSS_COMPONENTS,
    component_stacked_bar_chart,
    ensure_raw_losses,
    min_max,
    normalize_value,
    summarize_strategy_loss,
    total_loss_bar_chart,
    write_summary_csv,
)


INPUT_PATH = ROOT / "data" / "processed" / "strategy_simulation_results.csv"
OUT_DATA_PATH = ROOT / "data" / "processed" / "strategy_simulation_results_joint_norm.csv"
OUT_TABLE_PATH = ROOT / "outputs" / "tables" / "welfare_strategy_comparison_joint_norm.csv"
TOTAL_FIGURE_PATH = ROOT / "outputs" / "figures" / "welfare_total_loss_joint_norm.svg"
COMPONENT_FIGURE_PATH = ROOT / "outputs" / "figures" / "welfare_loss_components_joint_norm.svg"


def apply_joint_normalization(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output_rows: list[dict[str, object]] = ensure_raw_losses(rows)
    bounds = {}
    for component_key, raw_col, _, _ in LOSS_COMPONENTS:
        values = [parse_float(row.get(raw_col)) for row in output_rows]
        clean = [value for value in values if value is not None]
        bounds[component_key] = min_max(clean)

    for row in output_rows:
        total_loss = 0.0
        for component_key, raw_col, _, _ in LOSS_COMPONENTS:
            low, high = bounds[component_key]
            value = parse_float(row.get(raw_col))
            normalized = normalize_value(value, low, high)
            col = f"{component_key}_loss_joint_norm"
            row[col] = normalized
            total_loss += BASELINE_WEIGHTS[component_key] * normalized
        row["total_loss_joint_norm"] = total_loss
    return output_rows


def format_output_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    formatted_rows = []
    numeric_cols = [
        "consumer_loss_joint_norm",
        "refinery_loss_joint_norm",
        "cpi_loss_joint_norm",
        "volatility_loss_joint_norm",
        "security_loss_joint_norm",
        "total_loss_joint_norm",
    ]
    for row in rows:
        formatted = dict(row)
        for col in numeric_cols:
            formatted[col] = format_number(parse_float(formatted.get(col)))
        formatted_rows.append(formatted)
    return formatted_rows


def main() -> None:
    ensure_project_dirs(ROOT)
    headers, rows, _ = read_csv_auto(INPUT_PATH)
    joint_rows = apply_joint_normalization(rows)
    new_cols = [
        "consumer_loss_joint_norm",
        "refinery_loss_joint_norm",
        "cpi_loss_joint_norm",
        "volatility_loss_joint_norm",
        "security_loss_joint_norm",
        "total_loss_joint_norm",
    ]
    write_csv(OUT_DATA_PATH, format_output_rows(joint_rows), headers + [col for col in new_cols if col not in headers])

    summary_rows = summarize_strategy_loss(
        joint_rows,
        "total_loss_joint_norm",
        {
            "consumer": "consumer_loss_joint_norm",
            "refinery": "refinery_loss_joint_norm",
            "cpi": "cpi_loss_joint_norm",
            "volatility": "volatility_loss_joint_norm",
            "security": "security_loss_joint_norm",
        },
    )
    write_summary_csv(OUT_TABLE_PATH, summary_rows)
    total_loss_bar_chart(TOTAL_FIGURE_PATH, summary_rows, "Total Welfare Loss with Joint Normalization")
    component_stacked_bar_chart(COMPONENT_FIGURE_PATH, summary_rows, "Loss Components with Joint Normalization")
    print(f"Wrote {OUT_DATA_PATH}")
    print(f"Wrote {OUT_TABLE_PATH}")
    print(f"Wrote {TOTAL_FIGURE_PATH}")
    print(f"Wrote {COMPONENT_FIGURE_PATH}")


if __name__ == "__main__":
    main()
