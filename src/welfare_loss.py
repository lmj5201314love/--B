from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.data_utils import format_number, parse_float


DEFAULT_WEIGHTS = {
    "consumer": 0.25,
    "refinery": 0.20,
    "cpi": 0.25,
    "volatility": 0.15,
    "security": 0.15,
}


def normalize_series(s: list[float | int | str | None]) -> list[float]:
    """Min-max normalize a numeric series to [0, 1]."""
    values = [parse_float(value) for value in s]
    clean = [value for value in values if value is not None]
    if not clean:
        return [0.0 for _ in values]
    low = min(clean)
    high = max(clean)
    if high == low:
        return [0.0 for _ in values]
    return [0.0 if value is None else (value - low) / (high - low) for value in values]


def _non_missing_number(row: dict[str, Any], column: str, default: float = 0.0) -> float:
    value = parse_float(row.get(column))
    return default if value is None else value


def compute_loss_components(
    df: list[dict[str, Any]],
    action_col: str,
    theory_col: str,
) -> list[dict[str, Any]]:
    """Compute raw and normalized welfare loss components for one strategy.

    The function expects rows sorted by adjustment window. It returns a new list and
    does not mutate the input rows.
    """
    output_rows = [deepcopy(row) for row in df]
    previous_action: float | None = None
    cumulative_unmet_gap = 0.0

    for row in output_rows:
        action = _non_missing_number(row, action_col)
        theory_adjust = _non_missing_number(row, theory_col)
        cpi_yoy_pct = parse_float(row.get("cpi_yoy_pct"))
        cpi_pressure_factor = 1.0 if cpi_yoy_pct is None else 1.0 + max(cpi_yoy_pct, 0.0) / 5.0
        volatility_base = 0.0 if previous_action is None else action - previous_action
        unmet_gap = theory_adjust - action
        cumulative_unmet_gap += unmet_gap

        row["consumer_loss_raw"] = max(action, 0.0) ** 2
        row["refinery_loss_raw"] = unmet_gap**2
        row["cpi_loss_raw"] = max(action, 0.0) ** 2 * cpi_pressure_factor
        row["volatility_loss_raw"] = volatility_base**2
        row["unmet_gap"] = unmet_gap
        row["cumulative_unmet_gap"] = cumulative_unmet_gap
        row["security_loss_raw"] = cumulative_unmet_gap**2
        previous_action = action

    raw_to_normalized = {
        "consumer_loss_raw": "consumer_loss",
        "refinery_loss_raw": "refinery_loss",
        "cpi_loss_raw": "cpi_loss",
        "volatility_loss_raw": "volatility_loss",
        "security_loss_raw": "security_loss",
    }
    for raw_col, normalized_col in raw_to_normalized.items():
        normalized_values = normalize_series([row.get(raw_col) for row in output_rows])
        for row, normalized_value in zip(output_rows, normalized_values):
            row[normalized_col] = normalized_value

    return output_rows


def compute_total_welfare_loss(
    df: list[dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Compute weighted total welfare loss from normalized loss components."""
    active_weights = DEFAULT_WEIGHTS.copy()
    if weights:
        active_weights.update(weights)

    output_rows = [deepcopy(row) for row in df]
    for row in output_rows:
        total_loss = (
            active_weights["consumer"] * _non_missing_number(row, "consumer_loss")
            + active_weights["refinery"] * _non_missing_number(row, "refinery_loss")
            + active_weights["cpi"] * _non_missing_number(row, "cpi_loss")
            + active_weights["volatility"] * _non_missing_number(row, "volatility_loss")
            + active_weights["security"] * _non_missing_number(row, "security_loss")
        )
        row["total_loss"] = total_loss
    return output_rows


def format_loss_row(row: dict[str, Any]) -> dict[str, Any]:
    """Format numeric loss columns for CSV output while preserving other fields."""
    formatted = dict(row)
    for column in (
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
    ):
        if column in formatted:
            formatted[column] = format_number(parse_float(formatted[column]))
    return formatted
