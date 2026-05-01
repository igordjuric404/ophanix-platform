"""Runtime session and ring-control API models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


SUPPORTED_SESSION_STATES = {"active", "archived"}
SUPPORTED_REVERSIBILITY = {"full", "partial", "none"}
SUPPORTED_SANDBOX_PROVIDER_TYPES = {"subprocess", "noop"}
SUPPORTED_SANDBOX_PROFILE_STATUSES = {"active", "disabled"}
SUPPORTED_KILL_SWITCH_TARGET_TYPES = {"agent", "session", "mcp_server", "tool", "plugin"}
SUBPROCESS_SANDBOX_WARNING = (
    "Subprocess sandbox is demo-only and does not provide production isolation."
)


class RuntimeSessionCreateRequest(BaseModel):
    """Start a product runtime session for an active agent."""

    agent_id: str = Field(min_length=1)
    ring: int = Field(default=2, ge=0, le=3)
    sponsor_user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("agent_id")
    @classmethod
    def _strip_agent_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("agent_id must not be blank.")
        return stripped

    @field_validator("sponsor_user_id")
    @classmethod
    def _strip_optional_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class RuntimeSessionEndRequest(BaseModel):
    """End an active runtime session."""

    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def _strip_optional_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class RuntimeActionCreateRequest(BaseModel):
    """Submit a runtime action for ring enforcement."""

    action_name: str = Field(min_length=1)
    resource_type: str = Field(default="runtime-action", min_length=1)
    execute_api: str | None = None
    undo_api: str | None = None
    reversibility: str = "none"
    is_read_only: bool = False
    is_admin: bool = False
    has_consensus: bool = False
    has_sre_witness: bool = False

    @field_validator("action_name", "resource_type")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("execute_api", "undo_api")
    @classmethod
    def _strip_optional_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("reversibility")
    @classmethod
    def _validate_reversibility(cls, value: str) -> str:
        reversibility = value.strip().lower()
        if reversibility not in SUPPORTED_REVERSIBILITY:
            supported = ", ".join(sorted(SUPPORTED_REVERSIBILITY))
            raise ValueError(f"reversibility must be one of: {supported}.")
        return reversibility


class RuntimeRingDecisionResponse(BaseModel):
    """Persisted runtime ring enforcement decision."""

    id: str
    runtime_action_id: str
    session_id: str
    agent_id: str
    action_name: str
    resource_type: str
    agent_trust_score: int
    required_ring: int
    assigned_ring: int
    result: str
    reason: str
    created_at: str


class RuntimeRingRuleCreateRequest(BaseModel):
    """Create a runtime ring override rule."""

    action_pattern: str = Field(min_length=1)
    required_ring: int = Field(ge=0, le=3)
    min_trust_score: int = Field(default=0, ge=0, le=1000)
    enabled: bool = True

    @field_validator("action_pattern")
    @classmethod
    def _strip_pattern(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("action_pattern must not be blank.")
        return stripped


class RuntimeRingRuleResponse(BaseModel):
    """Persisted runtime ring override rule."""

    id: str
    organization_id: str
    environment_id: str
    action_pattern: str
    required_ring: int
    min_trust_score: int
    enabled: bool
    created_at: str
    updated_at: str


class RuntimeActionResponse(BaseModel):
    """Persisted runtime action within a session."""

    id: str
    session_id: str
    action_name: str
    resource_type: str
    required_ring: int | None = None
    decision: str
    reason: str
    latency_ms: int
    correlation_id: str | None = None
    created_at: str
    ring_decision: RuntimeRingDecisionResponse | None = None


class RuntimeSessionResponse(BaseModel):
    """Persisted runtime session with optional action timeline."""

    id: str
    organization_id: str
    environment_id: str
    agent_id: str
    agent_name: str | None = None
    state: str
    ring: int
    sponsor_user_id: str | None = None
    started_at: str
    ended_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    actions: list[RuntimeActionResponse] = Field(default_factory=list)


class SagaCreateRequest(BaseModel):
    """Create a draft saga definition."""

    name: str = Field(min_length=1)
    runtime_session_id: str | None = None
    correlation_id: str | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank.")
        return stripped

    @field_validator("runtime_session_id", "correlation_id")
    @classmethod
    def _strip_optional_saga_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class SagaStepCreateRequest(BaseModel):
    """Add a step to a draft saga."""

    step_order: int = Field(ge=1)
    name: str = Field(min_length=1)
    action_name: str = Field(min_length=1)
    target_agent_id: str = Field(min_length=1)
    required_capability: str | None = None
    timeout_seconds: int = Field(default=300, ge=1)
    retry_count: int = Field(default=0, ge=0)
    compensation_action: str | None = None

    @field_validator("name", "action_name", "target_agent_id")
    @classmethod
    def _strip_required_step_field(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("required_capability", "compensation_action")
    @classmethod
    def _strip_optional_step_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class SagaStepResponse(BaseModel):
    """Persisted saga step definition and execution state."""

    id: str
    saga_id: str
    step_order: int
    name: str
    action_name: str
    target_agent_id: str
    target_agent_name: str | None = None
    required_capability: str | None = None
    timeout_seconds: int
    retry_count: int
    compensation_action: str | None = None
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class SagaExecuteRequest(BaseModel):
    """Execute a configured saga using demo-safe fixtures."""

    runtime_session_id: str | None = None
    failure_actions: list[str] = Field(default_factory=list)

    @field_validator("runtime_session_id")
    @classmethod
    def _strip_runtime_session_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("failure_actions")
    @classmethod
    def _strip_failure_actions(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class SagaCancelRequest(BaseModel):
    """Cancel a non-terminal saga."""

    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class SagaEventResponse(BaseModel):
    """Persisted saga lifecycle event."""

    id: str
    saga_id: str
    step_id: str | None = None
    event_type: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class SagaResponse(BaseModel):
    """Persisted saga definition with optional step/event detail."""

    id: str
    organization_id: str
    environment_id: str
    runtime_session_id: str | None = None
    name: str
    status: str
    created_by: str
    started_at: str | None = None
    finished_at: str | None = None
    correlation_id: str | None = None
    created_at: str
    updated_at: str
    steps: list[SagaStepResponse] = Field(default_factory=list)
    events: list[SagaEventResponse] = Field(default_factory=list)


class SagaExecutionResponse(BaseModel):
    """API response for one saga execution attempt."""

    saga_id: str
    runtime_session_id: str | None = None
    status: str
    message: str
    executed_step_ids: list[str] = Field(default_factory=list)
    compensated_step_ids: list[str] = Field(default_factory=list)
    failed_step_id: str | None = None
    saga: SagaResponse


class SandboxProfileCreateRequest(BaseModel):
    """Create a runtime sandbox profile."""

    name: str = Field(min_length=1)
    provider_type: str = Field(default="subprocess", min_length=1)
    allowed_imports: list[str] = Field(default_factory=list)
    blocked_imports: list[str] = Field(default_factory=list)
    allowed_paths: list[str] = Field(default_factory=list)
    network_policy: dict[str, Any] = Field(default_factory=dict)
    resource_limits: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"

    @field_validator("name", "provider_type", "status")
    @classmethod
    def _strip_required_sandbox_field(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("allowed_imports", "blocked_imports", "allowed_paths")
    @classmethod
    def _strip_sandbox_lists(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class SandboxProfilePatchRequest(BaseModel):
    """Patch a runtime sandbox profile."""

    name: str | None = None
    provider_type: str | None = None
    allowed_imports: list[str] | None = None
    blocked_imports: list[str] | None = None
    allowed_paths: list[str] | None = None
    network_policy: dict[str, Any] | None = None
    resource_limits: dict[str, Any] | None = None
    status: str | None = None

    @field_validator("name", "provider_type", "status")
    @classmethod
    def _strip_optional_sandbox_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("allowed_imports", "blocked_imports", "allowed_paths")
    @classmethod
    def _strip_optional_sandbox_lists(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [item.strip() for item in value if item.strip()]


class SandboxProfileResponse(BaseModel):
    """Persisted runtime sandbox profile."""

    id: str
    organization_id: str
    environment_id: str
    name: str
    provider_type: str
    allowed_imports: list[str] = Field(default_factory=list)
    blocked_imports: list[str] = Field(default_factory=list)
    allowed_paths: list[str] = Field(default_factory=list)
    network_policy: dict[str, Any] = Field(default_factory=dict)
    resource_limits: dict[str, Any] = Field(default_factory=dict)
    status: str
    provider_warning: str | None = None
    created_at: str
    updated_at: str


class SandboxProfileTestRequest(BaseModel):
    """Test sample code/action descriptor against a sandbox profile."""

    code: str = Field(min_length=1)
    agent_id: str | None = None
    action_name: str | None = None

    @field_validator("code")
    @classmethod
    def _strip_code(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("code must not be blank.")
        return stripped

    @field_validator("agent_id", "action_name")
    @classmethod
    def _strip_optional_test_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class SandboxViolationResponse(BaseModel):
    """Static sandbox validation violation."""

    line: int
    column: int
    violation_type: str
    description: str
    severity: str


class SandboxDecisionResponse(BaseModel):
    """Sandbox test decision."""

    id: str | None = None
    profile_id: str
    agent_id: str | None = None
    action_name: str | None = None
    decision: str
    reason: str
    violations: list[SandboxViolationResponse] = Field(default_factory=list)
    provider_warning: str | None = None
    created_at: str | None = None


class KillSwitchRequest(BaseModel):
    """Trigger an emergency kill switch event."""

    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    scope: str = Field(default="target", min_length=1)
    reason: str = Field(min_length=1)
    confirmation: str = Field(min_length=1)

    @field_validator("target_type", "target_id", "scope", "reason", "confirmation")
    @classmethod
    def _strip_kill_switch_field(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped


class KillSwitchEventResponse(BaseModel):
    """Persisted kill-switch event."""

    id: str
    organization_id: str
    environment_id: str
    target_type: str
    target_id: str
    scope: str
    reason: str
    actor_id: str
    status: str
    created_at: str
