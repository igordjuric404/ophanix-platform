"""Health probe adapter for Tool Gateway upstream targets."""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

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
        self._owns_http_client = http_client is None
        self.http_client = http_client or httpx.Client()

    def close(self) -> None:
        """Close the owned HTTP client when this checker created it."""

        if self._owns_http_client:
            close = getattr(self.http_client, "close", None)
            if callable(close):
                close()

    def check_target(self, target_id: str) -> ToolUpstreamHealthResponse:
        """Run one health check and persist the resulting target status."""

        return self._record_probe_result(target_id, self._probe_target(target_id))

    async def check_target_async(self, target_id: str) -> ToolUpstreamHealthResponse:
        """Run one health check with either a sync or async HTTP client."""

        return self._record_probe_result(target_id, await self._probe_target_async(target_id))

    def _target_and_health(self, target_id: str) -> tuple[Any, Any]:
        target = self.repository.get_upstream_target(target_id)
        health = self.repository.get_upstream_health(target_id)
        if target is None or health is None:
            raise ToolUpstreamTargetNotFoundError("Upstream target not found.")
        return target, health

    def _disabled_result(self, target_id: str, health: Any) -> ToolUpstreamHealthProbeResult | None:
        checked_at = utc_now_iso()
        if not bool(health["enabled"]):
            return ToolUpstreamHealthProbeResult(
                target_id=target_id,
                status="disabled",
                checked_at=checked_at,
                error="Health check is disabled.",
            )
        return None

    def _probe_target(self, target_id: str) -> ToolUpstreamHealthProbeResult:
        target, health = self._target_and_health(target_id)
        disabled = self._disabled_result(target_id, health)
        if disabled is not None:
            return disabled
        checked_at = utc_now_iso()
        timeout_seconds = int(target["timeout_ms"]) / 1000
        try:
            if isinstance(self.http_client, httpx.AsyncClient):
                raise TypeError("Async health clients must use check_target_async().")
            response = self.http_client.get(health["health_url"], timeout=timeout_seconds)
            if inspect.isawaitable(response):
                raise TypeError("Async health clients must use check_target_async().")
            status, error, observed_status = _status_from_response(response, health)
        except httpx.TimeoutException:
            status = "unhealthy"
            error = "Health check timed out."
            observed_status = None
        except Exception as exc:
            status = "unhealthy"
            error = _summarize_exception(exc)
            observed_status = None
        return ToolUpstreamHealthProbeResult(
            target_id=target_id,
            status=status,
            checked_at=checked_at,
            error=error,
            observed_status=observed_status,
        )

    async def _probe_target_async(self, target_id: str) -> ToolUpstreamHealthProbeResult:
        target, health = self._target_and_health(target_id)
        disabled = self._disabled_result(target_id, health)
        if disabled is not None:
            return disabled
        checked_at = utc_now_iso()
        timeout_seconds = int(target["timeout_ms"]) / 1000
        try:
            maybe_response = self.http_client.get(health["health_url"], timeout=timeout_seconds)
            response = await maybe_response if inspect.isawaitable(maybe_response) else maybe_response
            status, error, observed_status = _status_from_response(response, health)
        except httpx.TimeoutException:
            status = "unhealthy"
            error = "Health check timed out."
            observed_status = None
        except Exception as exc:
            status = "unhealthy"
            error = _summarize_exception(exc)
            observed_status = None
        return ToolUpstreamHealthProbeResult(
            target_id=target_id,
            status=status,
            checked_at=checked_at,
            error=error,
            observed_status=observed_status,
        )

    def _record_probe_result(
        self,
        target_id: str,
        result: ToolUpstreamHealthProbeResult,
    ) -> ToolUpstreamHealthResponse:
        row = self.repository.record_upstream_health(
            target_id,
            status=result.status,
            checked_at=result.checked_at,
            error=result.error,
        )
        return tool_upstream_health_response(row)


def _status_from_response(response: Any, health: Any) -> tuple[str, str | None, int]:
    observed_status = int(response.status_code)
    expected_status = int(health["expected_status"])
    if observed_status == expected_status:
        return "healthy", None, observed_status
    return "degraded", f"Expected status {expected_status}, received {observed_status}.", observed_status


def _summarize_exception(exc: Exception) -> str:
    summary = _sanitize_error_text(f"{exc.__class__.__name__}: {exc}")
    return summary[:300]


def _sanitize_error_text(value: str) -> str:
    without_credentials = re.sub(r"//[^/@\s]+@", "//", value)
    return re.sub(r"https?://[^\s]+", _sanitize_url_match, without_credentials)


def _sanitize_url_match(match: re.Match[str]) -> str:
    raw_url = match.group(0)
    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        return "[redacted-url]"
    host = parsed.hostname or "[redacted-host]"
    port = f":{parsed.port}" if parsed.port is not None else ""
    return urlunsplit((parsed.scheme, f"{host}{port}", "[redacted-path]", "", ""))
