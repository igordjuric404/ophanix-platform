"""Trust score persistence and default rule management."""

from __future__ import annotations

import json
from dataclasses import dataclass
from sqlite3 import Connection, IntegrityError, Row
from typing import Any

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.trust.models import (
    TrustEventResponse,
    TrustRecalculationRunResponse,
    TrustThresholdCreateRequest,
    TrustThresholdPatchRequest,
    TrustThresholdResolveRequest,
    TrustThresholdResponse,
    TrustHandshakeResponse,
    TrustRulePatchRequest,
    TrustRuleResponse,
    TrustScoreResponse,
)


class TrustAgentNotFoundError(ValueError):
    """Raised when a trust operation targets an agent outside the tenant scope."""


class TrustRuleNotFoundError(ValueError):
    """Raised when a trust rule is not visible in the tenant scope."""


class TrustThresholdNotFoundError(ValueError):
    """Raised when a trust threshold is not visible in the tenant scope."""


class DuplicateTrustThresholdError(ValueError):
    """Raised when a trust threshold already exists for a target."""


@dataclass(frozen=True)
class DefaultTrustRule:
    """Default audit-to-trust mapping."""

    event_type: str
    dimension: str
    delta: int
    min_delta: int
    max_delta: int
    reason: str


DEFAULT_TRUST_RULES = [
    DefaultTrustRule("policy.decision.allow", "policy_compliance", 8, 0, 25, "Policy decision allowed."),
    DefaultTrustRule("policy.decision.deny", "policy_compliance", -35, -100, 0, "Policy decision denied."),
    DefaultTrustRule("policy.escalation", "policy_compliance", -12, -50, 0, "Policy escalation required."),
    DefaultTrustRule("credential.rotation", "security_posture", 18, 0, 50, "Credential rotated on schedule."),
    DefaultTrustRule("credential.expiry", "security_posture", -45, -100, 0, "Credential expired."),
    DefaultTrustRule("mcp.call.deny", "security_posture", -30, -100, 0, "MCP call blocked."),
    DefaultTrustRule("discovery.shadow_finding", "security_posture", -40, -100, 0, "Shadow AI discovery finding."),
    DefaultTrustRule("runtime.kill_switch", "security_posture", -100, -250, 0, "Runtime kill switch triggered."),
]


DEFAULT_THRESHOLD_TARGET_ID = ""


@dataclass(frozen=True)
class DefaultTrustThreshold:
    """Default threshold for protected trust handshakes."""

    threshold_type: str
    target_type: str
    min_score: int
    required_tier: str
    target_id: str = DEFAULT_THRESHOLD_TARGET_ID


DEFAULT_TRUST_THRESHOLDS = [
    DefaultTrustThreshold("handoff", "environment", 700, "trusted"),
    DefaultTrustThreshold("mcp_tool_use", "environment", 650, "standard"),
    DefaultTrustThreshold("privileged_runtime_action", "environment", 850, "trusted"),
    DefaultTrustThreshold("marketplace_install", "environment", 600, "standard"),
]


def calculate_trust_tier(score: int | float) -> str:
    """Map a 0-1000 trust score to the AgentMesh tier names."""

    normalized = max(0, min(1000, int(score)))
    if normalized >= 900:
        return "verified_partner"
    if normalized >= 700:
        return "trusted"
    if normalized >= 500:
        return "standard"
    if normalized >= 300:
        return "probationary"
    return "untrusted"


class TrustRepository:
    """Environment-scoped trust score repository."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def seed_default_rules(self) -> list[Row]:
        """Seed organization-level trust rules idempotently."""

        now = utc_now_iso()
        for rule in DEFAULT_TRUST_RULES:
            self.connection.execute(
                """
                INSERT INTO trust_rules (
                    id, organization_id, event_type, dimension, delta, min_delta,
                    max_delta, enabled, config_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (organization_id, event_type) DO NOTHING
                """,
                (
                    generate_id("trule"),
                    self.organization_id,
                    rule.event_type,
                    rule.dimension,
                    rule.delta,
                    rule.min_delta,
                    rule.max_delta,
                    1,
                    json.dumps({"reason": rule.reason}, sort_keys=True),
                    now,
                    now,
                ),
            )
        return self.list_rules()

    def seed_default_thresholds(self) -> list[Row]:
        """Seed environment-scoped protected-action thresholds idempotently."""

        now = utc_now_iso()
        for threshold in DEFAULT_TRUST_THRESHOLDS:
            self.connection.execute(
                """
                INSERT INTO trust_thresholds (
                    id, organization_id, environment_id, threshold_type,
                    target_type, target_id, min_score, required_tier,
                    enabled, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (
                    organization_id, environment_id, threshold_type, target_type, target_id
                ) DO NOTHING
                """,
                (
                    generate_id("tthr"),
                    self.organization_id,
                    self.environment_id,
                    threshold.threshold_type,
                    threshold.target_type,
                    threshold.target_id,
                    threshold.min_score,
                    threshold.required_tier,
                    1,
                    now,
                    now,
                ),
            )
        return self.list_thresholds()

    def list_thresholds(
        self,
        *,
        threshold_type: str | None = None,
        enabled: bool | None = None,
    ) -> list[Row]:
        """List trust thresholds for the current environment."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if threshold_type:
            clauses.append("threshold_type = ?")
            values.append(threshold_type)
        if enabled is not None:
            clauses.append("enabled = ?")
            values.append(1 if enabled else 0)
        return self.connection.execute(
            f"""
            SELECT *
            FROM trust_thresholds
            WHERE {' AND '.join(clauses)}
            ORDER BY threshold_type ASC, target_type ASC, target_id ASC
            """,
            values,
        ).fetchall()

    def get_threshold(self, threshold_id: str) -> Row | None:
        """Get one threshold by id."""

        return self.connection.execute(
            """
            SELECT *
            FROM trust_thresholds
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (threshold_id, self.organization_id, self.environment_id),
        ).fetchone()

    def find_enabled_threshold(self, body: TrustThresholdResolveRequest) -> Row | None:
        """Find an enabled threshold for an exact target."""

        return self.connection.execute(
            """
            SELECT *
            FROM trust_thresholds
            WHERE organization_id = ?
              AND environment_id = ?
              AND threshold_type = ?
              AND target_type = ?
              AND target_id = ?
              AND enabled = 1
            """,
            (
                self.organization_id,
                self.environment_id,
                body.threshold_type,
                body.target_type,
                _stored_threshold_target_id(body.target_id),
            ),
        ).fetchone()

    def create_threshold(self, body: TrustThresholdCreateRequest) -> Row:
        """Create a trust threshold."""

        threshold_id = generate_id("tthr")
        now = utc_now_iso()
        try:
            self.connection.execute(
                """
                INSERT INTO trust_thresholds (
                    id, organization_id, environment_id, threshold_type,
                    target_type, target_id, min_score, required_tier,
                    enabled, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    threshold_id,
                    self.organization_id,
                    self.environment_id,
                    body.threshold_type,
                    body.target_type,
                    _stored_threshold_target_id(body.target_id),
                    body.min_score,
                    body.required_tier,
                    1 if body.enabled else 0,
                    now,
                    now,
                ),
            )
        except IntegrityError as exc:
            raise DuplicateTrustThresholdError("Trust threshold already exists for this target.") from exc
        row = self.get_threshold(threshold_id)
        if row is None:
            raise TrustThresholdNotFoundError("Created trust threshold could not be loaded.")
        return row

    def update_threshold(self, threshold_id: str, body: TrustThresholdPatchRequest) -> Row:
        """Patch a trust threshold."""

        existing = self.get_threshold(threshold_id)
        if existing is None:
            raise TrustThresholdNotFoundError("Trust threshold not found.")
        values = body.model_dump(exclude_unset=True)
        if not values:
            return existing
        assignments: list[str] = []
        sql_values: list[object] = []
        for field, value in values.items():
            if field == "target_id":
                assignments.append("target_id = ?")
                sql_values.append(_stored_threshold_target_id(value))
            elif field == "enabled":
                assignments.append("enabled = ?")
                sql_values.append(1 if value else 0)
            else:
                assignments.append(f"{field} = ?")
                sql_values.append(value)
        sql_values.extend([utc_now_iso(), threshold_id, self.organization_id, self.environment_id])
        try:
            self.connection.execute(
                f"""
                UPDATE trust_thresholds
                SET {', '.join(assignments)}, updated_at = ?
                WHERE id = ? AND organization_id = ? AND environment_id = ?
                """,
                sql_values,
            )
        except IntegrityError as exc:
            raise DuplicateTrustThresholdError("Trust threshold already exists for this target.") from exc
        row = self.get_threshold(threshold_id)
        if row is None:
            raise TrustThresholdNotFoundError("Trust threshold not found.")
        return row

    def create_handshake_event(
        self,
        *,
        source_agent_id: str,
        target_agent_id: str,
        purpose: str,
        threshold_type: str,
        target_type: str,
        target_id: str | None,
        required_score: int,
        required_tier: str,
        source_score: int,
        target_score: int,
        result: str,
        reason: str,
        correlation_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> Row:
        """Persist a trust handshake outcome."""

        self._require_agent(source_agent_id)
        self._require_agent(target_agent_id)
        handshake_id = generate_id("hshake")
        self.connection.execute(
            """
            INSERT INTO handshake_events (
                id, organization_id, environment_id, source_agent_id, target_agent_id,
                purpose, threshold_type, target_type, target_id, required_score,
                required_tier, source_score, target_score, result, reason,
                correlation_id, metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                handshake_id,
                self.organization_id,
                self.environment_id,
                source_agent_id,
                target_agent_id,
                purpose,
                threshold_type,
                target_type,
                _stored_threshold_target_id(target_id),
                max(0, min(1000, int(required_score))),
                required_tier,
                max(0, min(1000, int(source_score))),
                max(0, min(1000, int(target_score))),
                result,
                reason,
                correlation_id,
                json.dumps(metadata or {}, sort_keys=True),
                utc_now_iso(),
            ),
        )
        row = self.connection.execute(
            """
            SELECT *
            FROM handshake_events
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (handshake_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise ValueError("Created handshake event could not be loaded.")
        return row

    def list_handshake_events(
        self,
        *,
        source_agent_id: str | None = None,
        target_agent_id: str | None = None,
        result: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List trust handshake outcomes."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        for column, value in [
            ("source_agent_id", source_agent_id),
            ("target_agent_id", target_agent_id),
            ("result", result),
        ]:
            if value:
                clauses.append(f"{column} = ?")
                values.append(value)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT *
            FROM handshake_events
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def upsert_score(
        self,
        *,
        agent_id: str,
        score: int,
        dimensions: dict[str, Any] | None = None,
        calculated_at: str | None = None,
    ) -> Row:
        """Create or replace the current score for an agent."""

        self._require_agent(agent_id)
        bounded_score = max(0, min(1000, int(score)))
        tier = calculate_trust_tier(bounded_score)
        now = utc_now_iso()
        score_id = generate_id("tscore")
        dimensions_json = json.dumps(dimensions or {}, sort_keys=True)
        calculated = calculated_at or now
        self.connection.execute(
            """
            INSERT INTO trust_scores (
                id, organization_id, environment_id, agent_id, score, tier,
                dimensions_json, calculated_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (organization_id, environment_id, agent_id) DO UPDATE SET
                score = excluded.score,
                tier = excluded.tier,
                dimensions_json = excluded.dimensions_json,
                calculated_at = excluded.calculated_at,
                updated_at = excluded.updated_at
            """,
            (
                score_id,
                self.organization_id,
                self.environment_id,
                agent_id,
                bounded_score,
                tier,
                dimensions_json,
                calculated,
                now,
                now,
            ),
        )
        self.connection.execute(
            """
            UPDATE agents
            SET trust_score = ?, trust_tier = ?, updated_at = ?
            WHERE id = ? AND organization_id = ? AND environment_id = ? AND deleted_at IS NULL
            """,
            (
                bounded_score,
                tier,
                now,
                agent_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        row = self.get_score(agent_id)
        if row is None:
            raise TrustAgentNotFoundError("Created trust score could not be loaded.")
        return row

    def get_score(self, agent_id: str) -> Row | None:
        """Get the current score for one agent."""

        return self.connection.execute(
            """
            SELECT s.*, a.name AS agent_name
            FROM trust_scores s
            JOIN agents a ON a.id = s.agent_id
            WHERE s.agent_id = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
              AND a.deleted_at IS NULL
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_scores(self) -> list[Row]:
        """List current trust scores from highest to lowest."""

        return self.connection.execute(
            """
            SELECT s.*, a.name AS agent_name
            FROM trust_scores s
            JOIN agents a ON a.id = s.agent_id
            WHERE s.organization_id = ?
              AND s.environment_id = ?
              AND a.deleted_at IS NULL
            ORDER BY s.score DESC, a.name ASC, s.agent_id ASC
            """,
            (self.organization_id, self.environment_id),
        ).fetchall()

    def create_trust_event(
        self,
        *,
        agent_id: str,
        source_event_id: str | None,
        dimension: str,
        delta: int,
        reason: str,
        score_before: int,
        score_after: int,
    ) -> Row:
        """Persist an explainable trust delta."""

        self._require_agent(agent_id)
        if source_event_id is not None:
            existing = self._get_event_by_source(
                agent_id=agent_id,
                source_event_id=source_event_id,
                dimension=dimension,
            )
            if existing is not None:
                return existing
        event_id = generate_id("tevt")
        now = utc_now_iso()
        try:
            self.connection.execute(
                """
                INSERT INTO trust_events (
                    id, organization_id, environment_id, agent_id, source_event_id,
                    dimension, delta, reason, score_before, score_after, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    self.organization_id,
                    self.environment_id,
                    agent_id,
                    source_event_id,
                    dimension,
                    int(delta),
                    reason,
                    max(0, min(1000, int(score_before))),
                    max(0, min(1000, int(score_after))),
                    now,
                ),
            )
        except IntegrityError:
            if source_event_id is None:
                raise
            existing = self._get_event_by_source(
                agent_id=agent_id,
                source_event_id=source_event_id,
                dimension=dimension,
            )
            if existing is None:
                raise
            return existing
        row = self.connection.execute(
            """
            SELECT e.*, a.name AS agent_name
            FROM trust_events e
            JOIN agents a ON a.id = e.agent_id
            WHERE e.id = ? AND e.organization_id = ? AND e.environment_id = ?
            """,
            (event_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise TrustAgentNotFoundError("Created trust event could not be loaded.")
        return row

    def _get_event_by_source(
        self,
        *,
        agent_id: str,
        source_event_id: str,
        dimension: str,
    ) -> Row | None:
        return self.connection.execute(
            """
            SELECT e.*, a.name AS agent_name
            FROM trust_events e
            JOIN agents a ON a.id = e.agent_id
            WHERE e.organization_id = ?
              AND e.environment_id = ?
              AND e.agent_id = ?
              AND e.source_event_id = ?
              AND e.dimension = ?
            """,
            (
                self.organization_id,
                self.environment_id,
                agent_id,
                source_event_id,
                dimension,
            ),
        ).fetchone()

    def list_events(
        self,
        *,
        agent_id: str | None = None,
        dimension: str | None = None,
        source_event_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List trust events with simple filters."""

        clauses = ["e.organization_id = ?", "e.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        for column, value in [
            ("e.agent_id", agent_id),
            ("e.dimension", dimension),
            ("e.source_event_id", source_event_id),
        ]:
            if value:
                clauses.append(f"{column} = ?")
                values.append(value)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT e.*, a.name AS agent_name
            FROM trust_events e
            JOIN agents a ON a.id = e.agent_id
            WHERE {' AND '.join(clauses)}
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def list_rules(self, *, enabled: bool | None = None) -> list[Row]:
        """List trust rules for the current organization."""

        clauses = ["organization_id = ?"]
        values: list[object] = [self.organization_id]
        if enabled is not None:
            clauses.append("enabled = ?")
            values.append(1 if enabled else 0)
        return self.connection.execute(
            f"""
            SELECT *
            FROM trust_rules
            WHERE {' AND '.join(clauses)}
            ORDER BY event_type ASC
            """,
            values,
        ).fetchall()

    def get_rule(self, rule_id: str) -> Row | None:
        """Get one trust rule by id."""

        return self.connection.execute(
            "SELECT * FROM trust_rules WHERE id = ? AND organization_id = ?",
            (rule_id, self.organization_id),
        ).fetchone()

    def update_rule(self, rule_id: str, body: TrustRulePatchRequest) -> Row:
        """Patch mutable trust rule fields."""

        existing = self.get_rule(rule_id)
        if existing is None:
            raise TrustRuleNotFoundError("Trust rule not found.")
        values = body.model_dump(exclude_unset=True)
        if not values:
            return existing
        assignments: list[str] = []
        sql_values: list[object] = []
        for field, value in values.items():
            if field == "config":
                assignments.append("config_json = ?")
                sql_values.append(json.dumps(value or {}, sort_keys=True))
            elif field == "enabled":
                assignments.append("enabled = ?")
                sql_values.append(1 if value else 0)
            else:
                assignments.append(f"{field} = ?")
                sql_values.append(value)
        sql_values.extend([utc_now_iso(), rule_id, self.organization_id])
        self.connection.execute(
            f"""
            UPDATE trust_rules
            SET {', '.join(assignments)}, updated_at = ?
            WHERE id = ? AND organization_id = ?
            """,
            sql_values,
        )
        row = self.get_rule(rule_id)
        if row is None:
            raise TrustRuleNotFoundError("Trust rule not found.")
        return row

    def create_recalculation_run(
        self,
        *,
        status: str = "running",
        summary: dict[str, Any] | None = None,
        finished_at: str | None = None,
    ) -> Row:
        """Create a recalculation run row."""

        run_id = generate_id("trecalc")
        started_at = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO trust_recalculation_runs (
                id, organization_id, environment_id, status, started_at, finished_at, summary_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                self.organization_id,
                self.environment_id,
                status,
                started_at,
                finished_at,
                json.dumps(summary or {}, sort_keys=True),
            ),
        )
        row = self.connection.execute(
            """
            SELECT *
            FROM trust_recalculation_runs
            WHERE id = ? AND organization_id = ? AND environment_id = ?
            """,
            (run_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise ValueError("Created trust recalculation run could not be loaded.")
        return row

    def finish_recalculation_run(
        self,
        run_id: str,
        *,
        status: str,
        summary: dict[str, Any],
    ) -> Row:
        """Mark a recalculation run finished with summary data."""

        self.connection.execute(
            """
            UPDATE trust_recalculation_runs
            SET status = ?, finished_at = ?, summary_json = ?
            WHERE id = ? AND organization_id = ? AND environment_id = ?
            """,
            (
                status,
                utc_now_iso(),
                json.dumps(summary, sort_keys=True),
                run_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        row = self.connection.execute(
            """
            SELECT *
            FROM trust_recalculation_runs
            WHERE id = ? AND organization_id = ? AND environment_id = ?
            """,
            (run_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise ValueError("Trust recalculation run not found.")
        return row

    def list_agent_ids(self, *, agent_id: str | None = None) -> list[str]:
        """List active agent ids visible to the repository scope."""

        clauses = [
            "organization_id = ?",
            "environment_id = ?",
            "deleted_at IS NULL",
        ]
        values: list[object] = [self.organization_id, self.environment_id]
        if agent_id is not None:
            clauses.append("id = ?")
            values.append(agent_id)
        rows = self.connection.execute(
            f"""
            SELECT id
            FROM agents
            WHERE {' AND '.join(clauses)}
            ORDER BY name ASC, id ASC
            """,
            values,
        ).fetchall()
        return [row["id"] for row in rows]

    def _require_agent(self, agent_id: str) -> Row:
        row = self.connection.execute(
            """
            SELECT *
            FROM agents
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND deleted_at IS NULL
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise TrustAgentNotFoundError("Agent not found in current environment.")
        return row


def trust_score_response(row: Row) -> TrustScoreResponse:
    """Serialize trust score row."""

    return TrustScoreResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        agent_id=row["agent_id"],
        score=int(row["score"]),
        tier=row["tier"],
        dimensions=json.loads(row["dimensions_json"]),
        calculated_at=row["calculated_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        agent_name=row["agent_name"] if "agent_name" in row.keys() else None,
    )


def trust_event_response(row: Row) -> TrustEventResponse:
    """Serialize trust event row."""

    return TrustEventResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        agent_id=row["agent_id"],
        source_event_id=row["source_event_id"],
        dimension=row["dimension"],
        delta=int(row["delta"]),
        reason=row["reason"],
        score_before=int(row["score_before"]),
        score_after=int(row["score_after"]),
        created_at=row["created_at"],
        agent_name=row["agent_name"] if "agent_name" in row.keys() else None,
    )


def trust_rule_response(row: Row) -> TrustRuleResponse:
    """Serialize trust rule row."""

    return TrustRuleResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        event_type=row["event_type"],
        dimension=row["dimension"],
        delta=int(row["delta"]),
        min_delta=int(row["min_delta"]),
        max_delta=int(row["max_delta"]),
        enabled=bool(row["enabled"]),
        config=json.loads(row["config_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _stored_threshold_target_id(target_id: str | None) -> str:
    return target_id or DEFAULT_THRESHOLD_TARGET_ID


def _public_threshold_target_id(target_id: str) -> str | None:
    return target_id or None


def trust_threshold_response(row: Row) -> TrustThresholdResponse:
    """Serialize a trust threshold row."""

    return TrustThresholdResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        threshold_type=row["threshold_type"],
        target_type=row["target_type"],
        target_id=_public_threshold_target_id(row["target_id"]),
        min_score=int(row["min_score"]),
        required_tier=row["required_tier"],
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def trust_handshake_response(row: Row) -> TrustHandshakeResponse:
    """Serialize a trust handshake row."""

    return TrustHandshakeResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        source_agent_id=row["source_agent_id"],
        target_agent_id=row["target_agent_id"],
        purpose=row["purpose"],
        threshold_type=row["threshold_type"],
        target_type=row["target_type"],
        target_id=_public_threshold_target_id(row["target_id"]),
        required_score=int(row["required_score"]),
        required_tier=row["required_tier"],
        source_score=int(row["source_score"]),
        target_score=int(row["target_score"]),
        result=row["result"],
        reason=row["reason"],
        correlation_id=row["correlation_id"],
        metadata=json.loads(row["metadata_json"]),
        created_at=row["created_at"],
    )


def trust_recalculation_run_response(row: Row) -> TrustRecalculationRunResponse:
    """Serialize recalculation run row."""

    return TrustRecalculationRunResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        status=row["status"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        summary=json.loads(row["summary_json"]),
    )
