"""SLO burn-rate and status calculations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SloEvaluation:
    """Calculated SLO measurement fields."""

    error_budget_remaining: float
    burn_rate: float
    status: str
    good_events: int
    total_events: int


def evaluate_slo_measurement(
    *,
    target_value: float,
    value: float,
    good_events: int | None = None,
    total_events: int | None = None,
) -> SloEvaluation:
    """Evaluate a ratio-style SLO measurement.

    The product dashboard stores ratio SLIs where higher values are better, such
    as task success rate. Event counts take precedence when supplied.
    """

    allowed_error_rate = max(1.0 - target_value, 0.000001)
    if good_events is not None and total_events is not None and total_events > 0:
        normalized_good_events = max(good_events, 0)
        normalized_total_events = max(total_events, normalized_good_events)
        actual_error_rate = max(normalized_total_events - normalized_good_events, 0) / normalized_total_events
    else:
        normalized_total_events = 1
        normalized_good_events = 1 if value >= target_value else 0
        actual_error_rate = max(0.0, min(1.0, 1.0 - value))
    burn_rate = round(actual_error_rate / allowed_error_rate, 4)
    error_budget_remaining = round(max(0.0, (allowed_error_rate - actual_error_rate) / allowed_error_rate), 4)
    return SloEvaluation(
        error_budget_remaining=error_budget_remaining,
        burn_rate=burn_rate,
        status=slo_status_for(error_budget_remaining=error_budget_remaining, burn_rate=burn_rate),
        good_events=normalized_good_events,
        total_events=normalized_total_events,
    )


def slo_status_for(*, error_budget_remaining: float, burn_rate: float) -> str:
    """Map budget and burn-rate state to a dashboard status."""

    if error_budget_remaining <= 0:
        return "exhausted"
    if burn_rate >= 10:
        return "critical"
    if burn_rate > 1:
        return "warning"
    return "healthy"
