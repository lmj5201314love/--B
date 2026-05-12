from __future__ import annotations

from typing import Iterable


def profit_deduction_factor(oil_price: float | None) -> float:
    """Approximate profit-deduction factor for oil prices above 80 USD/bbl.

    This is a modeling simplification of the policy rule that processing profit
    is gradually deducted above 80 USD/bbl and largely not raised above
    130 USD/bbl.
    """
    if oil_price is None:
        return 1.0
    if oil_price <= 80:
        return 1.0
    if oil_price < 130:
        return (130 - oil_price) / 50
    return 0.0


def apply_oil_price_band_policy(
    raw_adjust: float | None,
    oil_price: float | None,
    high_price_raise_factor: float = 0.0,
) -> float | None:
    """Apply simplified 40/80/130 USD/bbl policy-band constraints."""
    if raw_adjust is None or oil_price is None:
        return None
    if oil_price <= 40 and raw_adjust < 0:
        return 0.0
    if 40 < oil_price <= 80:
        return raw_adjust
    if 80 < oil_price < 130 and raw_adjust > 0:
        return raw_adjust * profit_deduction_factor(oil_price)
    if 80 < oil_price < 130 and raw_adjust <= 0:
        return raw_adjust
    if oil_price >= 130 and raw_adjust > 0:
        return raw_adjust * high_price_raise_factor
    if oil_price >= 130 and raw_adjust <= 0:
        return raw_adjust
    return raw_adjust


def apply_threshold_and_carry(
    policy_adjust_series: Iterable[float | None],
    threshold: float = 50.0,
) -> tuple[list[float | None], list[float], list[float]]:
    """Apply the 50 CNY/ton threshold and carry accumulation rule."""
    carry = 0.0
    rule_adjust_series: list[float | None] = []
    carry_before_series: list[float] = []
    carry_after_series: list[float] = []
    for policy_adjust in policy_adjust_series:
        if policy_adjust is None:
            carry_before_series.append(carry)
            rule_adjust_series.append(None)
            carry_after_series.append(carry)
            continue
        carry += policy_adjust
        carry_before_series.append(carry)
        if abs(carry) < threshold:
            rule_adjust_series.append(0.0)
            carry_after_series.append(carry)
        else:
            rule_adjust_series.append(carry)
            carry = 0.0
            carry_after_series.append(carry)
    return rule_adjust_series, carry_before_series, carry_after_series


def oil_price_band(oil_price: float | None) -> str:
    if oil_price is None:
        return "unknown"
    if oil_price <= 40:
        return "low_floor"
    if oil_price <= 80:
        return "normal"
    if oil_price < 130:
        return "profit_deduction"
    return "extreme_high"
