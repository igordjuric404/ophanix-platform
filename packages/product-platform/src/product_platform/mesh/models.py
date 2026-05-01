"""Mesh API models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


SUPPORTED_BRIDGE_TYPES = {"a2a", "mcp", "iatp", "acp", "custom"}
SUPPORTED_BRIDGE_STATUSES = {"configured", "active", "disabled", "limited", "error"}
SUPPORTED_ROUTE_PROTOCOLS = {"a2a", "mcp", "iatp", "acp"}


class MeshMessageCreateRequest(BaseModel):
    """Ingest an inter-agent mesh message."""

    source_agent_id: str = Field(min_length=1)
    target_agent_id: str = Field(min_length=1)
    protocol: str = Field(min_length=1)
    action: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    latency_ms: int = Field(default=0, ge=0)
    correlation_id: str | None = None
    payload_summary: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_agent_id", "target_agent_id", "protocol", "action", "decision")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("correlation_id")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class MeshMessageResponse(BaseModel):
    """Persisted inter-agent mesh message."""

    id: str
    organization_id: str
    environment_id: str
    source_agent_id: str
    target_agent_id: str
    protocol: str
    action: str
    decision: str
    latency_ms: int
    correlation_id: str | None = None
    payload_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    source_agent_name: str | None = None
    target_agent_name: str | None = None
    source_trust_tier: str | None = None
    target_trust_tier: str | None = None


class MeshHandoffCreateRequest(BaseModel):
    """Ingest a mesh handoff attempt."""

    source_agent_id: str = Field(min_length=1)
    target_agent_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    required_capabilities: list[str] = Field(default_factory=list)
    trust_result: str = Field(min_length=1)
    policy_result: str = Field(min_length=1)
    status: str = Field(min_length=1)
    reason: str = ""
    correlation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "source_agent_id",
        "target_agent_id",
        "task_type",
        "trust_result",
        "policy_result",
        "status",
    )
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("reason", "correlation_id")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("required_capabilities")
    @classmethod
    def _strip_capabilities(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class MeshHandoffResponse(BaseModel):
    """Persisted mesh handoff attempt."""

    id: str
    organization_id: str
    environment_id: str
    source_agent_id: str
    target_agent_id: str
    task_type: str
    required_capabilities: list[str] = Field(default_factory=list)
    trust_result: str
    policy_result: str
    status: str
    reason: str
    correlation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    source_agent_name: str | None = None
    target_agent_name: str | None = None


class MeshTopologyNode(BaseModel):
    """Agent node in the mesh topology graph."""

    agent_id: str
    name: str | None = None
    status: str | None = None
    trust_tier: str | None = None
    message_count: int = 0


class MeshTopologyEdge(BaseModel):
    """Directed communication edge in the mesh topology graph."""

    source_agent_id: str
    target_agent_id: str
    protocol: str
    volume: int
    denied_count: int
    deny_rate: float
    average_latency_ms: float


class MeshTopologyResponse(BaseModel):
    """Aggregated mesh topology graph."""

    nodes: list[MeshTopologyNode] = Field(default_factory=list)
    edges: list[MeshTopologyEdge] = Field(default_factory=list)
    message_count: int = 0
    generated_at: str
    cached: bool = False


class ProtocolBridgeCreateRequest(BaseModel):
    """Register a configured protocol bridge."""

    name: str = Field(min_length=1)
    bridge_type: str = Field(min_length=1)
    status: str = "configured"
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank.")
        return stripped

    @field_validator("bridge_type")
    @classmethod
    def _validate_bridge_type(cls, value: str) -> str:
        bridge_type = value.strip().lower()
        if bridge_type not in SUPPORTED_BRIDGE_TYPES:
            supported = ", ".join(sorted(SUPPORTED_BRIDGE_TYPES))
            raise ValueError(f"bridge_type must be one of: {supported}.")
        return bridge_type

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        status = value.strip().lower()
        if status not in SUPPORTED_BRIDGE_STATUSES:
            supported = ", ".join(sorted(SUPPORTED_BRIDGE_STATUSES))
            raise ValueError(f"status must be one of: {supported}.")
        return status


class ProtocolBridgePatchRequest(BaseModel):
    """Patch protocol bridge metadata or config."""

    name: str | None = None
    status: str | None = None
    config: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def _strip_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank.")
        return stripped

    @field_validator("status")
    @classmethod
    def _validate_optional_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        status = value.strip().lower()
        if status not in SUPPORTED_BRIDGE_STATUSES:
            supported = ", ".join(sorted(SUPPORTED_BRIDGE_STATUSES))
            raise ValueError(f"status must be one of: {supported}.")
        return status


class ProtocolBridgeRouteCreateRequest(BaseModel):
    """Create a protocol bridge route."""

    source_protocol: str = Field(min_length=1)
    target_protocol: str = Field(min_length=1)
    source_agent_id: str | None = None
    target_agent_id: str | None = None
    policy_binding_id: str | None = None
    enabled: bool = True

    @field_validator("source_protocol", "target_protocol")
    @classmethod
    def _validate_protocol(cls, value: str) -> str:
        protocol = value.strip().lower()
        if protocol not in SUPPORTED_ROUTE_PROTOCOLS:
            supported = ", ".join(sorted(SUPPORTED_ROUTE_PROTOCOLS))
            raise ValueError(f"protocol must be one of: {supported}.")
        return protocol

    @field_validator("source_agent_id", "target_agent_id", "policy_binding_id")
    @classmethod
    def _strip_optional_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ProtocolBridgeRouteResponse(BaseModel):
    """Persisted protocol bridge route."""

    id: str
    bridge_id: str
    source_protocol: str
    target_protocol: str
    source_agent_id: str | None = None
    target_agent_id: str | None = None
    policy_binding_id: str | None = None
    enabled: bool
    created_at: str
    updated_at: str
    source_agent_name: str | None = None
    target_agent_name: str | None = None


class ProtocolBridgeHealthCheckResponse(BaseModel):
    """Persisted protocol bridge health check."""

    id: str
    bridge_id: str
    status: str
    latency_ms: int
    message: str
    checked_at: str


class ProtocolBridgeResponse(BaseModel):
    """Persisted protocol bridge configuration."""

    id: str
    organization_id: str
    environment_id: str
    name: str
    bridge_type: str
    status: str
    config: dict[str, Any] = Field(default_factory=dict)
    current_health: ProtocolBridgeHealthCheckResponse | None = None
    routes: list[ProtocolBridgeRouteResponse] = Field(default_factory=list)
    created_at: str
    updated_at: str
