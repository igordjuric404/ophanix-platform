"""Usage trust scoring for marketplace plugins."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PluginUsageSignals:
    """Usage and incident signals for plugin trust recomputation."""

    daily_active_users: int = 0
    total_invocations: int = 0
    error_count: int = 0
    incident_count: int = 0
    days_since_update: int = 0
    adoption_trend: float = 0


def compute_usage_trust_delta(signals: PluginUsageSignals) -> tuple[int, str]:
    """Return trust delta and reason for usage signals."""

    delta = 0
    reasons: list[str] = []
    if signals.daily_active_users >= 1000:
        delta += 150
        reasons.append("high adoption")
    elif signals.daily_active_users >= 100:
        delta += 50
        reasons.append("moderate adoption")
    elif signals.daily_active_users >= 10:
        delta += 10
        reasons.append("early adoption")
    if signals.total_invocations >= 1000:
        error_rate = signals.error_count / signals.total_invocations
        if error_rate < 0.01:
            delta += 40
            reasons.append("reliable usage")
        elif error_rate > 0.1:
            delta -= 80
            reasons.append("high error rate")
    if signals.incident_count:
        delta -= min(signals.incident_count * 75, 250)
        reasons.append("incident penalty")
    if signals.days_since_update > 180:
        delta -= 40
        reasons.append("stale package")
    if signals.adoption_trend > 0.1:
        delta += 25
        reasons.append("growing adoption")
    elif signals.adoption_trend < -0.2:
        delta -= 25
        reasons.append("declining adoption")
    delta = max(-300, min(300, delta))
    return delta, ", ".join(reasons) or "neutral usage"


def trust_tier_for_score(score: int) -> str:
    """Map trust score to product trust tier."""

    if score >= 850:
        return "verified"
    if score >= 700:
        return "trusted"
    if score >= 500:
        return "standard"
    return "watchlist"
