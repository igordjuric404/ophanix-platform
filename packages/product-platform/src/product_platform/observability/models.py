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
SUPPORTED_TRACE_STATUSES = {"ok", "error", "running", "unknown"}
SUPPORTED_SPAN_KINDS = {"agent", "chain", "model", "tool", "retriever", "runtime", "policy", "eval", "artifact", "other"}


def _strip_non_blank(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank.")
    return stripped


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _validate_trace_id_value(value: str) -> str:
    trace_id = _strip_non_blank(value, "trace_id").lower()
    if len(trace_id) != 32 or not all(char in "0123456789abcdef" for char in trace_id):
        raise ValueError("trace_id must be a 32-character lowercase hexadecimal W3C trace id.")
    if trace_id == "0" * 32:
        raise ValueError("trace_id must not be all zeroes.")
    return trace_id


def _validate_span_id_value(value: str | None) -> str | None:
    if value is None:
        return None
    span_id = _strip_non_blank(value, "span_id").lower()
    if len(span_id) != 16 or not all(char in "0123456789abcdef" for char in span_id):
        raise ValueError("span_id must be a 16-character lowercase hexadecimal W3C span id.")
    if span_id == "0" * 16:
        raise ValueError("span_id must not be all zeroes.")
    return span_id


class ObservabilityTraceCreateRequest(BaseModel):
    """Create or update a product trace record."""

    trace_id: str = Field(min_length=32, max_length=32)
    name: str = Field(default="Agent trace", min_length=1)
    status: str = "unknown"
    agent_id: str | None = None
    runtime_session_id: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: str | None = None
    ended_at: str | None = None

    @field_validator("trace_id")
    @classmethod
    def _validate_trace_id(cls, value: str) -> str:
        return _validate_trace_id_value(value)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return _strip_non_blank(value, "name")

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        status = _strip_non_blank(value, "status").lower()
        if status not in SUPPORTED_TRACE_STATUSES:
            supported = ", ".join(sorted(SUPPORTED_TRACE_STATUSES))
            raise ValueError(f"status must be one of: {supported}.")
        return status

    @field_validator("agent_id", "runtime_session_id", "correlation_id", "started_at", "ended_at")
    @classmethod
    def _strip_optional_fields(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class ObservabilitySpanCreateRequest(BaseModel):
    """Create or update a span within a product trace."""

    span_id: str = Field(min_length=16, max_length=16)
    parent_span_id: str | None = None
    span_kind: str = "other"
    name: str = Field(min_length=1)
    status: str = "unknown"
    start_time: str | None = None
    end_time: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    resource_type: str | None = None
    resource_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("span_id", "parent_span_id")
    @classmethod
    def _validate_span_ids(cls, value: str | None) -> str | None:
        return _validate_span_id_value(value)

    @field_validator("span_kind")
    @classmethod
    def _validate_span_kind(cls, value: str) -> str:
        span_kind = _strip_non_blank(value, "span_kind").lower()
        if span_kind not in SUPPORTED_SPAN_KINDS:
            supported = ", ".join(sorted(SUPPORTED_SPAN_KINDS))
            raise ValueError(f"span_kind must be one of: {supported}.")
        return span_kind

    @field_validator("name", "status")
    @classmethod
    def _strip_required_strings(cls, value: str) -> str:
        return _strip_non_blank(value, "field")

    @field_validator("start_time", "end_time", "resource_type", "resource_id")
    @classmethod
    def _strip_optional_strings(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class ObservabilityEvalResultCreateRequest(BaseModel):
    """Create an eval result linked to a trace, span, and dataset."""

    trace_id: str = Field(min_length=32, max_length=32)
    span_id: str | None = None
    dataset_id: str | None = None
    dataset_name: str | None = None
    evaluator_name: str = Field(min_length=1)
    score: float | None = None
    label: str | None = None
    passed: bool | None = None
    feedback: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("trace_id")
    @classmethod
    def _validate_trace_id(cls, value: str) -> str:
        return _validate_trace_id_value(value)

    @field_validator("span_id")
    @classmethod
    def _validate_span_id(cls, value: str | None) -> str | None:
        return _validate_span_id_value(value)

    @field_validator("dataset_id", "dataset_name", "label")
    @classmethod
    def _strip_optional_eval_strings(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("evaluator_name")
    @classmethod
    def _strip_evaluator_name(cls, value: str) -> str:
        return _strip_non_blank(value, "evaluator_name")


class ObservabilityTraceAnnotationCreateRequest(BaseModel):
    """Attach an operator or evaluator annotation to a trace."""

    span_id: str | None = None
    annotation_type: str = Field(default="note", min_length=1)
    body: dict[str, Any] = Field(default_factory=dict)

    @field_validator("span_id")
    @classmethod
    def _validate_span_id(cls, value: str | None) -> str | None:
        return _validate_span_id_value(value)

    @field_validator("annotation_type")
    @classmethod
    def _strip_annotation_type(cls, value: str) -> str:
        return _strip_non_blank(value, "annotation_type")


class ObservabilityTraceFeedbackCreateRequest(BaseModel):
    """Attach feedback to a trace or span."""

    span_id: str | None = None
    rating: str = Field(min_length=1)
    body: dict[str, Any] = Field(default_factory=dict)

    @field_validator("span_id")
    @classmethod
    def _validate_span_id(cls, value: str | None) -> str | None:
        return _validate_span_id_value(value)

    @field_validator("rating")
    @classmethod
    def _strip_rating(cls, value: str) -> str:
        return _strip_non_blank(value, "rating").lower()


class ObservabilityTraceResponse(BaseModel):
    """Persisted product trace record."""

    id: str
    organization_id: str
    environment_id: str
    trace_id: str
    name: str
    status: str
    agent_id: str | None = None
    runtime_session_id: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: str
    ended_at: str | None = None
    created_by: str | None = None
    created_at: str
    updated_at: str


class ObservabilitySpanResponse(BaseModel):
    """Persisted product trace span."""

    id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    span_kind: str
    name: str
    status: str
    start_time: str
    end_time: str | None = None
    latency_ms: int | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ObservabilityEvalResultResponse(BaseModel):
    """Persisted eval result linked to a trace."""

    id: str
    organization_id: str
    environment_id: str
    trace_id: str
    span_id: str | None = None
    dataset_id: str | None = None
    dataset_name: str | None = None
    evaluator_name: str
    score: float | None = None
    label: str | None = None
    passed: bool | None = None
    feedback: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: str


class ObservabilityTraceAnnotationResponse(BaseModel):
    """Persisted annotation for a trace or span."""

    id: str
    trace_id: str
    span_id: str | None = None
    annotation_type: str
    body: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: str


class ObservabilityTraceFeedbackResponse(BaseModel):
    """Persisted feedback for a trace or span."""

    id: str
    trace_id: str
    span_id: str | None = None
    rating: str
    body: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: str


class ObservabilityTraceDetailResponse(BaseModel):
    """Trace detail with first-class spans and linked runtime evidence."""

    trace: ObservabilityTraceResponse
    spans: list[ObservabilitySpanResponse] = Field(default_factory=list)
    runtime_sessions: list[dict[str, Any]] = Field(default_factory=list)
    runs: list[dict[str, Any]] = Field(default_factory=list)
    runtime_actions: list[dict[str, Any]] = Field(default_factory=list)
    tool_runtime_actions: list[dict[str, Any]] = Field(default_factory=list)
    mcp_tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    policy_evaluations: list[dict[str, Any]] = Field(default_factory=list)
    eval_results: list[ObservabilityEvalResultResponse] = Field(default_factory=list)
    annotations: list[ObservabilityTraceAnnotationResponse] = Field(default_factory=list)
    feedback: list[ObservabilityTraceFeedbackResponse] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    model_calls: list[dict[str, Any]] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)


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
    source: str = Field(default="manual", min_length=1)
    source_resource_type: str | None = None
    source_resource_id: str | None = None
    trace_id: str | None = None

    @field_validator("measured_at")
    @classmethod
    def _strip_measured_at(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("source")
    @classmethod
    def _strip_source(cls, value: str) -> str:
        return _strip_non_blank(value, "source").lower()

    @field_validator("source_resource_type", "source_resource_id")
    @classmethod
    def _strip_source_resource(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("trace_id")
    @classmethod
    def _validate_optional_trace_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_trace_id_value(value)


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
    source: str
    source_resource_type: str | None = None
    source_resource_id: str | None = None
    trace_id: str | None = None


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
    source: str = Field(default="manual", min_length=1)
    source_resource_type: str | None = None
    source_resource_id: str | None = None
    trace_id: str | None = None

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

    @field_validator("source")
    @classmethod
    def _strip_cost_source(cls, value: str) -> str:
        return _strip_non_blank(value, "source").lower()

    @field_validator("source_resource_type", "source_resource_id")
    @classmethod
    def _strip_cost_source_resource(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("trace_id")
    @classmethod
    def _validate_cost_trace_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_trace_id_value(value)


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
    source: str
    source_resource_type: str | None = None
    source_resource_id: str | None = None
    trace_id: str | None = None
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
    source: str = Field(default="manual", min_length=1)
    source_resource_type: str | None = None
    source_resource_id: str | None = None
    trace_id: str | None = None

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

    @field_validator("owner_user_id", "correlation_id", "source_event_id", "source_resource_type", "source_resource_id")
    @classmethod
    def _strip_incident_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("source")
    @classmethod
    def _strip_incident_source(cls, value: str) -> str:
        return _strip_non_blank(value, "source").lower()

    @field_validator("trace_id")
    @classmethod
    def _validate_incident_trace_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_trace_id_value(value)


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
    source: str
    source_resource_type: str | None = None
    source_resource_id: str | None = None
    trace_id: str | None = None
    resolution_note: str | None = None
    started_at: str
    acknowledged_at: str | None = None
    resolved_at: str | None = None
    updated_at: str
    related_event_ids: list[str] = Field(default_factory=list)


class TelemetryDerivationRequest(BaseModel):
    """Derive SLO, cost, and incident signals from runtime telemetry."""

    target_type: str | None = None
    target_id: str | None = None
    created_from: str | None = None
    created_to: str | None = None
    limit: int = Field(default=200, ge=1, le=1000)
    create_incidents: bool = True

    @field_validator("target_type", "target_id", "created_from", "created_to")
    @classmethod
    def _strip_optional_telemetry_string(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class TelemetryDerivationResponse(BaseModel):
    """Result of one runtime telemetry derivation pass."""

    slo_measurements: list[SloMeasurementResponse] = Field(default_factory=list)
    cost_events: list[CostEventResponse] = Field(default_factory=list)
    incidents: list[IncidentResponse] = Field(default_factory=list)
    examined_tool_runtime_actions: int
    examined_runtime_actions: int
    skipped_duplicate_cost_events: int = 0


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
