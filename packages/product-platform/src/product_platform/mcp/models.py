"""MCP registry API models."""

from __future__ import annotations

from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Any


SUPPORTED_MCP_AUTH_TYPES = {"none", "api_key", "bearer", "oauth", "mtls", "custom"}
SUPPORTED_MCP_SERVER_STATUSES = {"registered", "active", "disabled", "error"}
SUPPORTED_MCP_FINDING_STATUSES = {"open", "accepted_risk", "resolved", "false_positive"}


class MCPServerCreateRequest(BaseModel):
    """Register an MCP server as a product resource."""

    name: str = Field(min_length=1)
    endpoint_url: str = Field(min_length=1)
    owner_user_id: str = Field(min_length=1)
    auth_type: str = "none"
    status: str = "registered"
    policy_pack_id: str | None = None

    @field_validator("name", "owner_user_id")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("endpoint_url")
    @classmethod
    def _validate_endpoint_url(cls, value: str) -> str:
        return validate_mcp_endpoint_url(value)

    @field_validator("auth_type")
    @classmethod
    def _validate_auth_type(cls, value: str) -> str:
        auth_type = value.strip().lower()
        if auth_type not in SUPPORTED_MCP_AUTH_TYPES:
            supported = ", ".join(sorted(SUPPORTED_MCP_AUTH_TYPES))
            raise ValueError(f"auth_type must be one of: {supported}.")
        return auth_type

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        status = value.strip().lower()
        if status not in SUPPORTED_MCP_SERVER_STATUSES:
            supported = ", ".join(sorted(SUPPORTED_MCP_SERVER_STATUSES))
            raise ValueError(f"status must be one of: {supported}.")
        return status

    @field_validator("policy_pack_id")
    @classmethod
    def _strip_optional_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class MCPServerPatchRequest(BaseModel):
    """Patch MCP server registry metadata."""

    name: str | None = None
    endpoint_url: str | None = None
    owner_user_id: str | None = None
    auth_type: str | None = None
    status: str | None = None
    policy_pack_id: str | None = None

    @field_validator("name", "owner_user_id")
    @classmethod
    def _strip_optional_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("endpoint_url")
    @classmethod
    def _validate_optional_endpoint_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_mcp_endpoint_url(value)

    @field_validator("auth_type")
    @classmethod
    def _validate_optional_auth_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        auth_type = value.strip().lower()
        if auth_type not in SUPPORTED_MCP_AUTH_TYPES:
            supported = ", ".join(sorted(SUPPORTED_MCP_AUTH_TYPES))
            raise ValueError(f"auth_type must be one of: {supported}.")
        return auth_type

    @field_validator("status")
    @classmethod
    def _validate_optional_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        status = value.strip().lower()
        if status not in SUPPORTED_MCP_SERVER_STATUSES:
            supported = ", ".join(sorted(SUPPORTED_MCP_SERVER_STATUSES))
            raise ValueError(f"status must be one of: {supported}.")
        return status

    @field_validator("policy_pack_id")
    @classmethod
    def _strip_optional_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class MCPServerResponse(BaseModel):
    """Persisted MCP server registry record."""

    id: str
    organization_id: str
    environment_id: str
    name: str
    endpoint_url: str
    owner_user_id: str
    owner_display_name: str | None = None
    owner_email: str | None = None
    auth_type: str
    status: str
    policy_pack_id: str | None = None
    tool_count: int = 0
    created_at: str
    updated_at: str
    last_discovered_at: str | None = None


class MCPToolVersionResponse(BaseModel):
    """Persisted MCP tool schema version."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    tool_id: str
    input_schema: dict[str, Any] = Field(
        default_factory=dict,
        serialization_alias="schema",
        validation_alias="schema",
    )
    schema_hash: str
    definition: dict[str, Any] = Field(default_factory=dict)
    discovered_at: str
    scan_status: str


class MCPToolResponse(BaseModel):
    """Persisted MCP tool registry record."""

    id: str
    server_id: str
    server_name: str | None = None
    name: str
    description: str
    current_version_id: str | None = None
    current_version: MCPToolVersionResponse | None = None
    versions: list[MCPToolVersionResponse] = Field(default_factory=list)
    risk_level: str
    status: str
    created_at: str
    updated_at: str


class MCPToolDiscoveryResponse(BaseModel):
    """Result of discovering tools for one MCP server."""

    server_id: str
    discovered_count: int
    tools: list[MCPToolResponse] = Field(default_factory=list)


class MCPScanRunResponse(BaseModel):
    """Persisted MCP security scan run."""

    id: str
    server_id: str
    server_name: str | None = None
    status: str
    started_at: str
    finished_at: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    findings: list["MCPFindingResponse"] = Field(default_factory=list)


class MCPFindingResponse(BaseModel):
    """Persisted MCP security finding."""

    id: str
    scan_run_id: str
    server_id: str | None = None
    server_name: str | None = None
    tool_id: str
    tool_name: str | None = None
    tool_version_id: str | None = None
    finding_type: str
    severity: str
    title: str
    description: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    recommendation: str
    status: str
    created_at: str
    updated_at: str


class MCPFindingActionRequest(BaseModel):
    """Lifecycle action payload for MCP security findings."""

    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def _strip_optional_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class MCPProxyCallRequest(BaseModel):
    """Request to run an MCP tool call through the governed proxy."""

    source_agent_id: str = Field(min_length=1)
    server_id: str = Field(min_length=1)
    tool_id: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None

    @field_validator("source_agent_id", "server_id", "tool_id")
    @classmethod
    def _strip_required_identifier(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("correlation_id")
    @classmethod
    def _strip_optional_correlation_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class MCPToolCallResponse(BaseModel):
    """Persisted MCP proxy traffic record."""

    id: str
    organization_id: str
    environment_id: str
    server_id: str
    server_name: str | None = None
    tool_id: str
    tool_name: str | None = None
    source_agent_id: str
    source_agent_name: str | None = None
    params_summary: dict[str, Any] = Field(default_factory=dict)
    decision: str
    reason: str
    matched_policy_id: str | None = None
    matched_policy_version_id: str | None = None
    policy_binding_id: str | None = None
    policy_action: str | None = None
    policy_reason: str | None = None
    policy_matched_rule: str | None = None
    policy_input: dict[str, Any] | None = None
    trust_threshold_id: str | None = None
    trust_score: int | None = None
    gateway_stage: str | None = None
    upstream_request: dict[str, Any] | None = None
    upstream_response_metadata: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    sanitizer_action: str | None = None
    latency_ms: int
    correlation_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    traceparent: str | None = None
    tracestate: str | None = None
    baggage: str | None = None
    created_at: str


class MCPApprovalDecisionRequest(BaseModel):
    """Approve or deny a pending MCP proxy approval."""

    reason: str | None = None
    idempotency_key: str | None = None

    @field_validator("reason", "idempotency_key")
    @classmethod
    def _strip_optional_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class MCPApprovalResponse(BaseModel):
    """Persisted MCP approval request."""

    id: str
    tool_call_id: str
    status: str
    requested_by_agent_id: str
    requested_by_agent_name: str | None = None
    approved_by_user_id: str | None = None
    decision_reason: str | None = None
    requested_at: str
    decided_at: str | None = None
    expires_at: str | None = None
    payload_hash: str | None = None
    release_status: str | None = None
    released_at: str | None = None
    release_error: str | None = None
    tool_call: MCPToolCallResponse | None = None


class MCPRateLimitCreateRequest(BaseModel):
    """Create an MCP proxy rate limit."""

    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    window_seconds: int = Field(default=60, ge=1)
    max_calls: int = Field(default=60, ge=1)
    enabled: bool = True

    @field_validator("target_type", "target_id")
    @classmethod
    def _strip_required_value(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped


class MCPRateLimitResponse(BaseModel):
    """Persisted MCP proxy rate limit."""

    id: str
    organization_id: str
    environment_id: str
    target_type: str
    target_id: str
    window_seconds: int
    max_calls: int
    enabled: bool
    created_at: str
    updated_at: str


def validate_mcp_endpoint_url(value: str) -> str:
    """Validate and normalize an MCP endpoint URL."""

    stripped = value.strip()
    parsed = urlparse(stripped)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("endpoint_url must be an absolute HTTP or HTTPS URL.")
    return stripped
