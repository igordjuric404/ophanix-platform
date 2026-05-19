"""Canonical audit event envelope and helper constructors."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso


class AuditEventEnvelope(BaseModel):
    """Canonical audit event written by all product features."""

    id: str = Field(default_factory=lambda: generate_id("evt"))
    organization_id: str
    environment_id: str
    event_type: str
    source_component: str
    actor_type: str
    actor_id: str | None = None
    agent_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    decision: str | None = None
    severity: str = "info"
    correlation_id: str | None = None
    trace_id: str | None = None
    policy_id: str | None = None
    policy_version_id: str | None = None
    trust_delta: float | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now_iso)

    @model_validator(mode="after")
    def require_tenant_context(self) -> "AuditEventEnvelope":
        if not self.organization_id:
            raise ValueError("organization_id is required.")
        if not self.environment_id:
            raise ValueError("environment_id is required.")
        return self


def policy_decision_event(
    *,
    organization_id: str,
    environment_id: str,
    actor_id: str,
    policy_id: str,
    decision: str,
    matched_rule: str,
    reason: str,
    correlation_id: str | None = None,
) -> AuditEventEnvelope:
    return AuditEventEnvelope(
        organization_id=organization_id,
        environment_id=environment_id,
        event_type="policy.decision",
        source_component="policy-engine",
        actor_type="user",
        actor_id=actor_id,
        resource_type="policy",
        resource_id=policy_id,
        decision=decision,
        policy_id=policy_id,
        severity="warning" if decision == "deny" else "info",
        correlation_id=correlation_id,
        payload_json={"matched_rule": matched_rule, "reason": reason},
    )


def agent_lifecycle_event(
    *,
    organization_id: str,
    environment_id: str,
    agent_id: str,
    lifecycle_state: str,
    actor_id: str,
    previous_state: str | None = None,
    reason: str | None = None,
    decision: str | None = None,
    correlation_id: str | None = None,
) -> AuditEventEnvelope:
    payload = {"lifecycle_state": lifecycle_state}
    if previous_state is not None:
        payload["previous_state"] = previous_state
    if reason is not None:
        payload["reason"] = reason
    return AuditEventEnvelope(
        organization_id=organization_id,
        environment_id=environment_id,
        event_type="agent.lifecycle",
        source_component="agent-registry",
        actor_type="user",
        actor_id=actor_id,
        agent_id=agent_id,
        resource_type="agent",
        resource_id=agent_id,
        decision=decision,
        correlation_id=correlation_id,
        payload_json=payload,
    )


def trust_change_event(
    *,
    organization_id: str,
    environment_id: str,
    agent_id: str,
    trust_delta: float,
    new_score: float,
) -> AuditEventEnvelope:
    return AuditEventEnvelope(
        organization_id=organization_id,
        environment_id=environment_id,
        event_type="trust.change",
        source_component="trust-pipeline",
        actor_type="system",
        agent_id=agent_id,
        resource_type="agent",
        resource_id=agent_id,
        trust_delta=trust_delta,
        payload_json={"new_score": new_score},
    )


def mcp_call_event(
    *,
    organization_id: str,
    environment_id: str,
    agent_id: str,
    server_id: str,
    tool_name: str,
    decision: str,
) -> AuditEventEnvelope:
    return AuditEventEnvelope(
        organization_id=organization_id,
        environment_id=environment_id,
        event_type="mcp.call",
        source_component="mcp-proxy",
        actor_type="agent",
        agent_id=agent_id,
        resource_type="mcp_server",
        resource_id=server_id,
        decision=decision,
        severity="warning" if decision == "deny" else "info",
        payload_json={"tool_name": tool_name},
    )


def runtime_action_event(
    *,
    organization_id: str,
    environment_id: str,
    session_id: str,
    action: str,
    ring: str,
    decision: str,
) -> AuditEventEnvelope:
    return AuditEventEnvelope(
        organization_id=organization_id,
        environment_id=environment_id,
        event_type="runtime.action",
        source_component="runtime-control",
        actor_type="system",
        resource_type="runtime_session",
        resource_id=session_id,
        decision=decision,
        payload_json={"action": action, "ring": ring},
    )


def workflow_run_event(
    *,
    organization_id: str,
    environment_id: str,
    workflow_run_id: str,
    workflow_type: str,
    status: str,
) -> AuditEventEnvelope:
    return AuditEventEnvelope(
        organization_id=organization_id,
        environment_id=environment_id,
        event_type="workflow.run",
        source_component="worker-runtime",
        actor_type="system",
        resource_type="workflow_run",
        resource_id=workflow_run_id,
        payload_json={"workflow_type": workflow_type, "status": status},
    )
