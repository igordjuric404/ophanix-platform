"""Observability API models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


SUPPORTED_CHAOS_FAULT_TYPES = {
    "latency",
    "error",
    "timeout",
    "trust_perturbation",
    "policy_denial",
}


class SloObjectiveCreateRequest(BaseModel):
    """Create an SLO objective for an operational target."""

    name: str = Field(min_length=1)
    target_type: str = Field(default="agent", min_length=1)
    target_id: str = Field(min_length=1)
    sli: str = Field(default="task_success_rate", min_length=1)
    target_value: float = Field(gt=0)
    window: str = Field(default="30d", min_length=1)

    @field_validator("name", "target_type", "target_id", "sli", "window")
    @classmethod
    def _strip_required_string(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped


class SloMeasurementCreateRequest(BaseModel):
    """Ingest an SLO measurement."""

    value: float = Field(ge=0)
    good_events: int | None = Field(default=None, ge=0)
    total_events: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    measured_at: str | None = None

    @field_validator("measured_at")
    @classmethod
    def _strip_measured_at(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class SloMeasurementResponse(BaseModel):
    """Persisted SLO measurement."""

    id: str
    slo_id: str
    value: float
    good_events: int
    total_events: int
    error_budget_remaining: float
    burn_rate: float
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    measured_at: str


class SloObjectiveResponse(BaseModel):
    """Persisted SLO objective with recent measurements."""

    id: str
    organization_id: str
    environment_id: str
    name: str
    target_type: str
    target_id: str
    sli: str
    target_value: float
    window: str
    status: str
    created_by: str
    created_at: str
    updated_at: str
    measurements: list[SloMeasurementResponse] = Field(default_factory=list)


class CostBudgetCreateRequest(BaseModel):
    """Create a cost budget for a target."""

    target_type: str = Field(default="agent", min_length=1)
    target_id: str = Field(min_length=1)
    period: str = Field(default="monthly", min_length=1)
    amount_limit: float = Field(gt=0)
    action_on_breach: str = "warn"

    @field_validator("target_type", "target_id", "period", "action_on_breach")
    @classmethod
    def _strip_budget_string(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("action_on_breach")
    @classmethod
    def _validate_action(cls, value: str) -> str:
        action = value.strip().lower()
        if action not in {"warn", "throttle", "kill_switch"}:
            raise ValueError("action_on_breach must be warn, throttle, or kill_switch.")
        return action


class CostEventCreateRequest(BaseModel):
    """Ingest one model/tool cost event."""

    target_type: str = Field(default="agent", min_length=1)
    target_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    amount: float = Field(ge=0)
    units: float = Field(ge=0)
    correlation_id: str | None = None
    created_at: str | None = None

    @field_validator("target_type", "target_id", "provider", "model")
    @classmethod
    def _strip_event_string(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("correlation_id", "created_at")
    @classmethod
    def _strip_optional_event_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class CostBudgetResponse(BaseModel):
    """Persisted cost budget."""

    id: str
    organization_id: str
    environment_id: str
    target_type: str
    target_id: str
    period: str
    amount_limit: float
    used_amount: float
    action_on_breach: str
    breach_action: str
    status: str
    created_by: str
    created_at: str
    updated_at: str


class CostEventResponse(BaseModel):
    """Persisted cost event."""

    id: str
    organization_id: str
    environment_id: str
    target_type: str
    target_id: str
    provider: str
    model: str
    amount: float
    units: float
    correlation_id: str | None = None
    created_at: str


class CostDashboardResponse(BaseModel):
    """Cost dashboard payload with budgets and recent events."""

    budgets: list[CostBudgetResponse] = Field(default_factory=list)
    events: list[CostEventResponse] = Field(default_factory=list)
    total_amount: float
    by_target: dict[str, float] = Field(default_factory=dict)
    by_provider: dict[str, float] = Field(default_factory=dict)
    by_model: dict[str, float] = Field(default_factory=dict)


class IncidentCreateRequest(BaseModel):
    """Create an incident manually."""

    severity: str = "warning"
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    owner_user_id: str | None = None
    correlation_id: str | None = None
    source_event_id: str | None = None

    @field_validator("severity")
    @classmethod
    def _validate_severity(cls, value: str) -> str:
        severity = value.strip().lower()
        if severity not in {"info", "warning", "critical"}:
            raise ValueError("severity must be info, warning, or critical.")
        return severity

    @field_validator("title", "summary")
    @classmethod
    def _strip_incident_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("owner_user_id", "correlation_id", "source_event_id")
    @classmethod
    def _strip_incident_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class IncidentFromEventRequest(BaseModel):
    """Create an incident from an audit event."""

    source_event_id: str = Field(min_length=1)
    title: str | None = None
    owner_user_id: str | None = None

    @field_validator("source_event_id")
    @classmethod
    def _strip_source_event_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("title", "owner_user_id")
    @classmethod
    def _strip_from_event_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class IncidentResolveRequest(BaseModel):
    """Resolve an incident."""

    resolution_note: str = Field(min_length=1)

    @field_validator("resolution_note")
    @classmethod
    def _strip_resolution_note(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("resolution_note must not be blank.")
        return stripped


class IncidentResponse(BaseModel):
    """Persisted incident with audit correlation hints."""

    id: str
    organization_id: str
    environment_id: str
    severity: str
    status: str
    title: str
    summary: str
    owner_user_id: str | None = None
    correlation_id: str | None = None
    source_event_id: str | None = None
    resolution_note: str | None = None
    started_at: str
    acknowledged_at: str | None = None
    resolved_at: str | None = None
    updated_at: str
    related_event_ids: list[str] = Field(default_factory=list)


class ChaosExperimentCreateRequest(BaseModel):
    """Create a guarded chaos experiment definition."""

    name: str = Field(min_length=1)
    fault_type: str = Field(min_length=1)
    target_type: str = Field(default="agent", min_length=1)
    target_id: str = Field(min_length=1)
    blast_radius: dict[str, Any] = Field(default_factory=dict)
    guardrails: dict[str, Any] = Field(default_factory=dict)
    status: str = "ready"

    @field_validator("name", "fault_type", "target_type", "target_id", "status")
    @classmethod
    def _strip_chaos_string(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("fault_type")
    @classmethod
    def _validate_fault_type(cls, value: str) -> str:
        fault_type = value.strip().lower()
        if fault_type not in SUPPORTED_CHAOS_FAULT_TYPES:
            supported = ", ".join(sorted(SUPPORTED_CHAOS_FAULT_TYPES))
            raise ValueError(f"fault_type must be one of: {supported}.")
        return fault_type

    @field_validator("blast_radius", "guardrails")
    @classmethod
    def _require_non_empty_controls(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("blast_radius and guardrails are required.")
        return value


class ChaosExperimentResponse(BaseModel):
    """Persisted chaos experiment definition."""

    id: str
    organization_id: str
    environment_id: str
    name: str
    fault_type: str
    target_type: str
    target_id: str
    blast_radius: dict[str, Any] = Field(default_factory=dict)
    guardrails: dict[str, Any] = Field(default_factory=dict)
    status: str
    created_by: str
    created_at: str
    updated_at: str


class ChaosRunCreateRequest(BaseModel):
    """Start a guarded demo chaos run."""

    observed_metrics: dict[str, Any] = Field(default_factory=dict)
    acknowledgement: str | None = None

    @field_validator("acknowledgement")
    @classmethod
    def _strip_chaos_acknowledgement(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ChaosRunResponse(BaseModel):
    """Persisted chaos run result."""

    id: str
    experiment_id: str
    status: str
    started_at: str
    finished_at: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)


class RolloutCreateRequest(BaseModel):
    """Create a staged rollout definition."""

    name: str = Field(min_length=1)
    target_type: str = Field(default="agent", min_length=1)
    target_id: str = Field(min_length=1)
    strategy: str = "canary"
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "target_type", "target_id", "strategy")
    @classmethod
    def _strip_rollout_string(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("strategy")
    @classmethod
    def _validate_strategy(cls, value: str) -> str:
        strategy = value.strip().lower()
        if strategy not in {"canary", "percentage"}:
            raise ValueError("strategy must be canary or percentage.")
        return strategy


class RolloutEventResponse(BaseModel):
    """Persisted rollout event."""

    id: str
    rollout_id: str
    stage: int
    decision: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class RolloutAdvanceRequest(BaseModel):
    """Advance a rollout after evaluating guardrail signals."""

    metrics: dict[str, Any] = Field(default_factory=dict)


class RolloutRollbackRequest(BaseModel):
    """Rollback a rollout with an operator reason."""

    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason must not be blank.")
        return stripped


class RolloutResponse(BaseModel):
    """Persisted staged rollout."""

    id: str
    organization_id: str
    environment_id: str
    name: str
    target_type: str
    target_id: str
    strategy: str
    status: str
    current_stage: int
    config: dict[str, Any] = Field(default_factory=dict)
    created_by: str
    created_at: str
    updated_at: str
    events: list[RolloutEventResponse] = Field(default_factory=list)
