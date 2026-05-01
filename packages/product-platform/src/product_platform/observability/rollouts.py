"""Rollout gate evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RolloutGateEvaluation:
    """Rollout gate decision."""

    decision: str
    blocked_reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


def evaluate_rollout_gates(gates: dict[str, Any], signals: dict[str, Any]) -> RolloutGateEvaluation:
    """Evaluate rollout gates against supplied operational signals."""

    reasons: list[str] = []
    slo_status = str(signals.get("slo_status") or "healthy")
    if gates.get("require_slo_healthy") and slo_status not in {"healthy", "unknown"}:
        reasons.append("slo_unhealthy")
    max_policy_deny_rate = gates.get("max_policy_deny_rate")
    if max_policy_deny_rate is not None and _numeric(signals.get("policy_deny_rate")) > _numeric(max_policy_deny_rate):
        reasons.append("policy_deny_rate")
    min_trust_score = gates.get("min_trust_score")
    if min_trust_score is not None and _numeric(signals.get("trust_score", 1000)) < _numeric(min_trust_score):
        reasons.append("trust_score")
    if gates.get("block_on_open_incident") and _numeric(signals.get("open_incidents")) > 0:
        reasons.append("open_incident")
    return RolloutGateEvaluation(
        decision="blocked" if reasons else "allowed",
        blocked_reasons=reasons,
        metrics=dict(signals),
    )


def _numeric(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
