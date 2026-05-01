"""Plugin quality assessment helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PluginQualityAssessment:
    """Quality score, dimensions, and findings for a plugin version."""

    score: float
    dimensions: dict[str, Any]
    findings: list[dict[str, Any]]


def assess_plugin_quality(manifest: dict[str, Any]) -> PluginQualityAssessment:
    """Assess manifest quality using deterministic local dimensions."""

    dimensions = {
        "documentation": _documentation_score(manifest),
        "testing": _testing_score(manifest),
        "security_posture": _security_score(manifest),
        "operational_readiness": _operational_score(manifest),
    }
    findings: list[dict[str, Any]] = []
    for dimension, result in dimensions.items():
        if result["score"] < 60:
            findings.append(
                {
                    "code": f"low_{dimension}",
                    "dimension": dimension,
                    "severity": "warning",
                    "message": result["recommendation"],
                    "score": result["score"],
                }
            )
    score = round(sum(item["score"] for item in dimensions.values()) / len(dimensions), 1)
    return PluginQualityAssessment(score=score, dimensions=dimensions, findings=findings)


def _documentation_score(manifest: dict[str, Any]) -> dict[str, Any]:
    docs = manifest.get("documentation") or {}
    score = 0
    score += 30 if docs.get("readme") else 0
    score += 30 if docs.get("examples") else 0
    score += 25 if docs.get("api_docs") else 0
    score += 15 if docs.get("changelog") else 0
    return {
        "score": score,
        "recommendation": "Add README, examples, API docs, and changelog before broad installation.",
    }


def _testing_score(manifest: dict[str, Any]) -> dict[str, Any]:
    tests = manifest.get("tests") or {}
    test_count = int(tests.get("count") or 0)
    score = min(test_count * 4, 60)
    score += 25 if tests.get("integration") else 0
    score += 15 if tests.get("edge_cases") else 0
    return {
        "score": min(score, 100),
        "recommendation": "Add unit, integration, and edge-case tests.",
    }


def _security_score(manifest: dict[str, Any]) -> dict[str, Any]:
    permissions = set(manifest.get("permissions") or [])
    dangerous = {"filesystem.write", "network.raw", "secrets.read"}
    score = 100
    if not manifest.get("signature"):
        score -= 35
    score -= min(len(permissions & dangerous) * 25, 50)
    return {
        "score": max(score, 0),
        "recommendation": "Sign the package and reduce high-risk permissions.",
    }


def _operational_score(manifest: dict[str, Any]) -> dict[str, Any]:
    operations = manifest.get("operations") or {}
    score = 0
    score += 35 if operations.get("health_check") else 0
    score += 35 if operations.get("rollback") else 0
    score += 30 if operations.get("owner") else 0
    return {
        "score": score,
        "recommendation": "Declare health checks, rollback steps, and owner metadata.",
    }
