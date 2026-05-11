"""Runtime request/response contract for Tool Gateway invocation."""

from __future__ import annotations

import inspect
import json
import math
import re
import time
from typing import Any
from urllib.parse import quote

import httpx

from pydantic import BaseModel, Field, field_validator

from product_platform.tool_gateway.decision import ToolPolicyDecisionResult
from product_platform.tool_gateway.models import validate_http_url

MAX_UPSTREAM_TEXT_BODY_CHARS = 8192
MAX_UPSTREAM_RESPONSE_BYTES = 1_000_000
MAX_INVOCATION_PAYLOAD_DEPTH = 50
MAX_CORRELATION_ID_LENGTH = 128
CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:/@+-]+$")
SECRET_LIKE_QUERY_KEY_TOKENS = {
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
}


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
        if len(stripped) > MAX_CORRELATION_ID_LENGTH:
            raise ValueError("correlation_id must be 128 characters or fewer.")
        if stripped and not CORRELATION_ID_PATTERN.fullmatch(stripped):
            raise ValueError("correlation_id contains unsupported characters.")
        return stripped or None

    @field_validator("payload")
    @classmethod
    def _validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_json_value(value, "payload", depth=0, seen=set())
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("payload must be JSON serializable with finite numbers.") from exc
        return value


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
        secret_provider: Any | None = None,
        fail_closed_unhealthy: bool = True,
        max_response_bytes: int = MAX_UPSTREAM_RESPONSE_BYTES,
    ) -> None:
        self.repository = repository
        self._owns_http_client = http_client is None
        self.http_client = http_client or httpx.Client()
        self.secret_provider = secret_provider
        self.fail_closed_unhealthy = fail_closed_unhealthy
        self.max_response_bytes = max_response_bytes

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
        url = build_upstream_url(target, payload)
        headers = {
            "X-Request-ID": decision.request_id,
            "X-Correlation-ID": decision.correlation_id or decision.request_id,
            "X-Ophanix-Decision-ID": decision.id,
            "X-Ophanix-Agent-ID": principal.agent_id,
        }
        headers.update(_upstream_auth_headers(target, self.secret_provider))
        timeout_seconds = int(target["timeout_ms"]) / 1000
        started = time.perf_counter()
        try:
            response = _send_limited_request(
                self.http_client,
                method=target["method"],
                url=url,
                headers=headers,
                timeout_seconds=timeout_seconds,
                max_response_bytes=self.max_response_bytes,
                request_kwargs=_request_payload_kwargs(
                    target["method"],
                    payload,
                    path_parameter_names=_path_parameter_names(target),
                    query_parameter_allowlist=_query_parameter_allowlist(target),
                ),
            )
        except ToolExecutionError:
            raise
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
        succeeded = 200 <= upstream_status_code < 300
        body = _response_body(response, max_response_bytes=self.max_response_bytes)
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


class AsyncHttpToolInvocationExecutor:
    """Forward allowed tool calls to upstream HTTP targets without blocking the event loop."""

    def __init__(
        self,
        repository: Any,
        *,
        http_client: Any | None = None,
        secret_provider: Any | None = None,
        fail_closed_unhealthy: bool = True,
        max_response_bytes: int = MAX_UPSTREAM_RESPONSE_BYTES,
    ) -> None:
        self.repository = repository
        self._owns_http_client = http_client is None
        self.http_client = http_client or httpx.AsyncClient()
        self.secret_provider = secret_provider
        self.fail_closed_unhealthy = fail_closed_unhealthy
        self.max_response_bytes = max_response_bytes

    async def close(self) -> None:
        """Close the owned async HTTP client when this executor created it."""

        if self._owns_http_client:
            aclose = getattr(self.http_client, "aclose", None)
            if callable(aclose):
                await aclose()
                return
            close = getattr(self.http_client, "close", None)
            if callable(close):
                close()

    async def execute(
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
        url = build_upstream_url(target, payload)
        headers = {
            "X-Request-ID": decision.request_id,
            "X-Correlation-ID": decision.correlation_id or decision.request_id,
            "X-Ophanix-Decision-ID": decision.id,
            "X-Ophanix-Agent-ID": principal.agent_id,
        }
        headers.update(_upstream_auth_headers(target, self.secret_provider))
        timeout_seconds = int(target["timeout_ms"]) / 1000
        started = time.perf_counter()
        try:
            maybe_response = _send_limited_request_async(
                self.http_client,
                method=target["method"],
                url=url,
                headers=headers,
                timeout_seconds=timeout_seconds,
                max_response_bytes=self.max_response_bytes,
                request_kwargs=_request_payload_kwargs(
                    target["method"],
                    payload,
                    path_parameter_names=_path_parameter_names(target),
                    query_parameter_allowlist=_query_parameter_allowlist(target),
                ),
            )
            response = await maybe_response if inspect.isawaitable(maybe_response) else maybe_response
        except ToolExecutionError:
            raise
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
        succeeded = 200 <= upstream_status_code < 300
        body = _response_body(response, max_response_bytes=self.max_response_bytes)
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

    try:
        base_url = validate_http_url(str(target["base_url"]), field="base_url")
    except ValueError as exc:
        raise ToolExecutionError(
            code="unsafe_upstream_url",
            message="Configured upstream target URL is not safe to invoke.",
            status_code=502,
        ) from exc
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


def _send_limited_request(
    http_client: Any,
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    timeout_seconds: float,
    max_response_bytes: int,
    request_kwargs: dict[str, Any],
) -> Any:
    stream = getattr(http_client, "stream", None)
    if callable(stream):
        with stream(
            method,
            url,
            headers=headers,
            timeout=timeout_seconds,
            **request_kwargs,
        ) as response:
            return _limited_response_from_sync_stream(
                response,
                max_response_bytes=max_response_bytes,
            )
    return http_client.request(
        method,
        url,
        headers=headers,
        timeout=timeout_seconds,
        **request_kwargs,
    )


async def _send_limited_request_async(
    http_client: Any,
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    timeout_seconds: float,
    max_response_bytes: int,
    request_kwargs: dict[str, Any],
) -> Any:
    stream = getattr(http_client, "stream", None)
    if callable(stream):
        async with stream(
            method,
            url,
            headers=headers,
            timeout=timeout_seconds,
            **request_kwargs,
        ) as response:
            return await _limited_response_from_async_stream(
                response,
                max_response_bytes=max_response_bytes,
            )
    maybe_response = http_client.request(
        method,
        url,
        headers=headers,
        timeout=timeout_seconds,
        **request_kwargs,
    )
    return await maybe_response if inspect.isawaitable(maybe_response) else maybe_response


def _limited_response_from_sync_stream(
    response: Any,
    *,
    max_response_bytes: int,
) -> httpx.Response:
    _ensure_content_length_within_limit(response, max_response_bytes=max_response_bytes)
    content = bytearray()
    for chunk in response.iter_bytes():
        content.extend(chunk)
        if len(content) > max_response_bytes:
            raise ToolExecutionError(
                code="upstream_response_too_large",
                message="Upstream response exceeds the configured size limit.",
                status_code=502,
            )
    return _materialized_response(response, bytes(content))


async def _limited_response_from_async_stream(
    response: Any,
    *,
    max_response_bytes: int,
) -> httpx.Response:
    _ensure_content_length_within_limit(response, max_response_bytes=max_response_bytes)
    content = bytearray()
    async for chunk in response.aiter_bytes():
        content.extend(chunk)
        if len(content) > max_response_bytes:
            raise ToolExecutionError(
                code="upstream_response_too_large",
                message="Upstream response exceeds the configured size limit.",
                status_code=502,
            )
    return _materialized_response(response, bytes(content))


def _materialized_response(response: Any, content: bytes) -> httpx.Response:
    request = getattr(response, "request", None)
    return httpx.Response(
        int(response.status_code),
        headers=getattr(response, "headers", None),
        content=content,
        request=request,
        extensions=getattr(response, "extensions", {}) or {},
    )


def _response_body(response: Any, *, max_response_bytes: int = MAX_UPSTREAM_RESPONSE_BYTES) -> Any:
    _ensure_content_length_within_limit(response, max_response_bytes=max_response_bytes)
    content = getattr(response, "content", None)
    if isinstance(content, bytes) and len(content) > max_response_bytes:
        raise ToolExecutionError(
            code="upstream_response_too_large",
            message="Upstream response exceeds the configured size limit.",
            status_code=502,
        )
    try:
        return response.json()
    except Exception:
        text = getattr(response, "text", None)
        if isinstance(text, str) and len(text) > MAX_UPSTREAM_TEXT_BODY_CHARS:
            return f"{text[:MAX_UPSTREAM_TEXT_BODY_CHARS - 3]}..."
        return text


def _ensure_content_length_within_limit(response: Any, *, max_response_bytes: int) -> None:
    headers = getattr(response, "headers", {}) or {}
    content_length = _header_value(headers, "content-length")
    if content_length is None:
        return
    try:
        too_large = int(content_length) > max_response_bytes
    except ValueError:
        return
    if too_large:
        raise ToolExecutionError(
            code="upstream_response_too_large",
            message="Upstream response exceeds the configured size limit.",
            status_code=502,
        )


def _request_payload_kwargs(
    method: str,
    payload: dict[str, Any],
    *,
    path_parameter_names: set[str] | None = None,
    query_parameter_allowlist: set[str] | None = None,
) -> dict[str, Any]:
    normalized_method = method.upper()
    if normalized_method in {"GET", "DELETE"}:
        path_parameter_names = path_parameter_names or set()
        query_payload = {
            key: value
            for key, value in payload.items()
            if key not in path_parameter_names
        }
        allowed_query_parameters = query_parameter_allowlist or set()
        if query_payload:
            if not allowed_query_parameters:
                raise ToolExecutionError(
                    code="query_parameter_not_allowed",
                    message=(
                        "GET and DELETE tool targets must declare query_parameter_allowlist "
                        "before payload fields can be serialized into the query string."
                    ),
                    status_code=422,
                )
        for key, value in query_payload.items():
            normalized_key = _normalize_key(key)
            if key not in allowed_query_parameters:
                raise ToolExecutionError(
                    code="query_parameter_not_allowed",
                    message="Payload field is not allowed as a query parameter for this tool target.",
                    status_code=422,
                )
            if any(token in normalized_key for token in SECRET_LIKE_QUERY_KEY_TOKENS):
                raise ToolExecutionError(
                    code="unsafe_query_payload",
                    message="GET and DELETE tool payloads must not place credential-like fields in query parameters.",
                    status_code=422,
                )
            if not isinstance(value, (str, int, float, bool)) and value is not None:
                raise ToolExecutionError(
                    code="unsupported_query_payload",
                    message="GET and DELETE tool query payload values must be scalar JSON values.",
                    status_code=422,
                )
        return {"params": query_payload}
    return {"json": payload}


def _path_parameter_names(target: Any) -> set[str]:
    return set(re.findall(r"\{([^{}]+)\}", str(target["path_template"])))


def _query_parameter_allowlist(target: Any) -> set[str]:
    value = _target_optional_value(target, "query_parameter_allowlist_json")
    if value is None:
        value = _target_optional_value(target, "query_parameter_allowlist")
    if value is None:
        return set()
    if isinstance(value, str):
        if not value.strip():
            return set()
        loaded = json.loads(value)
    else:
        loaded = value
    if not isinstance(loaded, list):
        return set()
    return {str(item) for item in loaded if isinstance(item, str) and item.strip()}


def _upstream_auth_headers(target: Any, secret_provider: Any | None) -> dict[str, str]:
    auth_mode = str(target["auth_mode"]).strip().lower()
    if auth_mode == "none":
        return {}
    auth_config = _target_json_mapping(target, "auth_config_json")
    secret_ref = str(auth_config.get("secret_ref") or "").strip()
    if not secret_ref:
        raise ToolExecutionError(
            code="upstream_auth_config_invalid",
            message="Configured upstream authentication is missing a secret reference.",
            status_code=502,
        )
    secret_value = _retrieve_upstream_secret(secret_provider, secret_ref)
    if auth_mode == "bearer":
        return {"Authorization": f"Bearer {secret_value}"}
    if auth_mode == "api_key":
        header_name = str(auth_config.get("header_name") or "X-API-Key").strip()
        header_prefix = str(auth_config.get("header_prefix") or "").strip()
        header_value = f"{header_prefix} {secret_value}" if header_prefix else secret_value
        return {header_name: header_value}
    raise ToolExecutionError(
        code="upstream_auth_mode_unsupported",
        message="Configured upstream authentication mode is not supported.",
        status_code=502,
    )


def _retrieve_upstream_secret(secret_provider: Any | None, secret_ref: str) -> str:
    if secret_provider is None:
        raise ToolExecutionError(
            code="upstream_auth_secret_unavailable",
            message="Configured upstream authentication secret is unavailable.",
            status_code=502,
        )
    retrieve = getattr(secret_provider, "retrieve", None)
    if not callable(retrieve):
        raise ToolExecutionError(
            code="upstream_auth_secret_unavailable",
            message="Configured upstream authentication secret is unavailable.",
            status_code=502,
        )
    secret_value = retrieve(secret_ref)
    if not isinstance(secret_value, str) or not secret_value:
        raise ToolExecutionError(
            code="upstream_auth_secret_unavailable",
            message="Configured upstream authentication secret is unavailable.",
            status_code=502,
        )
    return secret_value


def _target_json_mapping(target: Any, key: str) -> dict[str, Any]:
    value = _target_optional_value(target, key)
    if value is None:
        return {}
    if isinstance(value, str):
        if not value.strip():
            return {}
        loaded = json.loads(value)
    else:
        loaded = value
    return loaded if isinstance(loaded, dict) else {}


def _target_optional_value(target: Any, key: str) -> Any | None:
    try:
        return target[key]
    except Exception:
        return getattr(target, key, None)


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")


def _validate_json_value(
    value: Any,
    field_name: str,
    *,
    depth: int,
    seen: set[int],
) -> None:
    if depth > MAX_INVOCATION_PAYLOAD_DEPTH:
        raise ValueError(f"{field_name} exceeds maximum nesting depth.")
    if isinstance(value, dict):
        object_id = id(value)
        if object_id in seen:
            raise ValueError(f"{field_name} must not contain cycles.")
        seen.add(object_id)
        for key, child_value in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{field_name} keys must be strings.")
            _validate_json_value(child_value, field_name, depth=depth + 1, seen=seen)
        seen.remove(object_id)
        return
    if isinstance(value, list):
        object_id = id(value)
        if object_id in seen:
            raise ValueError(f"{field_name} must not contain cycles.")
        seen.add(object_id)
        for child_value in value:
            _validate_json_value(child_value, field_name, depth=depth + 1, seen=seen)
        seen.remove(object_id)
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field_name} must contain only finite numbers.")
    if isinstance(value, (str, int, float, bool)) or value is None:
        return
    raise ValueError(f"{field_name} must be JSON serializable.")


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
