"""Runtime session and action persistence."""

from __future__ import annotations

import json
import fnmatch
from dataclasses import dataclass
from product_platform.db.postgres import Connection, Row

from product_platform.agents.lifecycle import is_agent_operational
from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.runtime.models import (
    RuntimeActionResponse,
    RuntimeRingDecisionResponse,
    RuntimeRingRuleCreateRequest,
    RuntimeRingRuleResponse,
    RuntimeSessionCreateRequest,
    RuntimeSessionResponse,
)


class RuntimeSessionNotFoundError(ValueError):
    """Raised when a runtime session is not visible in tenant scope."""


class RuntimeAgentNotActiveError(ValueError):
    """Raised when a runtime session references a missing or inactive agent."""


class RuntimeSessionStateError(ValueError):
    """Raised when a runtime session state transition is invalid."""


class RuntimeRingRuleNotFoundError(ValueError):
    """Raised when a runtime ring rule is not visible in tenant scope."""


@dataclass(frozen=True)
class RuntimeActionDecisionRecord:
    """Runtime action and ring decision fields ready for persistence."""

    session_id: str
    action_name: str
    resource_type: str
    required_ring: int
    decision: str
    reason: str
    latency_ms: int
    correlation_id: str | None
    agent_trust_score: int
    assigned_ring: int


class RuntimeRepository:
    """Tenant-scoped runtime session repository."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create_session(self, body: RuntimeSessionCreateRequest) -> Row:
        """Create an active runtime session for an active agent."""

        agent = self.get_agent(body.agent_id)
        if agent is None:
            raise RuntimeAgentNotActiveError("Runtime sessions require an active agent.")
        if not is_agent_operational(agent["status"]):
            raise RuntimeAgentNotActiveError(
                f"Runtime sessions require an active agent; current status is {agent['status']}."
            )
        if agent["identity_status"] is not None and agent["identity_status"] != "active":
            raise RuntimeAgentNotActiveError(
                f"Runtime sessions require an active identity; current identity status is {agent['identity_status']}."
            )
        session_id = generate_id("rtssn")
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO runtime_sessions (
                id, organization_id, environment_id, agent_id, state, ring,
                sponsor_user_id, started_at, ended_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                self.organization_id,
                self.environment_id,
                body.agent_id,
                "active",
                body.ring,
                body.sponsor_user_id,
                now,
                None,
                json.dumps(body.metadata, sort_keys=True),
            ),
        )
        row = self.get_session(session_id)
        if row is None:
            raise RuntimeSessionNotFoundError("Created runtime session could not be loaded.")
        return row

    def end_session(self, session_id: str, *, reason: str | None = None) -> Row:
        """Archive an active runtime session."""

        existing = self.get_session(session_id)
        if existing is None:
            raise RuntimeSessionNotFoundError("Runtime session not found.")
        if existing["state"] != "active":
            raise RuntimeSessionStateError("Runtime session is not active.")
        metadata = json.loads(existing["metadata_json"])
        if reason:
            metadata["ended_reason"] = reason
        self.connection.execute(
            """
            UPDATE runtime_sessions
            SET state = ?, ended_at = ?, metadata_json = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (
                "archived",
                utc_now_iso(),
                json.dumps(metadata, sort_keys=True),
                session_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        row = self.get_session(session_id)
        if row is None:
            raise RuntimeSessionNotFoundError("Runtime session not found after update.")
        return row

    def get_agent(self, agent_id: str) -> Row | None:
        """Get an agent in tenant scope."""

        return self.connection.execute(
            """
            SELECT a.*, i.identity_status
            FROM agents a
            LEFT JOIN agent_identities i ON i.agent_id = a.id
            WHERE a.id = ?
              AND a.organization_id = ?
              AND a.environment_id = ?
              AND a.deleted_at IS NULL
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()

    def trust_score_for_agent(self, agent_id: str) -> int:
        """Resolve the current product trust score for an agent."""

        score = self.connection.execute(
            """
            SELECT score
            FROM trust_scores
            WHERE agent_id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()
        if score is not None:
            return max(0, min(1000, int(score["score"])))
        agent = self.get_agent(agent_id)
        if agent is not None and agent["trust_score"] is not None:
            return max(0, min(1000, int(agent["trust_score"])))
        return 500

    def get_session(self, session_id: str) -> Row | None:
        """Get one runtime session with agent context."""

        return self.connection.execute(
            """
            SELECT
                s.*,
                a.name AS agent_name
            FROM runtime_sessions s
            JOIN agents a ON a.id = s.agent_id
            WHERE s.id = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
              AND a.deleted_at IS NULL
            """,
            (session_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_sessions(
        self,
        *,
        state: str | None = None,
        agent_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List runtime sessions."""

        clauses = ["s.organization_id = ?", "s.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if state:
            clauses.append("s.state = ?")
            values.append(state)
        if agent_id:
            clauses.append("s.agent_id = ?")
            values.append(agent_id)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT
                s.*,
                a.name AS agent_name
            FROM runtime_sessions s
            JOIN agents a ON a.id = s.agent_id
            WHERE {' AND '.join(clauses)}
              AND a.deleted_at IS NULL
            ORDER BY s.started_at DESC, s.id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def list_actions_for_session(self, session_id: str) -> list[Row]:
        """List runtime actions for one session."""

        return self.connection.execute(
            """
            SELECT a.*
            FROM runtime_actions a
            JOIN runtime_sessions s ON s.id = a.session_id
            WHERE a.session_id = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
            ORDER BY a.created_at DESC, a.id DESC
            """,
            (session_id, self.organization_id, self.environment_id),
        ).fetchall()

    def record_action_decision(self, record: RuntimeActionDecisionRecord) -> tuple[Row, Row]:
        """Persist a runtime action and its ring decision."""

        action_id = generate_id("rtact")
        created_at = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO runtime_actions (
                id, session_id, action_name, resource_type, required_ring,
                decision, reason, latency_ms, correlation_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_id,
                record.session_id,
                record.action_name,
                record.resource_type,
                record.required_ring,
                record.decision,
                record.reason,
                record.latency_ms,
                record.correlation_id,
                created_at,
            ),
        )
        decision_id = generate_id("rtdcsn")
        self.connection.execute(
            """
            INSERT INTO runtime_ring_decisions (
                id, runtime_action_id, agent_trust_score, required_ring,
                assigned_ring, result, reason, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                action_id,
                record.agent_trust_score,
                record.required_ring,
                record.assigned_ring,
                record.decision,
                record.reason,
                created_at,
            ),
        )
        action = self.get_action(action_id)
        decision = self.get_ring_decision(decision_id)
        if action is None or decision is None:
            raise ValueError("Created runtime action decision could not be loaded.")
        return action, decision

    def create_ring_rule(self, body: RuntimeRingRuleCreateRequest) -> Row:
        """Create a runtime ring override rule."""

        rule_id = generate_id("rtrule")
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO runtime_ring_rules (
                id, organization_id, environment_id, action_pattern,
                required_ring, min_trust_score, enabled, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule_id,
                self.organization_id,
                self.environment_id,
                body.action_pattern,
                body.required_ring,
                body.min_trust_score,
                1 if body.enabled else 0,
                now,
                now,
            ),
        )
        row = self.get_ring_rule(rule_id)
        if row is None:
            raise RuntimeRingRuleNotFoundError("Created runtime ring rule could not be loaded.")
        return row

    def get_ring_rule(self, rule_id: str) -> Row | None:
        """Get one runtime ring rule."""

        return self.connection.execute(
            """
            SELECT *
            FROM runtime_ring_rules
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (rule_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_ring_rules(
        self,
        *,
        enabled: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List runtime ring rules."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if enabled is not None:
            clauses.append("enabled = ?")
            values.append(1 if enabled else 0)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT *
            FROM runtime_ring_rules
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def matching_ring_rule(self, action_name: str) -> Row | None:
        """Return the first enabled ring rule matching an action name."""

        for rule in self.list_ring_rules(enabled=True, limit=500):
            if fnmatch.fnmatchcase(action_name, rule["action_pattern"]):
                return rule
        return None

    def get_action(self, action_id: str) -> Row | None:
        """Get one runtime action in tenant scope."""

        return self.connection.execute(
            """
            SELECT a.*
            FROM runtime_actions a
            JOIN runtime_sessions s ON s.id = a.session_id
            WHERE a.id = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
            """,
            (action_id, self.organization_id, self.environment_id),
        ).fetchone()

    def get_ring_decision(self, decision_id: str) -> Row | None:
        """Get one ring decision with action/session context."""

        return self.connection.execute(
            """
            SELECT
                d.*,
                a.session_id,
                a.action_name,
                a.resource_type,
                s.agent_id
            FROM runtime_ring_decisions d
            JOIN runtime_actions a ON a.id = d.runtime_action_id
            JOIN runtime_sessions s ON s.id = a.session_id
            WHERE d.id = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
            """,
            (decision_id, self.organization_id, self.environment_id),
        ).fetchone()

    def get_ring_decision_for_action(self, action_id: str) -> Row | None:
        """Get the ring decision for a runtime action."""

        return self.connection.execute(
            """
            SELECT
                d.*,
                a.session_id,
                a.action_name,
                a.resource_type,
                s.agent_id
            FROM runtime_ring_decisions d
            JOIN runtime_actions a ON a.id = d.runtime_action_id
            JOIN runtime_sessions s ON s.id = a.session_id
            WHERE d.runtime_action_id = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
            """,
            (action_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_ring_decisions(
        self,
        *,
        result: str | None = None,
        session_id: str | None = None,
        agent_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List runtime ring decisions with filters."""

        clauses = ["s.organization_id = ?", "s.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if result:
            clauses.append("d.result = ?")
            values.append(result)
        if session_id:
            clauses.append("a.session_id = ?")
            values.append(session_id)
        if agent_id:
            clauses.append("s.agent_id = ?")
            values.append(agent_id)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT
                d.*,
                a.session_id,
                a.action_name,
                a.resource_type,
                s.agent_id
            FROM runtime_ring_decisions d
            JOIN runtime_actions a ON a.id = d.runtime_action_id
            JOIN runtime_sessions s ON s.id = a.session_id
            WHERE {' AND '.join(clauses)}
            ORDER BY d.created_at DESC, d.id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()


def runtime_ring_decision_response(row: Row) -> RuntimeRingDecisionResponse:
    """Serialize a runtime ring decision row."""

    return RuntimeRingDecisionResponse(
        id=row["id"],
        runtime_action_id=row["runtime_action_id"],
        session_id=row["session_id"],
        agent_id=row["agent_id"],
        action_name=row["action_name"],
        resource_type=row["resource_type"],
        agent_trust_score=row["agent_trust_score"],
        required_ring=row["required_ring"],
        assigned_ring=row["assigned_ring"],
        result=row["result"],
        reason=row["reason"],
        created_at=row["created_at"],
    )


def runtime_ring_rule_response(row: Row) -> RuntimeRingRuleResponse:
    """Serialize a runtime ring rule row."""

    return RuntimeRingRuleResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        action_pattern=row["action_pattern"],
        required_ring=row["required_ring"],
        min_trust_score=row["min_trust_score"],
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def runtime_action_response(
    row: Row,
    *,
    ring_decision: RuntimeRingDecisionResponse | None = None,
) -> RuntimeActionResponse:
    """Serialize a runtime action row."""

    return RuntimeActionResponse(
        id=row["id"],
        session_id=row["session_id"],
        action_name=row["action_name"],
        resource_type=row["resource_type"],
        required_ring=row["required_ring"],
        decision=row["decision"],
        reason=row["reason"],
        latency_ms=row["latency_ms"],
        correlation_id=row["correlation_id"],
        created_at=row["created_at"],
        ring_decision=ring_decision,
    )


def runtime_session_response(
    row: Row,
    *,
    actions: list[RuntimeActionResponse] | None = None,
) -> RuntimeSessionResponse:
    """Serialize a runtime session row."""

    return RuntimeSessionResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        agent_id=row["agent_id"],
        agent_name=row["agent_name"],
        state=row["state"],
        ring=row["ring"],
        sponsor_user_id=row["sponsor_user_id"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        metadata=json.loads(row["metadata_json"]),
        actions=actions or [],
    )
