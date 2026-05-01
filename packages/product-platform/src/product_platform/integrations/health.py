"""Provider and integration health evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any


@dataclass(frozen=True)
class ProviderHealthResult:
    """Health check result."""

    status: str
    latency_ms: int
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def run_provider_health_test(provider_type: str, secret_value: str | None) -> ProviderHealthResult:
    """Run deterministic provider validation for demos and tests."""

    started = perf_counter()
    if not secret_value or secret_value.startswith("invalid"):
        return _result(started, "failed", "Provider secret is invalid or missing.", provider_type)
    if provider_type == "model_provider":
        return _result(started, "healthy", "Model provider credential accepted by no-op validation.", provider_type)
    if provider_type == "mcp_server":
        return _result(started, "healthy", "MCP server credential accepted by discovery health validation.", provider_type)
    if provider_type == "observability_provider":
        return _result(started, "healthy", "Observability provider endpoint/token validation succeeded.", provider_type)
    return _result(started, "healthy", "Provider credential accepted by generic validation.", provider_type)


def should_emit_repeated_failure_event(statuses: list[str], *, threshold: int = 2) -> bool:
    """Return true when the latest consecutive checks are failed."""

    if len(statuses) < threshold:
        return False
    return all(status == "failed" for status in statuses[:threshold])


def _result(started: float, status: str, message: str, provider_type: str) -> ProviderHealthResult:
    latency_ms = max(1, int((perf_counter() - started) * 1000))
    return ProviderHealthResult(
        status=status,
        latency_ms=latency_ms,
        message=message,
        details={"provider_type": provider_type},
    )
