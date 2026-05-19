"""Runtime ring classifier/enforcer adapter."""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from product_platform.runtime.models import RuntimeActionCreateRequest
from product_platform.runtime.repository import (
    RuntimeActionDecisionRecord,
    RuntimeRepository,
    RuntimeSessionNotFoundError,
    RuntimeSessionStateError,
)


@dataclass(frozen=True)
class RuntimeRingEvaluation:
    """Normalized ring enforcement result."""

    required_ring: int
    assigned_ring: int
    decision: str
    reason: str
    agent_trust_score: int


class RuntimeRingAdapter:
    """Small product adapter over hypervisor ring classifier/enforcer."""

    def __init__(self, classifier: Any | None = None, enforcer: Any | None = None) -> None:
        ActionClassifier, RingEnforcer, _ActionDescriptor, _ExecutionRing, _ReversibilityLevel = (
            _load_ring_classes()
        )
        self.classifier = classifier or ActionClassifier()
        self.enforcer = enforcer or RingEnforcer()
        self._action_descriptor = _ActionDescriptor
        self._execution_ring = _ExecutionRing
        self._reversibility_level = _ReversibilityLevel

    def classify_required_ring(self, body: RuntimeActionCreateRequest) -> int:
        """Return the required hypervisor ring for an action."""

        classification = self.classifier.classify(self._build_descriptor(body))
        return int(classification.ring.value)

    def evaluate(
        self,
        body: RuntimeActionCreateRequest,
        *,
        agent_trust_score: int,
        override_required_ring: int | None = None,
        min_trust_score: int | None = None,
    ) -> RuntimeRingEvaluation:
        """Evaluate one runtime action against current public-preview ring rules."""

        descriptor = self._build_descriptor(body)
        classification = self.classifier.classify(descriptor)
        required_ring = int(classification.ring.value)
        check_action = descriptor
        if override_required_ring is not None:
            required_ring = override_required_ring
            check_action = SimpleNamespace(required_ring=self._execution_ring(override_required_ring))
        eff_score = max(0.0, min(1.0, agent_trust_score / 1000))
        assigned_ring = self.enforcer.compute_ring(eff_score, has_consensus=body.has_consensus)
        if min_trust_score is not None and agent_trust_score < min_trust_score:
            return RuntimeRingEvaluation(
                required_ring=required_ring,
                assigned_ring=int(assigned_ring.value),
                decision="denied",
                reason=f"Trust score {agent_trust_score} is below ring rule minimum {min_trust_score}",
                agent_trust_score=max(0, min(1000, int(agent_trust_score))),
            )
        check = self.enforcer.check(
            assigned_ring,
            check_action,
            eff_score,
            has_consensus=body.has_consensus,
            has_sre_witness=body.has_sre_witness,
        )
        return RuntimeRingEvaluation(
            required_ring=required_ring,
            assigned_ring=int(check.agent_ring.value),
            decision="allowed" if check.allowed else "denied",
            reason=check.reason,
            agent_trust_score=max(0, min(1000, int(agent_trust_score))),
        )

    def _build_descriptor(self, body: RuntimeActionCreateRequest) -> Any:
        return self._action_descriptor(
            action_id=_action_id(body.action_name),
            name=body.action_name,
            execute_api=body.execute_api or f"/runtime/actions/{_action_id(body.action_name)}",
            undo_api=body.undo_api,
            reversibility=self._reversibility_level(body.reversibility),
            is_read_only=body.is_read_only,
            is_admin=body.is_admin,
        )


class RuntimeRingDecisionService:
    """Evaluate runtime actions and persist action/decision records."""

    def __init__(
        self,
        repository: RuntimeRepository,
        adapter: RuntimeRingAdapter | None = None,
    ) -> None:
        self.repository = repository
        self.adapter = adapter or RuntimeRingAdapter()

    def evaluate_and_record(
        self,
        session_id: str,
        body: RuntimeActionCreateRequest,
        *,
        correlation_id: str | None,
        trace_id: str | None = None,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        traceparent: str | None = None,
        tracestate: str | None = None,
        baggage: str | None = None,
    ) -> tuple[Any, Any]:
        """Evaluate and persist one runtime action."""

        started = time.perf_counter()
        session = self.repository.get_session(session_id)
        if session is None:
            raise RuntimeSessionNotFoundError("Runtime session not found.")
        if session["state"] != "active":
            raise RuntimeSessionStateError("Runtime session is not active.")
        trust_score = self.repository.trust_score_for_agent(session["agent_id"])
        rule = self.repository.matching_ring_rule(body.action_name)
        evaluation = self.adapter.evaluate(
            body,
            agent_trust_score=trust_score,
            override_required_ring=rule["required_ring"] if rule is not None else None,
            min_trust_score=rule["min_trust_score"] if rule is not None else None,
        )
        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        return self.repository.record_action_decision(
            RuntimeActionDecisionRecord(
                session_id=session["id"],
                action_name=body.action_name,
                resource_type=body.resource_type,
                required_ring=evaluation.required_ring,
                decision=evaluation.decision,
                reason=evaluation.reason,
                latency_ms=latency_ms,
                correlation_id=correlation_id,
                agent_trust_score=evaluation.agent_trust_score,
                assigned_ring=evaluation.assigned_ring,
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                traceparent=traceparent,
                tracestate=tracestate,
                baggage=baggage,
            )
        )


def _action_id(action_name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.:-]+", "_", action_name.strip())
    return normalized.strip("._:-") or "runtime_action"


def _load_ring_classes() -> tuple[Any, Any, Any, Any, Any]:
    try:
        from hypervisor.models import ActionDescriptor, ExecutionRing, ReversibilityLevel
        from hypervisor.rings.classifier import ActionClassifier
        from hypervisor.rings.enforcer import RingEnforcer

        return ActionClassifier, RingEnforcer, ActionDescriptor, ExecutionRing, ReversibilityLevel
    except ModuleNotFoundError:
        hypervisor_src = Path(__file__).resolve().parents[4] / "agent-hypervisor" / "src"
        if str(hypervisor_src) not in sys.path:
            sys.path.insert(0, str(hypervisor_src))
        from hypervisor.models import ActionDescriptor, ExecutionRing, ReversibilityLevel
        from hypervisor.rings.classifier import ActionClassifier
        from hypervisor.rings.enforcer import RingEnforcer

        return ActionClassifier, RingEnforcer, ActionDescriptor, ExecutionRing, ReversibilityLevel
