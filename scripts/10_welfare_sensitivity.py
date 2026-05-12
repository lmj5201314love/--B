from __future__ import annotations

import html
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import ensure_project_dirs, format_number, parse_float, read_csv_auto, write_csv  # noqa: E402
from src.strategy_utils import load_main_sample, simulate_all_strategies  # noqa: E402
from src.svg_utils import HEIGHT, WIDTH, svg_header, write_svg  # noqa: E402


INPUT_PATH = ROOT / "data" / "processed" / "modeling_dataset_pass_through.csv"
OUT_PATH = ROOT / "outputs" / "tables" / "welfare_sensitivity_ranking.csv"
FIGURE_PATH = ROOT / "outputs" / "figures" / "welfare_sensitivity_ranking.svg"


WEIGHT_SCENARIOS = {
    "baseline": {
        "consumer": 0.25,
        "refinery": 0.20,
        "cpi": 0.25,
        "volatility": 0.15,
        "security": 0.15,
    },
    "livelihood_priority": {
        "consumer": 0.35,
        "refinery": 0.15,
        "cpi": 0.30,
        "volatility": 0.10,
        "security": 0.10,
    },
    "refinery_priority": {
        "consumer": 0.15,
        "refinery": 0.35,
        "cpi": 0.20,
        "volatility": 0.15,
        "security": 0.15,
    },
    "stability_priority": {
        "consumer": 0.20,
        "refinery": 0.15,
        "cpi": 0.20,
        "volatility": 0.30,
        "security": 0.15,
    },
    "security_priority": {
        "consumer": 0.15,
        "refinery": 0.20,
        "cpi": 0.20,
        "volatility": 0.15,
        "security": 0.30,
    },
}


def run_sensitivity(main_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output_rows: list[dict[str, Any]] = []
    for scenario, weights in WEIGHT_SCENARIOS.items():
        _, summaries, metadata = simulate_all_strategies(main_rows, weights)
        ranked = sorted(summaries, key=lambda item: item["total_loss_sum"])
        for rank, summary in enumerate(ranked, start=1):
            best_segmented = metadata["best_segmented_lambdas"]
            output_rows.append(
                {
                    "weight_scenario": scenario,
                    "rank": rank,
                    "strategy": summary["strategy"],
                    "total_loss_sum": format_number(parse_float(summary["total_loss_sum"])),
                    "consumer_weight": weights["consumer"],
                    "refinery_weight": weights["refinery"],
                    "cpi_weight": weights["cpi"],
                    "volatility_weight": weights["volatility"],
                    "security_weight": weights["security"],
                    "best_fixed_lambda": format_number(parse_float(metadata["best_fixed_lambda"])),
                    "best_lambda_small": format_number(parse_float(best_segmented["lambda_small"])),
                    "best_lambda_medium": format_number(parse_float(best_segmented["lambda_medium"])),
                    "best_lambda_large": format_number(parse_float(best_segmented["lambda_large"])),
                    "best_lambda_extreme": format_number(parse_float(best_segmented["lambda_extreme"])),
                    "notes": summary["notes"],
                }
            )
    return output_rows


def color_for_rank(rank: int) -> str:
    palette = {
        1: "#2ca25f",
        2: "#99d8c9",
        3: "#fee08b",
        4: "#fdae61",
        5: "#f46d43",
        6: "#d73027",
    }
    return palette.get(rank, "#cccccc")


def build_ranking_figure(rows: list[dict[str, Any]]) -> None:
    scenarios = list(WEIGHT_SCENARIOS)
    strategies = sorted({row["strategy"] for row in rows})
    rank_map = {(row["weight_scenario"], row["strategy"]): int(row["rank"]) for row in rows}
    left = 210
    top = 72
    cell_w = 132
    cell_h = 72
    lines = svg_header("Welfare Strategy Ranking under Weight Sensitivity")
    lines.append(f'<text x="{left + cell_w * len(strategies) / 2:.1f}" y="56" text-anchor="middle" font-family="Arial" font-size="13" fill="#555">Lower rank is better</text>')
    for col, strategy in enumerate(strategies):
        x = left + col * cell_w + cell_w / 2
        lines.append(
            f'<text x="{x:.1f}" y="{top - 12}" text-anchor="middle" font-family="Arial" font-size="11" fill="#333">{html.escape(strategy)}</text>'
        )
    for row_index, scenario in enumerate(scenarios):
        y = top + row_index * cell_h
        lines.append(
            f'<text x="{left - 14}" y="{y + cell_h / 2 + 5:.1f}" text-anchor="end" font-family="Arial" font-size="12" fill="#333">{html.escape(scenario)}</text>'
        )
        for col, strategy in enumerate(strategies):
            rank = rank_map.get((scenario, strategy), 0)
            x = left + col * cell_w
            color = color_for_rank(rank)
            lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w - 6}" height="{cell_h - 8}" fill="{color}" opacity="0.88" stroke="white"/>')
            lines.append(
                f'<text x="{x + (cell_w - 6) / 2:.1f}" y="{y + cell_h / 2 + 5:.1f}" text-anchor="middle" font-family="Arial" font-size="20" font-weight="700" fill="#222">{rank}</text>'
            )
    lines.append(f'<text x="{WIDTH / 2:.1f}" y="{HEIGHT - 38}" text-anchor="middle" font-family="Arial" font-size="12" fill="#555">Ranks are recomputed after re-searching S4 and S5 under each weight scenario.</text>')
    write_svg(FIGURE_PATH, lines)


def main() -> None:
    ensure_project_dirs(ROOT)
    _, rows, _ = read_csv_auto(INPUT_PATH)
    main_rows = load_main_sample(rows)
    output_rows = run_sensitivity(main_rows)
    write_csv(
        OUT_PATH,
        output_rows,
        [
            "weight_scenario",
            "rank",
            "strategy",
            "total_loss_sum",
            "consumer_weight",
            "refinery_weight",
            "cpi_weight",
            "volatility_weight",
            "security_weight",
            "best_fixed_lambda",
            "best_lambda_small",
            "best_lambda_medium",
            "best_lambda_large",
            "best_lambda_extreme",
            "notes",
        ],
    )
    build_ranking_figure(output_rows)
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {FIGURE_PATH}")


if __name__ == "__main__":
    main()
