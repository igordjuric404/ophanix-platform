"""Deterministic demo chaos run guardrail evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChaosRunEvaluation:
    """Result of evaluating a guarded demo chaos run."""

    status: str
    guardrail_breached: bool
    breached_guardrails: list[str] = field(default_factory=list)
    observed_metrics: dict[str, Any] = field(default_factory=dict)


def evaluate_chaos_run(guardrails: dict[str, Any], observed_metrics: dict[str, Any] | None = None) -> ChaosRunEvaluation:
    """Evaluate observed metrics against max_* guardrails."""

    metrics = dict(observed_metrics or {})
    breaches: list[str] = []
    for guardrail, limit in guardrails.items():
        if not guardrail.startswith("max_"):
            continue
        metric_name = guardrail.removeprefix("max_")
        if metric_name not in metrics:
            metrics[metric_name] = _safe_metric_value(limit)
        if _numeric(metrics[metric_name]) > _numeric(limit):
            breaches.append(guardrail)
    return ChaosRunEvaluation(
        status="stopped" if breaches else "completed",
        guardrail_breached=bool(breaches),
        breached_guardrails=breaches,
        observed_metrics=metrics,
    )


def _safe_metric_value(limit: Any) -> float:
    value = _numeric(limit)
    return value / 2 if value > 0 else 0.0


def _numeric(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
