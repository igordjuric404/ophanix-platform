"""Thin Python client for calling the Tool Gateway HTTP contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import quote
from urllib.parse import urlparse

import httpx


class TokenProvider(Protocol):
    """Supplies bearer tokens for gateway requests."""

    def get_token(self) -> str:
        """Return the raw bearer token without the `Bearer` prefix."""


@dataclass(frozen=True)
class StaticTokenProvider:
    """Token provider for callers that already have a long-lived gateway token."""

    token: str

    def get_token(self) -> str:
        token = self.token.strip()
        if not token:
            raise ValueError("token is required")
        return token


@dataclass(frozen=True)
class ToolCallResult:
    """Typed response returned by a successful gateway invocation."""

    request_id: str
    correlation_id: str
    tool_name: str
    result: Any | None = None
    reason_code: str | None = None
    decision: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolDefinition:
    """SDK view of a Tool Gateway contract."""

    id: str
    name: str
    display_name: str
    description: str
    owner_team: str
    status: str
    required_scope: str
    input_schema_json: dict[str, Any] | None = None
    output_schema_json: dict[str, Any] | None = None
    latest_version: dict[str, Any] | None = None
    versions: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


class ToolGatewayError(RuntimeError):
    """Base SDK error for gateway, upstream, and transport failures."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        request_id: str | None = None,
        correlation_id: str | None = None,
        response_body: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        self.correlation_id = correlation_id
        self.response_body = response_body or {}


class ToolDeniedError(ToolGatewayError):
    """Raised when gateway policy denies a tool call."""

    def __init__(
        self,
        message: str,
        *,
        reason_code: str | None = None,
        status_code: int | None = 403,
        request_id: str | None = None,
        correlation_id: str | None = None,
        response_body: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status_code,
            code=reason_code,
            request_id=request_id,
            correlation_id=correlation_id,
            response_body=response_body,
        )
        self.reason_code = reason_code


class OphanixToolGatewayClient:
    """Small synchronous SDK client for external Python agents."""

    def __init__(
        self,
        *,
        base_url: str,
        token_provider: TokenProvider,
        timeout_seconds: float = 5.0,
        http_client: httpx.Client | None = None,
        cache_tools: bool = False,
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        if token_provider is None:
            raise ValueError("token_provider is required")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self.token_provider = token_provider
        self.timeout_seconds = float(timeout_seconds)
        self.cache_tools = cache_tools
        self._tool_cache: dict[str, ToolDefinition] | None = {} if cache_tools else None
        self._list_cache: dict[tuple[tuple[str, str], ...], list[ToolDefinition]] | None = (
            {} if cache_tools else None
        )
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(timeout=self.timeout_seconds)

    def close(self) -> None:
        """Close the underlying HTTP client if this SDK instance created it."""

        if self._owns_http_client:
            self._http_client.close()

    def call_tool(
        self,
        tool_name: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> ToolCallResult:
        """Invoke one registered gateway tool with bearer authentication."""

        normalized_tool_name = _require_text(tool_name, "tool_name")
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dictionary")
        body: dict[str, Any] = {"payload": payload}
        headers = self._auth_headers()
        normalized_correlation_id = _optional_text(correlation_id)
        if normalized_correlation_id is not None:
            body["correlation_id"] = normalized_correlation_id
            headers["X-Correlation-ID"] = normalized_correlation_id
        try:
            response = self._http_client.post(
                f"{self.base_url}/api/v1/tools/{quote(normalized_tool_name, safe='')}/invoke",
                json=body,
                headers=headers,
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise ToolGatewayError(str(exc), code="transport_error") from exc
        response_body = _response_json(response)
        if response.status_code == 403:
            _raise_denied(response_body, response.status_code)
        if response.status_code >= 400:
            _raise_gateway_error(response_body, response.status_code)
        return _tool_call_result(response_body)

    def list_tools(
        self,
        *,
        status: str | None = None,
        owner_team: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ToolDefinition]:
        """List Tool Gateway contracts visible to the configured caller."""

        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset must be greater than or equal to zero")
        params: list[tuple[str, str]] = []
        normalized_status = _optional_text(status)
        normalized_owner_team = _optional_text(owner_team)
        if normalized_status is not None:
            params.append(("status", normalized_status))
        if normalized_owner_team is not None:
            params.append(("owner_team", normalized_owner_team))
        params.append(("limit", str(limit)))
        params.append(("offset", str(offset)))
        cache_key = tuple(params)
        if self._list_cache is not None and cache_key in self._list_cache:
            return list(self._list_cache[cache_key])
        try:
            response = self._http_client.get(
                f"{self.base_url}/api/v1/tools",
                params=params,
                headers=self._auth_headers(),
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise ToolGatewayError(str(exc), code="transport_error") from exc
        response_data = _response_data(response)
        if response.status_code >= 400:
            _raise_gateway_error(_mapping_response(response_data), response.status_code)
        if not isinstance(response_data, list):
            raise ToolGatewayError("Tool Gateway returned an invalid tools response.")
        tools = [_tool_definition(item) for item in response_data if isinstance(item, dict)]
        self._remember_tools(tools)
        if self._list_cache is not None:
            self._list_cache[cache_key] = list(tools)
        return tools

    def get_tool(self, tool_name: str) -> ToolDefinition:
        """Return one tool definition by name or id from the list contract."""

        normalized_tool_name = _require_text(tool_name, "tool_name")
        if self._tool_cache is not None and normalized_tool_name in self._tool_cache:
            return self._tool_cache[normalized_tool_name]
        tools = self.list_tools(limit=200)
        for tool in tools:
            if tool.name == normalized_tool_name or tool.id == normalized_tool_name:
                return tool
        raise ToolGatewayError(
            f"Tool not found: {normalized_tool_name}",
            status_code=404,
            code="tool_not_found",
        )

    def __enter__(self) -> OphanixToolGatewayClient:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def _auth_headers(self) -> dict[str, str]:
        token = self.token_provider.get_token().strip()
        if not token:
            raise ValueError("token is required")
        return {"Authorization": f"Bearer {token}"}

    def _remember_tools(self, tools: list[ToolDefinition]) -> None:
        if self._tool_cache is None:
            return
        for tool in tools:
            self._tool_cache[tool.name] = tool
            self._tool_cache[tool.id] = tool


def _normalize_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("base_url is required")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be an absolute http or https URL")
    return normalized


def _tool_call_result(body: dict[str, Any]) -> ToolCallResult:
    return ToolCallResult(
        request_id=str(body.get("request_id") or ""),
        correlation_id=str(body.get("correlation_id") or ""),
        tool_name=str(body.get("tool_name") or ""),
        reason_code=body.get("reason_code"),
        decision=_optional_mapping(body.get("decision")),
        result=body.get("result"),
        raw=body,
    )


def _tool_definition(body: dict[str, Any]) -> ToolDefinition:
    return ToolDefinition(
        id=str(body.get("id") or ""),
        name=str(body.get("name") or ""),
        display_name=str(body.get("display_name") or ""),
        description=str(body.get("description") or ""),
        owner_team=str(body.get("owner_team") or ""),
        status=str(body.get("status") or ""),
        required_scope=str(body.get("required_scope") or ""),
        input_schema_json=_optional_mapping(body.get("input_schema_json")),
        output_schema_json=_optional_mapping(body.get("output_schema_json")),
        latest_version=_optional_mapping(body.get("latest_version")),
        versions=_mapping_list(body.get("versions")),
        raw=body,
    )


def _raise_denied(body: dict[str, Any], status_code: int) -> None:
    error = _optional_mapping(body.get("error")) or {}
    reason_code = body.get("reason_code") or error.get("code")
    message = str(error.get("message") or "Tool call denied by gateway policy.")
    raise ToolDeniedError(
        message,
        reason_code=str(reason_code) if reason_code is not None else None,
        status_code=status_code,
        request_id=_optional_string(body.get("request_id")),
        correlation_id=_optional_string(body.get("correlation_id")),
        response_body=body,
    )


def _raise_gateway_error(body: dict[str, Any], status_code: int) -> None:
    error = _optional_mapping(body.get("error")) or {}
    code = error.get("code") or body.get("reason_code")
    message = str(error.get("message") or f"Tool Gateway returned HTTP {status_code}.")
    raise ToolGatewayError(
        message,
        status_code=status_code,
        code=str(code) if code is not None else None,
        request_id=_optional_string(body.get("request_id")),
        correlation_id=_optional_string(body.get("correlation_id")),
        response_body=body,
    )


def _response_json(response: httpx.Response) -> dict[str, Any]:
    return _mapping_response(_response_data(response))


def _response_data(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"error": {"message": response.text}}


def _mapping_response(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"result": value}


def _optional_mapping(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _optional_string(value: Any) -> str | None:
    return str(value) if value is not None else None


def _require_text(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} is required")
    return stripped


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
