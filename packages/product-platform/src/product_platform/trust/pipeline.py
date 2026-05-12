"""Map audit events into persistent trust signals."""

from __future__ import annotations

import json
from product_platform.db.postgres import Row

from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.events import trust_change_event
from product_platform.audit.store import AuditEventRepository
from product_platform.trust.repository import TrustRepository

SUPPORTED_AUDIT_EVENT_TYPES = {
    "policy.decision",
    "agent.credential.rotated",
    "agent.credential.expiring_soon",
    "agent.credential.expired",
    "mcp.call",
    "discovery.finding.created",
    "discovery.finding.action",
    "runtime.action",
}


class TrustSignalMapper:
    """Convert supported audit events into trust events."""

    def __init__(self, repository: TrustRepository) -> None:
        self.repository = repository

    def map_pending_audit_events(self, *, limit: int = 100) -> list[Row]:
        """Query supported audit events that do not yet have trust-event links."""

        placeholders = ", ".join("?" for _ in SUPPORTED_AUDIT_EVENT_TYPES)
        values: list[object] = [
            self.repository.organization_id,
            self.repository.environment_id,
            *sorted(SUPPORTED_AUDIT_EVENT_TYPES),
            limit,
        ]
        rows = self.repository.connection.execute(
            f"""
            SELECT a.*
            FROM audit_events a
            WHERE a.organization_id = ?
              AND a.environment_id = ?
              AND a.event_type IN ({placeholders})
              AND NOT EXISTS (
                  SELECT 1
                  FROM trust_events t
                  WHERE t.source_event_id = a.id
                    AND t.organization_id = a.organization_id
                    AND t.environment_id = a.environment_id
              )
            ORDER BY a.created_at ASC, a.id ASC
            LIMIT ?
            """,
            values,
        ).fetchall()
        mapped: list[Row] = []
        for row in rows:
            trust_event = self.map_audit_event(_audit_event_from_row(row))
            if trust_event is not None:
                mapped.append(trust_event)
        return mapped

    def map_audit_event(self, event: AuditEventEnvelope) -> Row | None:
        """Create a trust event for one supported audit event."""

        if not event.agent_id:
            return None
        event_key = trust_rule_event_key(event)
        if event_key is None:
            return None
        rule = self._enabled_rule_for_event_key(event_key)
        if rule is None:
            return None
        current = self.repository.get_score(event.agent_id)
        score_before = int(current["score"]) if current is not None else 500
        delta = max(int(rule["min_delta"]), min(int(rule["max_delta"]), int(rule["delta"])))
        score_after = max(0, min(1000, score_before + delta))
        reason = json.loads(rule["config_json"]).get("reason") or event.payload_json.get("reason")
        if not reason:
            reason = f"Mapped audit event {event.event_type} to trust signal."
        return self.repository.create_trust_event(
            agent_id=event.agent_id,
            source_event_id=event.id,
            dimension=rule["dimension"],
            delta=delta,
            reason=reason,
            score_before=score_before,
            score_after=score_after,
        )

    def _enabled_rule_for_event_key(self, event_key: str) -> Row | None:
        row = self.repository.connection.execute(
            """
            SELECT *
            FROM trust_rules
            WHERE organization_id = ?
              AND event_type = ?
              AND enabled = 1
            """,
            (self.repository.organization_id, event_key),
        ).fetchone()
        return row


class TrustScoreRecalculator:
    """Recalculate deterministic trust scores from stored trust events."""

    def __init__(self, repository: TrustRepository) -> None:
        self.repository = repository

    def recalculate(self, *, agent_id: str | None = None) -> Row:
        """Map pending events, recompute scores, and emit trust-change audit events."""

        self.repository.seed_default_rules()
        run = self.repository.create_recalculation_run(status="running")
        mapped_events = TrustSignalMapper(self.repository).map_pending_audit_events()
        target_agent_ids = self.repository.list_agent_ids(agent_id=agent_id)
        updated_count = 0
        summaries: dict[str, dict[str, object]] = {}
        audit_repository = AuditEventRepository(self.repository.connection)
        for target_agent_id in target_agent_ids:
            previous = self.repository.get_score(target_agent_id)
            previous_score = int(previous["score"]) if previous is not None else 500
            score, dimensions = self._calculate_agent_score(target_agent_id)
            self.repository.upsert_score(
                agent_id=target_agent_id,
                score=score,
                dimensions=dimensions,
            )
            if score != previous_score:
                updated_count += 1
                audit_repository.insert(
                    trust_change_event(
                        organization_id=self.repository.organization_id,
                        environment_id=self.repository.environment_id,
                        agent_id=target_agent_id,
                        trust_delta=score - previous_score,
                        new_score=score,
                    )
                )
            summaries[target_agent_id] = {
                "previous_score": previous_score,
                "score": score,
                "event_count": sum(
                    int(value["signal_count"]) for value in dimensions.values()
                ),
            }
        finished = self.repository.finish_recalculation_run(
            run["id"],
            status="completed",
            summary={
                "agent_count": len(target_agent_ids),
                "updated_count": updated_count,
                "mapped_event_count": len(mapped_events),
                "agents": summaries,
            },
        )
        return finished

    def _calculate_agent_score(self, agent_id: str) -> tuple[int, dict[str, dict[str, int]]]:
        events = self.repository.list_events(agent_id=agent_id, limit=1000)
        events = sorted(events, key=lambda row: (row["created_at"], row["id"]))
        score = 500
        dimensions: dict[str, dict[str, int]] = {}
        for event in events:
            delta = int(event["delta"])
            score = apply_trust_delta(score, delta)
            dimension_name = event["dimension"]
            dimension = dimensions.setdefault(
                dimension_name,
                {"score": 500, "signal_count": 0},
            )
            dimension["score"] = apply_trust_delta(dimension["score"], delta)
            dimension["signal_count"] += 1
        return score, dimensions


def apply_trust_delta(score: int, delta: int) -> int:
    """Apply a trust delta with 0-1000 score bounds."""

    return max(0, min(1000, int(score) + int(delta)))


def trust_rule_event_key(event: AuditEventEnvelope) -> str | None:
    """Normalize real audit envelopes into trust-rule event keys."""

    if event.event_type == "policy.decision":
        if event.decision == "allow":
            return "policy.decision.allow"
        if event.decision == "deny":
            return "policy.decision.deny"
        if event.decision in {"escalate", "escalated", "requires_approval"}:
            return "policy.escalation"
    if event.event_type == "agent.credential.rotated":
        return "credential.rotation"
    if event.event_type in {"agent.credential.expiring_soon", "agent.credential.expired"}:
        return "credential.expiry"
    if event.event_type == "mcp.call" and event.decision in {"deny", "blocked", "block"}:
        return "mcp.call.deny"
    if event.event_type.startswith("discovery.") and (
        event.payload_json.get("finding_type") == "shadow_ai"
        or event.payload_json.get("category") == "shadow_ai"
        or event.payload_json.get("action_type") == "register_agent"
    ):
        return "discovery.shadow_finding"
    if event.event_type == "runtime.action" and (
        event.payload_json.get("action") == "kill_switch"
        or event.payload_json.get("status") == "kill_switch_triggered"
    ):
        return "runtime.kill_switch"
    return None


def _audit_event_from_row(row: Row) -> AuditEventEnvelope:
    return AuditEventEnvelope(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        event_type=row["event_type"],
        source_component=row["source_component"],
        actor_type=row["actor_type"],
        actor_id=row["actor_id"],
        agent_id=row["agent_id"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        decision=row["decision"],
        severity=row["severity"],
        correlation_id=row["correlation_id"],
        trace_id=row["trace_id"],
        policy_id=row["policy_id"],
        policy_version_id=row["policy_version_id"],
        trust_delta=row["trust_delta"],
        payload_json=json.loads(row["payload_json"]),
        created_at=row["created_at"],
    )
