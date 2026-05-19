"""Tool Gateway API and repository data models."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import regex as safe_regex
from pydantic import BaseModel, Field, field_validator, model_validator

SUPPORTED_TOOL_STATUSES = {"draft", "active", "disabled", "retired"}
TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")
SUPPORTED_UPSTREAM_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
SUPPORTED_UPSTREAM_AUTH_MODES = {"none", "api_key", "bearer", "oauth"}
SUPPORTED_UPSTREAM_STATUSES = {"configured", "healthy", "degraded", "unhealthy", "disabled"}
SUPPORTED_AGENT_TOOL_PERMISSION_STATUSES = {"active", "paused", "revoked", "expired"}
GATEWAY_CONTRACT_VERSION = "tool-gateway.v1"
UPSTREAM_AUTH_HEADER_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,127}$")
UPSTREAM_AUTH_HEADER_PREFIX_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]{0,63}$")
UPSTREAM_QUERY_PARAMETER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")


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

    @model_validator(mode="after")
    def _require_draft_create(self) -> "ToolDefinitionCreateRequest":
        if self.status != "draft":
            raise ValueError(
                "new tools must be created as draft; use lifecycle endpoints to activate, "
                "disable, or retire tools."
            )
        return self


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


class GatewayToolListPageResponse(BaseModel):
    """Cursor-paginated Tool Gateway discovery page."""

    tools: list[GatewayToolDefinitionResponse]
    next_cursor: str | None = None


class GatewayCapabilitiesResponse(BaseModel):
    """Authenticated SDK compatibility probe response."""

    gateway_contract_version: str = GATEWAY_CONTRACT_VERSION
    min_sdk_version: str = "0.1.0"
    sdk_package: str = "ophanix-tool-gateway-sdk"
    max_payload_bytes: int = 1_000_000
    max_response_bytes: int = 1_000_000
    max_discovery_page_size: int = 200
    supported_pagination_modes: list[str] = Field(default_factory=lambda: ["cursor", "offset"])
    supports_idempotency: bool = True
    idempotency_in_progress_ttl_seconds: int = 600
    idempotency_replay_retention_seconds: int = 604_800
    discovery_retryable_status_codes: list[int] = Field(
        default_factory=lambda: [408, 429, 500, 502, 503, 504]
    )
    invocation_retryable_status_codes: list[int] = Field(
        default_factory=lambda: [408, 429, 500, 502, 503, 504]
    )
    rate_limit_window_seconds: int = 60
    rate_limit_max_requests: int = 600
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_cooldown_seconds: int = 30


class ToolUpstreamTargetCreateRequest(BaseModel):
    """Create an upstream target for a registered tool."""

    base_url: str = Field(min_length=1)
    path_template: str = Field(default="/", min_length=1)
    method: str = "POST"
    auth_mode: str = "none"
    auth_config_json: dict[str, Any] | None = None
    timeout_ms: int = Field(default=5_000, ge=100, le=60_000)
    status: str = "configured"
    health_url: str | None = None
    expected_status: int = Field(default=200, ge=100, le=599)
    interval_seconds: int = Field(default=60, ge=1, le=86_400)
    health_enabled: bool = True
    query_parameter_allowlist: list[str] = Field(default_factory=list)

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

    @field_validator("auth_config_json")
    @classmethod
    def _validate_auth_config_json(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return normalize_upstream_auth_config(value)

    @field_validator("query_parameter_allowlist")
    @classmethod
    def _validate_query_parameter_allowlist(cls, value: list[str]) -> list[str]:
        return normalize_query_parameter_allowlist(value)

    @model_validator(mode="after")
    def _validate_auth_config_for_mode(self) -> "ToolUpstreamTargetCreateRequest":
        validate_upstream_auth_configuration(self.auth_mode, self.auth_config_json)
        return self

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
    auth_config_json: dict[str, Any] | None = None
    timeout_ms: int | None = Field(default=None, ge=100, le=60_000)
    status: str | None = None
    health_url: str | None = None
    expected_status: int | None = Field(default=None, ge=100, le=599)
    interval_seconds: int | None = Field(default=None, ge=1, le=86_400)
    health_enabled: bool | None = None
    query_parameter_allowlist: list[str] | None = None

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

    @field_validator("auth_config_json")
    @classmethod
    def _validate_optional_auth_config_json(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        return normalize_upstream_auth_config(value)

    @field_validator("query_parameter_allowlist")
    @classmethod
    def _validate_optional_query_parameter_allowlist(
        cls,
        value: list[str] | None,
    ) -> list[str] | None:
        if value is None:
            return None
        return normalize_query_parameter_allowlist(value)

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
    query_parameter_allowlist: list[str] = Field(default_factory=list)
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


def validate_http_url(
    value: str,
    *,
    field: str,
    allowed_hosts: list[str] | tuple[str, ...] | set[str] | None = None,
) -> str:
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
    validate_upstream_host_allowed(stripped, allowed_hosts=allowed_hosts, field=field)
    if _is_forbidden_upstream_host(hostname):
        raise ValueError(f"{field} must not target private, loopback, link-local, or metadata hosts.")
    return stripped.rstrip("/")


def validate_upstream_host_allowed(
    value: str,
    *,
    allowed_hosts: list[str] | tuple[str, ...] | set[str] | None,
    field: str,
) -> None:
    """Validate an upstream hostname against an optional exact/wildcard allowlist."""

    effective_allowed_hosts = list(allowed_hosts or _env_upstream_host_allowlist())
    if not effective_allowed_hosts:
        return
    parsed = urlparse(value.strip())
    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        raise ValueError(f"{field} must include a hostname.")
    if not any(_hostname_matches_allowed_pattern(hostname, pattern) for pattern in effective_allowed_hosts):
        raise ValueError(f"{field} hostname is not in the Tool Gateway upstream host allowlist.")


def normalize_upstream_auth_config(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Normalize upstream auth config without accepting inline secrets."""

    if value is None:
        return None
    allowed = {"header_name", "header_prefix", "oauth_provider", "required_scopes", "secret_ref"}
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"unsupported auth_config_json keys: {', '.join(sorted(unknown))}.")
    normalized: dict[str, Any] = {}
    secret_ref = _optional_str(value.get("secret_ref"))
    if secret_ref is not None:
        if _looks_like_inline_secret_key("secret_ref", secret_ref):
            raise ValueError("auth_config_json.secret_ref must be an opaque secret reference.")
        normalized["secret_ref"] = secret_ref
    header_name = _optional_str(value.get("header_name"))
    if header_name is not None:
        if not UPSTREAM_AUTH_HEADER_NAME_PATTERN.fullmatch(header_name):
            raise ValueError("auth_config_json.header_name must be a valid HTTP header name.")
        if header_name.lower() in {"authorization", "cookie", "set-cookie"}:
            raise ValueError("auth_config_json.header_name must not override sensitive headers.")
        normalized["header_name"] = header_name
    header_prefix = _optional_str(value.get("header_prefix"))
    if header_prefix is not None:
        if not UPSTREAM_AUTH_HEADER_PREFIX_PATTERN.fullmatch(header_prefix):
            raise ValueError(
                "auth_config_json.header_prefix must be a single HTTP authentication scheme token."
            )
        normalized["header_prefix"] = header_prefix
    oauth_provider = _optional_str(value.get("oauth_provider"))
    if oauth_provider is not None:
        normalized["oauth_provider"] = oauth_provider
    required_scopes = value.get("required_scopes")
    if required_scopes is not None:
        if not isinstance(required_scopes, list):
            raise ValueError("auth_config_json.required_scopes must be a list of strings.")
        normalized_scopes = []
        for scope in required_scopes:
            scope_text = _optional_str(scope)
            if scope_text and scope_text not in normalized_scopes:
                normalized_scopes.append(scope_text)
        normalized["required_scopes"] = normalized_scopes
    return normalized or None


def validate_upstream_auth_configuration(
    auth_mode: str,
    auth_config_json: dict[str, Any] | str | None,
) -> None:
    """Validate that an upstream auth mode has the required secret reference."""

    mode = auth_mode.strip().lower()
    config = _json_mapping(auth_config_json)
    if mode == "none":
        if config:
            raise ValueError("auth_config_json must be omitted when auth_mode is none.")
        return
    if mode not in SUPPORTED_UPSTREAM_AUTH_MODES:
        supported = ", ".join(sorted(SUPPORTED_UPSTREAM_AUTH_MODES))
        raise ValueError(f"auth_mode must be one of: {supported}.")
    if mode == "oauth":
        if not config or not str(config.get("oauth_provider", "")).strip():
            raise ValueError("auth_config_json.oauth_provider is required when auth_mode is oauth.")
        if str(config.get("secret_ref", "")).strip():
            raise ValueError("auth_config_json.secret_ref must not be used when auth_mode is oauth.")
        return
    if not config or not str(config.get("secret_ref", "")).strip():
        raise ValueError(f"auth_config_json.secret_ref is required when auth_mode is {mode}.")
    if mode == "bearer":
        return
    if mode == "api_key":
        header_name = str(config.get("header_name") or "X-API-Key")
        if not UPSTREAM_AUTH_HEADER_NAME_PATTERN.fullmatch(header_name):
            raise ValueError("auth_config_json.header_name must be a valid HTTP header name.")
        return


def normalize_query_parameter_allowlist(value: list[str]) -> list[str]:
    """Normalize explicit query-parameter names for GET/DELETE upstream targets."""

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        stripped = item.strip()
        if not stripped:
            raise ValueError("query_parameter_allowlist entries must not be blank.")
        if not UPSTREAM_QUERY_PARAMETER_PATTERN.fullmatch(stripped):
            raise ValueError(
                "query_parameter_allowlist entries must start with a letter and contain only "
                "letters, numbers, dots, underscores, or hyphens."
            )
        lowered = stripped.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(stripped)
    return normalized


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


def _json_mapping(value: dict[str, Any] | str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        if not value.strip():
            return None
        loaded = json.loads(value)
        if not isinstance(loaded, dict):
            raise ValueError("auth_config_json must be an object.")
        return loaded
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("auth_config_json values must be strings.")
    stripped = value.strip()
    return stripped or None


def _looks_like_inline_secret_key(key: str, value: str) -> bool:
    lowered_key = key.lower()
    lowered_value = value.lower()
    if lowered_key != "secret_ref":
        return False
    if len(value) > 256 or any(character.isspace() for character in value):
        return True
    if lowered_value.startswith(
        (
            "bearer ",
            "eyj",
            "ghp_",
            "github_pat_",
            "glpat-",
            "pk-",
            "pk_",
            "sk-",
            "sk_",
            "xoxa-",
            "xoxb-",
            "xoxp-",
            "xoxr-",
            "xoxs-",
        )
    ):
        return True
    if value.startswith(("AKIA", "ASIA", "-----BEGIN ")):
        return True
    return bool(re.fullmatch(r"[A-Za-z0-9+/]{32,}={0,2}", value))


def _validate_redaction_pattern(pattern: str) -> None:
    try:
        safe_regex.compile(pattern)
    except safe_regex.error as exc:
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
        return not _allow_unresolved_upstream_hosts()
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


def _allow_unresolved_upstream_hosts() -> bool:
    environment = os.environ.get("OPHANIX_ENVIRONMENT", "development").strip().lower()
    if _bool_env("OPHANIX_ALLOW_UNRESOLVED_UPSTREAM_HOSTS", False):
        return environment in {"development", "dev", "local", "test"}
    return False


def _env_upstream_host_allowlist() -> list[str]:
    raw = os.environ.get("OPHANIX_TOOL_GATEWAY_UPSTREAM_HOST_ALLOWLIST", "")
    return [value.strip().lower().rstrip(".") for value in raw.split(",") if value.strip()]


def _hostname_matches_allowed_pattern(hostname: str, pattern: str) -> bool:
    normalized_pattern = pattern.strip().lower().rstrip(".")
    if not normalized_pattern:
        return False
    if normalized_pattern.startswith("*."):
        suffix = normalized_pattern[1:]
        return hostname.endswith(suffix) and hostname != suffix.lstrip(".")
    return hostname == normalized_pattern


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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
