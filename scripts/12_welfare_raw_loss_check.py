from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import ensure_project_dirs, format_number, parse_float, read_csv_auto, write_csv  # noqa: E402
from src.robustness_utils import (  # noqa: E402
    BASELINE_WEIGHTS,
    component_stacked_bar_chart,
    ensure_raw_losses,
    summarize_strategy_loss,
    total_loss_bar_chart,
    write_summary_csv,
)


INPUT_PATH = ROOT / "data" / "processed" / "strategy_simulation_results.csv"
OUT_DATA_PATH = ROOT / "data" / "processed" / "strategy_simulation_results_raw_scaled.csv"
OUT_TABLE_PATH = ROOT / "outputs" / "tables" / "welfare_strategy_comparison_raw_scaled.csv"
TOTAL_FIGURE_PATH = ROOT / "outputs" / "figures" / "welfare_total_loss_raw_scaled.svg"


SCALE_MAP = {
    "consumer": ("consumer_loss_raw", "consumer_loss_scaled", 1e6),
    "refinery": ("refinery_loss_raw", "refinery_loss_scaled", 1e6),
    "cpi": ("cpi_loss_raw", "cpi_loss_scaled", 1e6),
    "volatility": ("volatility_loss_raw", "volatility_loss_scaled", 1e6),
    "security": ("security_loss_raw", "security_loss_scaled", 1e8),
}


def apply_raw_scaled_loss(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output_rows: list[dict[str, object]] = ensure_raw_losses(rows)
    for row in output_rows:
        total_loss = 0.0
        for component, (raw_col, scaled_col, scale_value) in SCALE_MAP.items():
            scaled = (parse_float(row.get(raw_col)) or 0.0) / scale_value
            row[scaled_col] = scaled
            total_loss += BASELINE_WEIGHTS[component] * scaled
        row["total_loss_scaled"] = total_loss
    return output_rows


def format_output_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    formatted_rows = []
    for row in rows:
        formatted = dict(row)
        for _, scaled_col, _ in SCALE_MAP.values():
            formatted[scaled_col] = format_number(parse_float(formatted.get(scaled_col)))
        formatted["total_loss_scaled"] = format_number(parse_float(formatted.get("total_loss_scaled")))
        formatted_rows.append(formatted)
    return formatted_rows


def main() -> None:
    ensure_project_dirs(ROOT)
    headers, rows, _ = read_csv_auto(INPUT_PATH)
    scaled_rows = apply_raw_scaled_loss(rows)
    new_cols = [scaled_col for _, scaled_col, _ in SCALE_MAP.values()] + ["total_loss_scaled"]
    write_csv(OUT_DATA_PATH, format_output_rows(scaled_rows), headers + [col for col in new_cols if col not in headers])
    summary_rows = summarize_strategy_loss(
        scaled_rows,
        "total_loss_scaled",
        {
            "consumer": "consumer_loss_scaled",
            "refinery": "refinery_loss_scaled",
            "cpi": "cpi_loss_scaled",
            "volatility": "volatility_loss_scaled",
            "security": "security_loss_scaled",
        },
    )
    write_summary_csv(OUT_TABLE_PATH, summary_rows)
    total_loss_bar_chart(TOTAL_FIGURE_PATH, summary_rows, "Total Welfare Loss with Raw Scaled Loss")
    print(f"Wrote {OUT_DATA_PATH}")
    print(f"Wrote {OUT_TABLE_PATH}")
    print(f"Wrote {TOTAL_FIGURE_PATH}")


if __name__ == "__main__":
    main()
