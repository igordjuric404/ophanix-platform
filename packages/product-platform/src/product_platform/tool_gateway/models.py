"""Tool Gateway API and repository data models."""

from __future__ import annotations

import re
import ipaddress
import socket
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

SUPPORTED_TOOL_STATUSES = {"draft", "active", "disabled", "retired"}
TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")
SUPPORTED_UPSTREAM_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
SUPPORTED_UPSTREAM_AUTH_MODES = {"none"}
SUPPORTED_UPSTREAM_STATUSES = {"configured", "healthy", "degraded", "unhealthy", "disabled"}
SUPPORTED_AGENT_TOOL_PERMISSION_STATUSES = {"active", "paused", "revoked", "expired"}


class ToolDefinitionCreateRequest(BaseModel):
    """Create a tenant-scoped callable tool contract."""

    name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str = ""
    owner_team: str = Field(min_length=1)
    required_scope: str = Field(min_length=1)
    input_schema_json: dict[str, Any] | None = None
    output_schema_json: dict[str, Any] | None = None
    status: str = "draft"

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not TOOL_NAME_PATTERN.match(normalized):
            raise ValueError("name must start with a letter and contain lowercase letters, numbers, dots, underscores, or hyphens.")
        return normalized

    @field_validator("display_name", "owner_team", "required_scope")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("description")
    @classmethod
    def _strip_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        status = value.strip().lower()
        if status not in SUPPORTED_TOOL_STATUSES:
            supported = ", ".join(sorted(SUPPORTED_TOOL_STATUSES))
            raise ValueError(f"status must be one of: {supported}.")
        return status


class ToolDefinitionPatchRequest(BaseModel):
    """Patch mutable tool contract fields."""

    display_name: str | None = None
    description: str | None = None
    owner_team: str | None = None
    required_scope: str | None = None
    input_schema_json: dict[str, Any] | None = None
    output_schema_json: dict[str, Any] | None = None
    change_summary: str | None = None

    @field_validator("display_name", "owner_team", "required_scope")
    @classmethod
    def _strip_optional_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("description", "change_summary")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ToolLifecycleActionRequest(BaseModel):
    """Optional lifecycle action metadata."""

    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ToolDefinitionVersionResponse(BaseModel):
    """Persisted version of a tool contract."""

    id: str
    tool_id: str
    version: int
    input_schema_json: dict[str, Any] | None = None
    output_schema_json: dict[str, Any] | None = None
    required_scope: str
    change_summary: str
    created_by: str
    created_at: str


class ToolDefinitionResponse(BaseModel):
    """Persisted tool definition returned by the product API."""

    id: str
    organization_id: str
    environment_id: str
    name: str
    display_name: str
    description: str
    owner_team: str
    status: str
    required_scope: str
    input_schema_json: dict[str, Any] | None = None
    output_schema_json: dict[str, Any] | None = None
    created_by: str
    created_at: str
    updated_at: str
    latest_version: ToolDefinitionVersionResponse | None = None
    versions: list[ToolDefinitionVersionResponse] = Field(default_factory=list)


class GatewayToolDefinitionResponse(BaseModel):
    """Tool definition fields safe for authenticated agent SDK discovery."""

    id: str
    name: str
    display_name: str
    description: str
    owner_team: str
    status: str
    required_scope: str
    input_schema_json: dict[str, Any] | None = None
    output_schema_json: dict[str, Any] | None = None


class ToolUpstreamTargetCreateRequest(BaseModel):
    """Create an upstream target for a registered tool."""

    base_url: str = Field(min_length=1)
    path_template: str = Field(default="/", min_length=1)
    method: str = "POST"
    auth_mode: str = "none"
    timeout_ms: int = Field(default=5_000, ge=100, le=60_000)
    status: str = "configured"
    health_url: str | None = None
    expected_status: int = Field(default=200, ge=100, le=599)
    interval_seconds: int = Field(default=60, ge=1, le=86_400)
    health_enabled: bool = True

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, value: str) -> str:
        return validate_http_url(value, field="base_url")

    @field_validator("health_url")
    @classmethod
    def _validate_health_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_http_url(value, field="health_url")

    @field_validator("path_template")
    @classmethod
    def _validate_path_template(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped.startswith("/"):
            raise ValueError("path_template must start with '/'.")
        return stripped

    @field_validator("method")
    @classmethod
    def _validate_method(cls, value: str) -> str:
        method = value.strip().upper()
        if method not in SUPPORTED_UPSTREAM_METHODS:
            supported = ", ".join(sorted(SUPPORTED_UPSTREAM_METHODS))
            raise ValueError(f"method must be one of: {supported}.")
        return method

    @field_validator("auth_mode")
    @classmethod
    def _validate_auth_mode(cls, value: str) -> str:
        auth_mode = value.strip().lower()
        if auth_mode not in SUPPORTED_UPSTREAM_AUTH_MODES:
            supported = ", ".join(sorted(SUPPORTED_UPSTREAM_AUTH_MODES))
            raise ValueError(f"auth_mode must be one of: {supported}.")
        return auth_mode

    @field_validator("status")
    @classmethod
    def _validate_upstream_status(cls, value: str) -> str:
        status = value.strip().lower()
        if status not in SUPPORTED_UPSTREAM_STATUSES:
            supported = ", ".join(sorted(SUPPORTED_UPSTREAM_STATUSES))
            raise ValueError(f"status must be one of: {supported}.")
        return status


class ToolUpstreamTargetPatchRequest(BaseModel):
    """Patch upstream target settings and health probe configuration."""

    base_url: str | None = None
    path_template: str | None = None
    method: str | None = None
    auth_mode: str | None = None
    timeout_ms: int | None = Field(default=None, ge=100, le=60_000)
    status: str | None = None
    health_url: str | None = None
    expected_status: int | None = Field(default=None, ge=100, le=599)
    interval_seconds: int | None = Field(default=None, ge=1, le=86_400)
    health_enabled: bool | None = None

    @field_validator("base_url")
    @classmethod
    def _validate_optional_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_http_url(value, field="base_url")

    @field_validator("health_url")
    @classmethod
    def _validate_optional_health_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_http_url(value, field="health_url")

    @field_validator("path_template")
    @classmethod
    def _validate_optional_path_template(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped.startswith("/"):
            raise ValueError("path_template must start with '/'.")
        return stripped

    @field_validator("method")
    @classmethod
    def _validate_optional_method(cls, value: str | None) -> str | None:
        if value is None:
            return None
        method = value.strip().upper()
        if method not in SUPPORTED_UPSTREAM_METHODS:
            supported = ", ".join(sorted(SUPPORTED_UPSTREAM_METHODS))
            raise ValueError(f"method must be one of: {supported}.")
        return method

    @field_validator("auth_mode")
    @classmethod
    def _validate_optional_auth_mode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        auth_mode = value.strip().lower()
        if auth_mode not in SUPPORTED_UPSTREAM_AUTH_MODES:
            supported = ", ".join(sorted(SUPPORTED_UPSTREAM_AUTH_MODES))
            raise ValueError(f"auth_mode must be one of: {supported}.")
        return auth_mode

    @field_validator("status")
    @classmethod
    def _validate_optional_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        status = value.strip().lower()
        if status not in SUPPORTED_UPSTREAM_STATUSES:
            supported = ", ".join(sorted(SUPPORTED_UPSTREAM_STATUSES))
            raise ValueError(f"status must be one of: {supported}.")
        return status


class ToolUpstreamHealthResponse(BaseModel):
    """Persisted upstream health-check state."""

    id: str
    target_id: str
    health_url: str
    expected_status: int
    interval_seconds: int
    last_status: str | None = None
    last_checked_at: str | None = None
    last_error: str | None = None
    enabled: bool


class ToolUpstreamTargetResponse(BaseModel):
    """Persisted upstream target returned by the product API."""

    id: str
    organization_id: str
    environment_id: str
    tool_id: str
    tool_name: str | None = None
    base_url: str
    path_template: str
    method: str
    auth_mode: str
    timeout_ms: int
    status: str
    created_at: str
    updated_at: str
    health: ToolUpstreamHealthResponse | None = None


class AgentToolPermissionGrantRequest(BaseModel):
    """Grant one active agent access to one active tool."""

    tool_id: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    granted_reason: str = ""
    expires_at: str | None = None

    @field_validator("tool_id", "scope")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("granted_reason")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("expires_at")
    @classmethod
    def _validate_expires_at(cls, value: str | None) -> str | None:
        return _normalize_optional_utc_datetime(value, field="expires_at")


class AgentToolPermissionPatchRequest(BaseModel):
    """Patch mutable agent-tool permission fields."""

    scope: str | None = None
    expires_at: str | None = None

    @field_validator("scope")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("expires_at")
    @classmethod
    def _validate_expires_at(cls, value: str | None) -> str | None:
        return _normalize_optional_utc_datetime(value, field="expires_at")


class AgentToolPermissionActionRequest(BaseModel):
    """Reasoned permission lifecycle action."""

    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason must not be blank.")
        return stripped


class AgentToolPermissionHistoryResponse(BaseModel):
    """Persisted lifecycle history entry for an agent-tool permission."""

    id: str
    permission_id: str
    action: str
    actor_user_id: str
    reason: str | None = None
    previous_status: str | None = None
    new_status: str
    created_at: str


class AgentToolPermissionResponse(BaseModel):
    """Persisted agent-tool permission returned by the product API."""

    id: str
    organization_id: str
    environment_id: str
    agent_id: str
    agent_name: str | None = None
    tool_id: str
    tool_name: str | None = None
    tool_display_name: str | None = None
    scope: str
    status: str
    granted_by: str
    granted_reason: str
    granted_at: str
    revoked_by: str | None = None
    revoked_reason: str | None = None
    revoked_at: str | None = None
    expires_at: str | None = None


class ToolResponsePolicyPatchRequest(BaseModel):
    """Patch response handling controls for a tool."""

    max_response_bytes: int | None = Field(default=None, ge=1, le=1_000_000)
    redaction_rules_json: dict[str, Any] | None = None
    expose_to_agent: bool | None = None
    store_full_response: bool | None = None
    strict_output_validation: bool | None = None
    status: str | None = None

    @field_validator("redaction_rules_json")
    @classmethod
    def _validate_redaction_rules(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        return _validate_redaction_rules(value)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        status = value.strip().lower()
        if status not in {"active", "disabled"}:
            raise ValueError("status must be one of: active, disabled.")
        return status


class ToolResponsePolicyResponse(BaseModel):
    """Persisted response handling policy for a tool."""

    id: str
    organization_id: str
    environment_id: str
    tool_id: str
    max_response_bytes: int
    redaction_rules_json: dict[str, Any]
    expose_to_agent: bool
    store_full_response: bool
    strict_output_validation: bool
    status: str
    created_at: str
    updated_at: str


def validate_http_url(value: str, *, field: str) -> str:
    """Validate and normalize an HTTP(S) URL."""

    stripped = value.strip()
    parsed = urlparse(stripped)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field} must be an absolute http or https URL.")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"{field} must include a hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{field} must not include credentials.")
    if parsed.query or parsed.fragment:
        raise ValueError(f"{field} must not include a query string or fragment.")
    if parsed.scheme == "http":
        raise ValueError(f"{field} must use https for upstream targets.")
    if _is_forbidden_upstream_host(hostname):
        raise ValueError(f"{field} must not target private, loopback, link-local, or metadata hosts.")
    return stripped.rstrip("/")


def _validate_redaction_rules(value: dict[str, Any]) -> dict[str, Any]:
    allowed = {"redact_keys", "redact_patterns"}
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"unsupported redaction rule keys: {', '.join(sorted(unknown))}.")
    for key in ["redact_keys", "redact_patterns"]:
        if key in value and (
            not isinstance(value[key], list)
            or not all(isinstance(item, str) and item.strip() for item in value[key])
        ):
            raise ValueError(f"{key} must be a list of nonblank strings.")
    normalized = {
        key: [item.strip() for item in value.get(key, [])]
        for key in ["redact_keys", "redact_patterns"]
        if key in value
    }
    for pattern in normalized.get("redact_patterns", []):
        _validate_redaction_pattern(pattern)
    return normalized


def _validate_redaction_pattern(pattern: str) -> None:
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"invalid redaction regex pattern: {exc}") from exc
    if len(pattern) > 300:
        raise ValueError("redact_patterns entries must be 300 characters or fewer.")
    if re.search(r"\([^)]*[+*][^)]*\)[+*?]", pattern):
        raise ValueError("redact_patterns entries must not contain nested unbounded quantifiers.")
    if re.search(r"(?:\.\*|\.\+).*(?:\.\*|\.\+)", pattern):
        raise ValueError("redact_patterns entries must not contain multiple unbounded wildcards.")
    if re.search(r"(\[[^\]]+\]|\w)[+*].*(\[[^\]]+\]|\w)[+*]", pattern):
        raise ValueError("redact_patterns entries must not contain repeated unbounded atoms.")


def _is_forbidden_upstream_host(hostname: str) -> bool:
    lowered = hostname.strip().lower().rstrip(".")
    if lowered in {"localhost", "169.254.169.254", "metadata.google.internal"}:
        return True
    try:
        address = ipaddress.ip_address(lowered)
    except ValueError:
        return _hostname_resolves_to_forbidden_address(lowered)
    return _is_forbidden_upstream_address(address)


def _hostname_resolves_to_forbidden_address(hostname: str) -> bool:
    try:
        resolved = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        # Test and private DNS names are often not resolvable in local
        # development. Runtime network policy must still deny private egress.
        return False
    for item in resolved:
        sockaddr = item[4]
        if not sockaddr:
            continue
        try:
            address = ipaddress.ip_address(str(sockaddr[0]))
        except ValueError:
            continue
        if _is_forbidden_upstream_address(address):
            return True
    return False


def _is_forbidden_upstream_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _normalize_optional_utc_datetime(value: str | None, *, field: str) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        parsed = datetime.fromisoformat(stripped.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO 8601 timestamp with timezone.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone.")
    return parsed.astimezone(timezone.utc).isoformat()
