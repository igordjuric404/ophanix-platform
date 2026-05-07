"""Health probe adapter for Tool Gateway upstream targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from product_platform.db.time import utc_now_iso
from product_platform.tool_gateway.repository import (
    ToolRegistryRepository,
    ToolUpstreamTargetNotFoundError,
    tool_upstream_health_response,
)
from product_platform.tool_gateway.models import ToolUpstreamHealthResponse


@dataclass(frozen=True)
class ToolUpstreamHealthProbeResult:
    """Result of one upstream health probe."""

    target_id: str
    status: str
    checked_at: str
    error: str | None = None
    observed_status: int | None = None


class ToolUpstreamHealthChecker:
    """Run and persist health probes for registered upstream targets."""

    def __init__(
        self,
        repository: ToolRegistryRepository,
        *,
        http_client: Any | None = None,
    ) -> None:
        self.repository = repository
        self.http_client = http_client or httpx.Client()

    def check_target(self, target_id: str) -> ToolUpstreamHealthResponse:
        """Run one health check and persist the resulting target status."""

        target = self.repository.get_upstream_target(target_id)
        health = self.repository.get_upstream_health(target_id)
        if target is None or health is None:
            raise ToolUpstreamTargetNotFoundError("Upstream target not found.")
        checked_at = utc_now_iso()
        if not bool(health["enabled"]):
            row = self.repository.record_upstream_health(
                target_id,
                status="disabled",
                checked_at=checked_at,
                error="Health check is disabled.",
            )
            return tool_upstream_health_response(row)

        timeout_seconds = int(target["timeout_ms"]) / 1000
        try:
            response = self.http_client.get(health["health_url"], timeout=timeout_seconds)
            observed_status = int(response.status_code)
            expected_status = int(health["expected_status"])
            if observed_status == expected_status:
                status = "healthy"
                error = None
            else:
                status = "degraded"
                error = f"Expected status {expected_status}, received {observed_status}."
        except httpx.TimeoutException:
            status = "unhealthy"
            error = "Health check timed out."
        except Exception as exc:
            status = "unhealthy"
            error = _summarize_exception(exc)
        row = self.repository.record_upstream_health(
            target_id,
            status=status,
            checked_at=checked_at,
            error=error,
        )
        return tool_upstream_health_response(row)


def _summarize_exception(exc: Exception) -> str:
    summary = f"{exc.__class__.__name__}: {exc}"
    return summary[:300]
