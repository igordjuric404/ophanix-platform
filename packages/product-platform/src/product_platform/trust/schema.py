"""Canonical trust score schema contract."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

TRUST_SCORE_SCHEMA_VERSION = "trust.score.v1"
TRUST_SCORE_MIN = 0
TRUST_SCORE_MAX = 1000
TRUST_SCORE_BASELINE = 500

TRUST_SCORE_DIMENSIONS = [
    "policy_compliance",
    "resource_efficiency",
    "output_quality",
    "security_posture",
    "collaboration_health",
]

TRUST_SCORE_DIMENSION_LABELS = {
    "policy_compliance": "Policy Compliance",
    "resource_efficiency": "Resource Efficiency",
    "output_quality": "Output Quality",
    "security_posture": "Security Posture",
    "collaboration_health": "Collaboration Health",
}

TRUST_SCORE_TIER_THRESHOLDS = [
    ("verified_partner", 900),
    ("trusted", 700),
    ("standard", 500),
    ("probationary", 300),
    ("untrusted", 0),
]

TRUST_SCORE_THRESHOLDS = [
    {
        "threshold_type": "handoff",
        "target_type": "environment",
        "target_id": None,
        "min_score": 700,
        "required_tier": "trusted",
    },
    {
        "threshold_type": "mcp_tool_use",
        "target_type": "environment",
        "target_id": None,
        "min_score": 650,
        "required_tier": "standard",
    },
    {
        "threshold_type": "privileged_runtime_action",
        "target_type": "environment",
        "target_id": None,
        "min_score": 850,
        "required_tier": "trusted",
    },
    {
        "threshold_type": "marketplace_install",
        "target_type": "environment",
        "target_id": None,
        "min_score": 600,
        "required_tier": "standard",
    },
]


def clamp_trust_score(value: int | float) -> int:
    """Clamp a value to the canonical 0-1000 trust score range."""

    return max(TRUST_SCORE_MIN, min(TRUST_SCORE_MAX, int(value)))


def normalize_trust_dimensions(dimensions: dict[str, Any] | None) -> dict[str, dict[str, int]]:
    """Return canonical dimension entries with score and signal_count fields."""

    source = dimensions or {}
    normalized: dict[str, dict[str, int]] = {}
    for dimension in TRUST_SCORE_DIMENSIONS:
        raw = source.get(dimension, {})
        if isinstance(raw, dict):
            score = raw.get("score", TRUST_SCORE_BASELINE)
            signal_count = raw.get("signal_count", 0)
        else:
            score = raw
            signal_count = 0
        normalized[dimension] = {
            "score": clamp_trust_score(score),
            "signal_count": max(0, int(signal_count)),
        }
    return normalized


def trust_score_explanation(dimensions: dict[str, Any] | None) -> dict[str, Any]:
    """Build a deterministic score explanation from canonical dimensions."""

    normalized = normalize_trust_dimensions(dimensions)
    return {
        "schema_version": TRUST_SCORE_SCHEMA_VERSION,
        "source_event_versions": ["audit_events.v1"],
        "input_event_count": sum(value["signal_count"] for value in normalized.values()),
        "dimensions": normalized,
    }


def trust_score_contract() -> dict[str, Any]:
    """Return the shared trust score contract as a JSON-serializable dictionary."""

    return {
        "schema_version": TRUST_SCORE_SCHEMA_VERSION,
        "score_range": {
            "min": TRUST_SCORE_MIN,
            "max": TRUST_SCORE_MAX,
            "baseline": TRUST_SCORE_BASELINE,
        },
        "dimensions": [
            {
                "name": dimension,
                "label": TRUST_SCORE_DIMENSION_LABELS[dimension],
                "default_score": TRUST_SCORE_BASELINE,
            }
            for dimension in TRUST_SCORE_DIMENSIONS
        ],
        "tiers": [
            {"name": name, "min_score": min_score}
            for name, min_score in TRUST_SCORE_TIER_THRESHOLDS
        ],
        "thresholds": deepcopy(TRUST_SCORE_THRESHOLDS),
    }
