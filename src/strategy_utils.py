from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.data_utils import format_number, parse_date, parse_float
from src.welfare_loss import DEFAULT_WEIGHTS, compute_loss_components, compute_total_welfare_loss


START_DATE = parse_date("2016-01-01")
END_DATE = parse_date("2026-05-09")
THEORY_COL = "theory_adjust_rule_cny_per_ton"
ACTUAL_COL = "avg_adjust_cny_per_ton"
ACTION_COL = "strategy_action_cny_per_ton"
THRESHOLD_CNY_PER_TON = 50.0

FIXED_LAMBDAS = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
SEGMENTED_GRID = {
    "lambda_small": [0.9, 1.0],
    "lambda_medium": [0.7, 0.8, 0.9],
    "lambda_large": [0.5, 0.6, 0.7],
    "lambda_extreme": [0.4, 0.5, 0.6],
}


def in_main_sample(row: dict[str, Any]) -> bool:
    parsed = parse_date(row.get("date", ""))
    return parsed is not None and START_DATE is not None and END_DATE is not None and START_DATE <= parsed <= END_DATE


def load_main_sample(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    main_rows = [dict(row) for row in rows if in_main_sample(row)]
    main_rows.sort(key=lambda item: (item.get("date", ""), item.get("notice_date", "")))
    return main_rows


def threshold_action(action: float, threshold: float = THRESHOLD_CNY_PER_TON) -> float:
    return 0.0 if abs(action) < threshold else action


def fixed_lambda_action(theory: float, lambda_value: float, apply_threshold: bool = True) -> float:
    action = lambda_value * theory
    return threshold_action(action) if apply_threshold else action


def segmented_action(
    theory: float,
    lambda_small: float = 1.0,
    lambda_medium: float = 0.8,
    lambda_large: float = 0.6,
    lambda_extreme: float = 0.5,
) -> float:
    abs_theory = abs(theory)
    if abs_theory < THRESHOLD_CNY_PER_TON:
        return 0.0
    if abs_theory < 300:
        return lambda_small * theory
    if abs_theory < 800:
        return lambda_medium * theory
    if abs_theory < 1500:
        return lambda_large * theory
    return lambda_extreme * theory


def apply_strategy(
    rows: list[dict[str, Any]],
    strategy: str,
    notes: str,
    action_values: list[float],
    weights: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    strategy_rows = [deepcopy(row) for row in rows]
    for row, action in zip(strategy_rows, action_values):
        row["strategy"] = strategy
        row[ACTION_COL] = action
        row["strategy_notes"] = notes

    loss_rows = compute_loss_components(strategy_rows, ACTION_COL, THEORY_COL)
    loss_rows = compute_total_welfare_loss(loss_rows, weights or DEFAULT_WEIGHTS)
    summary = summarize_strategy(strategy, loss_rows, notes)
    return loss_rows, summary


def summarize_strategy(strategy: str, rows: list[dict[str, Any]], notes: str) -> dict[str, Any]:
    actions = [parse_float(row.get(ACTION_COL)) for row in rows]
    action_values = [value for value in actions if value is not None]
    total = lambda col: sum(parse_float(row.get(col)) or 0.0 for row in rows)
    no_adjust = sum(1 for value in action_values if abs(value) < 1e-9)
    up_actions = [value for value in action_values if value > 0]
    down_actions = [value for value in action_values if value < 0]
    final_gap = parse_float(rows[-1].get("cumulative_unmet_gap")) if rows else None
    return {
        "strategy": strategy,
        "total_loss_sum": total("total_loss"),
        "consumer_loss_sum": total("consumer_loss"),
        "refinery_loss_sum": total("refinery_loss"),
        "cpi_loss_sum": total("cpi_loss"),
        "volatility_loss_sum": total("volatility_loss"),
        "security_loss_sum": total("security_loss"),
        "mean_action": sum(action_values) / len(action_values) if action_values else None,
        "mean_abs_action": sum(abs(value) for value in action_values) / len(action_values) if action_values else None,
        "max_up_action": max(up_actions) if up_actions else None,
        "max_down_action": min(down_actions) if down_actions else None,
        "no_adjust_rate": no_adjust / len(action_values) if action_values else None,
        "final_cumulative_unmet_gap": final_gap,
        "notes": notes,
    }


def evaluate_fixed_lambda(
    rows: list[dict[str, Any]],
    lambda_value: float,
    weights: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    actions = []
    for row in rows:
        theory = parse_float(row.get(THEORY_COL)) or 0.0
        actions.append(fixed_lambda_action(theory, lambda_value))
    return apply_strategy(
        rows,
        f"S4_grid_best_fixed_lambda",
        f"lambda={format_number(lambda_value)}; threshold=50",
        actions,
        weights,
    )


def search_best_fixed_lambda(
    rows: list[dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> tuple[float, list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    best_lambda = FIXED_LAMBDAS[0]
    best_rows: list[dict[str, Any]] = []
    best_summary: dict[str, Any] | None = None
    for lambda_value in FIXED_LAMBDAS:
        candidate_rows, summary = evaluate_fixed_lambda(rows, lambda_value, weights)
        candidates.append(
            {
                "candidate_type": "fixed_lambda",
                "lambda": lambda_value,
                "total_loss_sum": summary["total_loss_sum"],
            }
        )
        if best_summary is None or summary["total_loss_sum"] < best_summary["total_loss_sum"]:
            best_lambda = lambda_value
            best_rows = candidate_rows
            best_summary = summary
    assert best_summary is not None
    best_summary["notes"] = f"best lambda={format_number(best_lambda)}; threshold=50"
    for row in best_rows:
        row["strategy_notes"] = best_summary["notes"]
    return best_lambda, best_rows, best_summary, candidates


def evaluate_segmented_grid(
    rows: list[dict[str, Any]],
    lambdas: dict[str, float],
    weights: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    actions = []
    for row in rows:
        theory = parse_float(row.get(THEORY_COL)) or 0.0
        actions.append(segmented_action(theory, **lambdas))
    notes = (
        f"small={format_number(lambdas['lambda_small'])}, "
        f"medium={format_number(lambdas['lambda_medium'])}, "
        f"large={format_number(lambdas['lambda_large'])}, "
        f"extreme={format_number(lambdas['lambda_extreme'])}"
    )
    return apply_strategy(rows, "S5_grid_best_segmented", notes, actions, weights)


def search_best_segmented(
    rows: list[dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> tuple[dict[str, float], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    best_lambdas: dict[str, float] | None = None
    best_rows: list[dict[str, Any]] = []
    best_summary: dict[str, Any] | None = None
    for lambda_small in SEGMENTED_GRID["lambda_small"]:
        for lambda_medium in SEGMENTED_GRID["lambda_medium"]:
            for lambda_large in SEGMENTED_GRID["lambda_large"]:
                for lambda_extreme in SEGMENTED_GRID["lambda_extreme"]:
                    lambdas = {
                        "lambda_small": lambda_small,
                        "lambda_medium": lambda_medium,
                        "lambda_large": lambda_large,
                        "lambda_extreme": lambda_extreme,
                    }
                    candidate_rows, summary = evaluate_segmented_grid(rows, lambdas, weights)
                    candidates.append(
                        {
                            "candidate_type": "segmented",
                            **lambdas,
                            "total_loss_sum": summary["total_loss_sum"],
                        }
                    )
                    if best_summary is None or summary["total_loss_sum"] < best_summary["total_loss_sum"]:
                        best_lambdas = lambdas
                        best_rows = candidate_rows
                        best_summary = summary
    assert best_lambdas is not None and best_summary is not None
    best_summary["notes"] = (
        f"best small={format_number(best_lambdas['lambda_small'])}, "
        f"medium={format_number(best_lambdas['lambda_medium'])}, "
        f"large={format_number(best_lambdas['lambda_large'])}, "
        f"extreme={format_number(best_lambdas['lambda_extreme'])}"
    )
    for row in best_rows:
        row["strategy_notes"] = best_summary["notes"]
    return best_lambdas, best_rows, best_summary, candidates


def simulate_all_strategies(
    rows: list[dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    active_weights = weights or DEFAULT_WEIGHTS
    all_result_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    actual_actions = [parse_float(row.get(ACTUAL_COL)) or 0.0 for row in rows]
    s0_rows, s0_summary = apply_strategy(rows, "S0_current", "actual historical adjustment", actual_actions, active_weights)
    all_result_rows.extend(s0_rows)
    summaries.append(s0_summary)

    full_actions = [parse_float(row.get(THEORY_COL)) or 0.0 for row in rows]
    s1_rows, s1_summary = apply_strategy(rows, "S1_full_pass", "action=theory_adjust_rule", full_actions, active_weights)
    all_result_rows.extend(s1_rows)
    summaries.append(s1_summary)

    fixed_70_actions = [fixed_lambda_action(parse_float(row.get(THEORY_COL)) or 0.0, 0.7) for row in rows]
    s2_rows, s2_summary = apply_strategy(rows, "S2_fixed_70", "lambda=0.7; threshold=50", fixed_70_actions, active_weights)
    all_result_rows.extend(s2_rows)
    summaries.append(s2_summary)

    segmented_actions = [segmented_action(parse_float(row.get(THEORY_COL)) or 0.0) for row in rows]
    s3_rows, s3_summary = apply_strategy(
        rows,
        "S3_segmented_smoothing",
        "small=1.0, medium=0.8, large=0.6, extreme=0.5",
        segmented_actions,
        active_weights,
    )
    all_result_rows.extend(s3_rows)
    summaries.append(s3_summary)

    best_fixed_lambda, s4_rows, s4_summary, fixed_candidates = search_best_fixed_lambda(rows, active_weights)
    all_result_rows.extend(s4_rows)
    summaries.append(s4_summary)

    best_segmented_lambdas, s5_rows, s5_summary, segmented_candidates = search_best_segmented(rows, active_weights)
    all_result_rows.extend(s5_rows)
    summaries.append(s5_summary)

    search_metadata = {
        "best_fixed_lambda": best_fixed_lambda,
        "best_segmented_lambdas": best_segmented_lambdas,
        "fixed_candidates": fixed_candidates,
        "segmented_candidates": segmented_candidates,
    }
    return all_result_rows, summaries, search_metadata
