"""Runtime request/response contract for Tool Gateway invocation."""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import quote

import httpx

from pydantic import BaseModel, Field, field_validator

from product_platform.tool_gateway.decision import ToolPolicyDecisionResult

MAX_UPSTREAM_TEXT_BODY_CHARS = 8192


class ToolInvocationRequest(BaseModel):
    """External agent request to invoke a registered tool."""

    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None

    @field_validator("correlation_id")
    @classmethod
    def _strip_correlation_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ToolInvocationResponse(BaseModel):
    """Stable response envelope for allowed and denied tool calls."""

    request_id: str
    correlation_id: str
    tool_name: str
    decision: ToolPolicyDecisionResult | None = None
    reason_code: str | None = None
    result: Any | None = None
    error: dict[str, Any] | None = None


class ToolExecutionResult(BaseModel):
    """Normalized result returned by a tool executor."""

    status: str
    body: Any | None = None
    headers_summary: dict[str, str] = Field(default_factory=dict)
    latency_ms: float | None = None
    upstream_status_code: int | None = None
    error: dict[str, Any] | None = None
    response_schema_valid: bool | None = None
    redaction_applied: bool = False
    exposed_to_agent: bool = True
    warnings: list[str] = Field(default_factory=list)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        status = value.strip().lower()
        if status not in {"succeeded", "failed"}:
            raise ValueError("status must be one of: failed, succeeded.")
        return status


class ToolExecutionError(RuntimeError):
    """Controlled executor failure safe to return to gateway callers."""

    def __init__(self, *, code: str, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class HttpToolInvocationExecutor:
    """Forward allowed tool calls to registered upstream HTTP targets."""

    def __init__(
        self,
        repository: Any,
        *,
        http_client: Any | None = None,
        fail_closed_unhealthy: bool = True,
    ) -> None:
        self.repository = repository
        self._owns_http_client = http_client is None
        self.http_client = http_client or httpx.Client()
        self.fail_closed_unhealthy = fail_closed_unhealthy

    def close(self) -> None:
        """Close the owned HTTP client when this executor created it."""

        if self._owns_http_client:
            close = getattr(self.http_client, "close", None)
            if callable(close):
                close()

    def execute(
        self,
        *,
        tool: Any,
        payload: dict[str, Any],
        decision: ToolPolicyDecisionResult,
        principal: Any,
    ) -> ToolExecutionResult:
        target = self.repository.get_upstream_target_for_tool(tool["id"])
        if target is None:
            raise ToolExecutionError(
                code="upstream_target_missing",
                message="No active upstream target is configured for this tool.",
                status_code=502,
            )
        if self.fail_closed_unhealthy and target["status"] == "unhealthy":
            raise ToolExecutionError(
                code="upstream_target_unhealthy",
                message="Configured upstream target is unhealthy.",
                status_code=503,
            )
        if target["auth_mode"] != "none":
            raise ToolExecutionError(
                code="upstream_auth_mode_unsupported",
                message="Configured upstream authentication mode is not supported.",
                status_code=502,
            )

        url = build_upstream_url(target, payload)
        headers = {
            "X-Request-ID": decision.request_id,
            "X-Correlation-ID": decision.correlation_id or decision.request_id,
            "X-Ophanix-Decision-ID": decision.id,
            "X-Ophanix-Agent-ID": principal.agent_id,
        }
        timeout_seconds = int(target["timeout_ms"]) / 1000
        started = time.perf_counter()
        try:
            response = self.http_client.request(
                target["method"],
                url,
                headers=headers,
                timeout=timeout_seconds,
                **_request_payload_kwargs(target["method"], payload),
            )
        except httpx.TimeoutException as exc:
            raise ToolExecutionError(
                code="upstream_timeout",
                message="Upstream request timed out.",
                status_code=504,
            ) from exc
        except Exception as exc:
            raise ToolExecutionError(
                code="upstream_connection_error",
                message="Upstream request failed.",
                status_code=502,
            ) from exc
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        upstream_status_code = int(response.status_code)
        succeeded = 200 <= upstream_status_code < 400
        body = _response_body(response)
        return ToolExecutionResult(
            status="succeeded" if succeeded else "failed",
            body=body,
            headers_summary=_headers_summary(response),
            latency_ms=latency_ms,
            upstream_status_code=upstream_status_code,
            error=None
            if succeeded
            else {
                "code": "upstream_error",
                "message": f"Upstream returned status {upstream_status_code}.",
            },
        )


class InMemoryToolInvocationExecutor:
    """Default local executor used until upstream forwarding is implemented."""

    def execute(
        self,
        *,
        tool: Any,
        payload: dict[str, Any],
        decision: ToolPolicyDecisionResult,
        principal: Any,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            status="succeeded",
            body={
                "status": "executed",
                "tool_name": tool["name"],
                "payload": payload,
            },
            headers_summary={},
            latency_ms=0.0,
            upstream_status_code=None,
        )


def build_upstream_url(target: Any, payload: dict[str, Any]) -> str:
    """Build an upstream URL from a target row and path-template payload values."""

    base_url = str(target["base_url"]).rstrip("/")
    path_template = str(target["path_template"])

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in payload:
            raise ToolExecutionError(
                code="path_parameter_missing",
                message=f"Missing path parameter: {key}.",
                status_code=422,
            )
        return quote(str(payload[key]), safe="")

    path = re.sub(r"\{([^{}]+)\}", replace, path_template)
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base_url}{path}"


def _response_body(response: Any) -> Any:
    try:
        return response.json()
    except Exception:
        text = getattr(response, "text", None)
        if isinstance(text, str) and len(text) > MAX_UPSTREAM_TEXT_BODY_CHARS:
            return f"{text[:MAX_UPSTREAM_TEXT_BODY_CHARS - 3]}..."
        return text


def _request_payload_kwargs(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized_method = method.upper()
    if normalized_method in {"GET", "DELETE"}:
        return {"params": payload}
    return {"json": payload}


def _headers_summary(response: Any) -> dict[str, str]:
    headers = getattr(response, "headers", {}) or {}
    summary: dict[str, str] = {}
    for key in ["content-type", "x-request-id", "x-correlation-id"]:
        value = _header_value(headers, key)
        if value is not None:
            summary[key] = value
    return summary


def _header_value(headers: Any, key: str) -> str | None:
    try:
        value = headers.get(key)
    except AttributeError:
        value = None
    if value is None and isinstance(headers, dict):
        for header_key, header_value in headers.items():
            if str(header_key).lower() == key:
                value = header_value
                break
    if value is None:
        return None
    return str(value)
