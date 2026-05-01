"""Cost budget status and breach-action helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostBudgetEvaluation:
    """Calculated budget status."""

    status: str
    breach_action: str
    usage_ratio: float


def evaluate_cost_budget(
    *,
    amount_limit: float,
    used_amount: float,
    action_on_breach: str,
) -> CostBudgetEvaluation:
    """Evaluate cost budget usage against the configured limit."""

    if amount_limit <= 0:
        usage_ratio = 1.0
    else:
        usage_ratio = used_amount / amount_limit
    if usage_ratio >= 1.0:
        return CostBudgetEvaluation(
            status="breached",
            breach_action=action_on_breach,
            usage_ratio=round(usage_ratio, 4),
        )
    if usage_ratio >= 0.8:
        return CostBudgetEvaluation(status="warning", breach_action="warn", usage_ratio=round(usage_ratio, 4))
    return CostBudgetEvaluation(status="active", breach_action="none", usage_ratio=round(usage_ratio, 4))
