"""Mesh message, handoff, and topology persistence."""

from __future__ import annotations

import json
from sqlite3 import Connection, Row

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.mesh.models import (
    MeshHandoffCreateRequest,
    MeshHandoffResponse,
    MeshMessageCreateRequest,
    MeshMessageResponse,
    ProtocolBridgeCreateRequest,
    ProtocolBridgeHealthCheckResponse,
    ProtocolBridgePatchRequest,
    ProtocolBridgeRouteCreateRequest,
    ProtocolBridgeRouteResponse,
    ProtocolBridgeResponse,
)


class MeshAgentNotFoundError(ValueError):
    """Raised when a mesh message references an agent outside tenant scope."""


class ProtocolBridgeNotFoundError(ValueError):
    """Raised when a protocol bridge is not visible in tenant scope."""


class ProtocolBridgeReferenceNotFoundError(ValueError):
    """Raised when a protocol bridge route references an invisible resource."""


SENSITIVE_CONFIG_KEY_PARTS = (
    "api_key",
    "apikey",
    "client_secret",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)
SECRET_REFERENCE_SUFFIXES = (
    "secret_id",
    "secret_ids",
    "secret_arn",
    "secret_name",
    "secret_ref",
    "secret_refs",
)
REDACTED_CONFIG_VALUE = "[redacted]"


class MeshRepository:
    """Tenant-scoped mesh communication repository."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create_message(self, body: MeshMessageCreateRequest) -> Row:
        """Persist an inter-agent mesh message."""

        self._require_agent(body.source_agent_id)
        self._require_agent(body.target_agent_id)
        message_id = generate_id("mmsg")
        self.connection.execute(
            """
            INSERT INTO mesh_messages (
                id, organization_id, environment_id, source_agent_id,
                target_agent_id, protocol, action, decision, latency_ms,
                correlation_id, payload_summary_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                self.organization_id,
                self.environment_id,
                body.source_agent_id,
                body.target_agent_id,
                body.protocol,
                body.action,
                body.decision,
                body.latency_ms,
                body.correlation_id,
                json.dumps(body.payload_summary, sort_keys=True),
                utc_now_iso(),
            ),
        )
        row = self.get_message(message_id)
        if row is None:
            raise ValueError("Created mesh message could not be loaded.")
        return row

    def get_message(self, message_id: str) -> Row | None:
        """Get one mesh message with agent context."""

        return self.connection.execute(
            """
            SELECT
                m.*,
                source.name AS source_agent_name,
                target.name AS target_agent_name,
                source.status AS source_agent_status,
                target.status AS target_agent_status,
                source.trust_tier AS source_trust_tier,
                target.trust_tier AS target_trust_tier
            FROM mesh_messages m
            JOIN agents source ON source.id = m.source_agent_id
            JOIN agents target ON target.id = m.target_agent_id
            WHERE m.id = ?
              AND m.organization_id = ?
              AND m.environment_id = ?
              AND source.deleted_at IS NULL
              AND target.deleted_at IS NULL
            """,
            (message_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_messages(
        self,
        *,
        source_agent_id: str | None = None,
        target_agent_id: str | None = None,
        protocol: str | None = None,
        decision: str | None = None,
        action: str | None = None,
        correlation_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List mesh messages with feed filters."""

        clauses = ["m.organization_id = ?", "m.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        for column, value in [
            ("m.source_agent_id", source_agent_id),
            ("m.target_agent_id", target_agent_id),
            ("m.protocol", protocol),
            ("m.decision", decision),
            ("m.action", action),
            ("m.correlation_id", correlation_id),
        ]:
            if value:
                clauses.append(f"{column} = ?")
                values.append(value)
        if start_time:
            clauses.append("m.created_at >= ?")
            values.append(start_time)
        if end_time:
            clauses.append("m.created_at <= ?")
            values.append(end_time)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT
                m.*,
                source.name AS source_agent_name,
                target.name AS target_agent_name,
                source.status AS source_agent_status,
                target.status AS target_agent_status,
                source.trust_tier AS source_trust_tier,
                target.trust_tier AS target_trust_tier
            FROM mesh_messages m
            JOIN agents source ON source.id = m.source_agent_id
            JOIN agents target ON target.id = m.target_agent_id
            WHERE {' AND '.join(clauses)}
              AND source.deleted_at IS NULL
              AND target.deleted_at IS NULL
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def create_handoff(self, body: MeshHandoffCreateRequest) -> Row:
        """Persist a mesh handoff attempt."""

        self._require_agent(body.source_agent_id)
        self._require_agent(body.target_agent_id)
        handoff_id = generate_id("mhnd")
        self.connection.execute(
            """
            INSERT INTO mesh_handoffs (
                id, organization_id, environment_id, source_agent_id,
                target_agent_id, task_type, required_capabilities_json,
                trust_result, policy_result, status, reason, correlation_id,
                metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                handoff_id,
                self.organization_id,
                self.environment_id,
                body.source_agent_id,
                body.target_agent_id,
                body.task_type,
                json.dumps(body.required_capabilities, sort_keys=True),
                body.trust_result,
                body.policy_result,
                body.status,
                body.reason or "",
                body.correlation_id,
                json.dumps(body.metadata, sort_keys=True),
                utc_now_iso(),
            ),
        )
        row = self.get_handoff(handoff_id)
        if row is None:
            raise ValueError("Created mesh handoff could not be loaded.")
        return row

    def get_handoff(self, handoff_id: str) -> Row | None:
        """Get one mesh handoff with agent context."""

        return self.connection.execute(
            """
            SELECT
                h.*,
                source.name AS source_agent_name,
                target.name AS target_agent_name
            FROM mesh_handoffs h
            JOIN agents source ON source.id = h.source_agent_id
            JOIN agents target ON target.id = h.target_agent_id
            WHERE h.id = ?
              AND h.organization_id = ?
              AND h.environment_id = ?
              AND source.deleted_at IS NULL
              AND target.deleted_at IS NULL
            """,
            (handoff_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_handoffs(
        self,
        *,
        source_agent_id: str | None = None,
        target_agent_id: str | None = None,
        status: str | None = None,
        correlation_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List mesh handoffs."""

        clauses = ["h.organization_id = ?", "h.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        for column, value in [
            ("h.source_agent_id", source_agent_id),
            ("h.target_agent_id", target_agent_id),
            ("h.status", status),
            ("h.correlation_id", correlation_id),
        ]:
            if value:
                clauses.append(f"{column} = ?")
                values.append(value)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT
                h.*,
                source.name AS source_agent_name,
                target.name AS target_agent_name
            FROM mesh_handoffs h
            JOIN agents source ON source.id = h.source_agent_id
            JOIN agents target ON target.id = h.target_agent_id
            WHERE {' AND '.join(clauses)}
              AND source.deleted_at IS NULL
              AND target.deleted_at IS NULL
            ORDER BY h.created_at DESC, h.id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def create_protocol_bridge(self, body: ProtocolBridgeCreateRequest) -> Row:
        """Persist a protocol bridge configuration without raw secret values."""

        bridge_id = generate_id("pbrg")
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO protocol_bridges (
                id, organization_id, environment_id, name, bridge_type,
                status, config_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bridge_id,
                self.organization_id,
                self.environment_id,
                body.name,
                body.bridge_type,
                body.status,
                json.dumps(scrub_protocol_bridge_config(body.config), sort_keys=True),
                now,
                now,
            ),
        )
        row = self.get_protocol_bridge(bridge_id)
        if row is None:
            raise ValueError("Created protocol bridge could not be loaded.")
        return row

    def get_protocol_bridge(self, bridge_id: str) -> Row | None:
        """Get one protocol bridge in tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM protocol_bridges
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (bridge_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_protocol_bridges(
        self,
        *,
        bridge_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List protocol bridges in tenant scope."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if bridge_type:
            clauses.append("bridge_type = ?")
            values.append(bridge_type)
        if status:
            clauses.append("status = ?")
            values.append(status)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT *
            FROM protocol_bridges
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def update_protocol_bridge(self, bridge_id: str, body: ProtocolBridgePatchRequest) -> Row:
        """Patch protocol bridge metadata or config."""

        existing = self.get_protocol_bridge(bridge_id)
        if existing is None:
            raise ProtocolBridgeNotFoundError("Protocol bridge not found.")
        fields: list[str] = []
        values: list[object] = []
        if "name" in body.model_fields_set and body.name is not None:
            fields.append("name = ?")
            values.append(body.name)
        if "status" in body.model_fields_set and body.status is not None:
            fields.append("status = ?")
            values.append(body.status)
        if "config" in body.model_fields_set and body.config is not None:
            fields.append("config_json = ?")
            values.append(json.dumps(scrub_protocol_bridge_config(body.config), sort_keys=True))
        if not fields:
            return existing
        fields.append("updated_at = ?")
        values.append(utc_now_iso())
        values.extend([bridge_id, self.organization_id, self.environment_id])
        self.connection.execute(
            f"""
            UPDATE protocol_bridges
            SET {', '.join(fields)}
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            values,
        )
        row = self.get_protocol_bridge(bridge_id)
        if row is None:
            raise ProtocolBridgeNotFoundError("Protocol bridge not found.")
        return row

    def create_protocol_bridge_route(
        self,
        bridge_id: str,
        body: ProtocolBridgeRouteCreateRequest,
    ) -> Row:
        """Persist a protocol bridge route after validating scoped references."""

        if self.get_protocol_bridge(bridge_id) is None:
            raise ProtocolBridgeNotFoundError("Protocol bridge not found.")
        if body.source_agent_id:
            self._require_agent(body.source_agent_id)
        if body.target_agent_id:
            self._require_agent(body.target_agent_id)
        if body.policy_binding_id:
            self._require_policy_binding(body.policy_binding_id)
        route_id = generate_id("pbrt")
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO protocol_bridge_routes (
                id, bridge_id, source_protocol, target_protocol,
                source_agent_id, target_agent_id, policy_binding_id,
                enabled, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                route_id,
                bridge_id,
                body.source_protocol,
                body.target_protocol,
                body.source_agent_id,
                body.target_agent_id,
                body.policy_binding_id,
                1 if body.enabled else 0,
                now,
                now,
            ),
        )
        row = self.get_protocol_bridge_route(route_id)
        if row is None:
            raise ValueError("Created protocol bridge route could not be loaded.")
        return row

    def get_protocol_bridge_route(self, route_id: str) -> Row | None:
        """Get one route for a visible protocol bridge."""

        return self.connection.execute(
            """
            SELECT
                r.*,
                source.name AS source_agent_name,
                target.name AS target_agent_name
            FROM protocol_bridge_routes r
            JOIN protocol_bridges b ON b.id = r.bridge_id
            LEFT JOIN agents source
                ON source.id = r.source_agent_id
               AND source.organization_id = b.organization_id
               AND source.environment_id = b.environment_id
               AND source.deleted_at IS NULL
            LEFT JOIN agents target
                ON target.id = r.target_agent_id
               AND target.organization_id = b.organization_id
               AND target.environment_id = b.environment_id
               AND target.deleted_at IS NULL
            WHERE r.id = ?
              AND b.organization_id = ?
              AND b.environment_id = ?
            """,
            (route_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_protocol_bridge_routes(self, bridge_id: str) -> list[Row]:
        """List routes for a visible protocol bridge."""

        if self.get_protocol_bridge(bridge_id) is None:
            raise ProtocolBridgeNotFoundError("Protocol bridge not found.")
        return self.connection.execute(
            """
            SELECT
                r.*,
                source.name AS source_agent_name,
                target.name AS target_agent_name
            FROM protocol_bridge_routes r
            JOIN protocol_bridges b ON b.id = r.bridge_id
            LEFT JOIN agents source
                ON source.id = r.source_agent_id
               AND source.organization_id = b.organization_id
               AND source.environment_id = b.environment_id
               AND source.deleted_at IS NULL
            LEFT JOIN agents target
                ON target.id = r.target_agent_id
               AND target.organization_id = b.organization_id
               AND target.environment_id = b.environment_id
               AND target.deleted_at IS NULL
            WHERE r.bridge_id = ?
              AND b.organization_id = ?
              AND b.environment_id = ?
            ORDER BY r.created_at DESC, r.id DESC
            """,
            (bridge_id, self.organization_id, self.environment_id),
        ).fetchall()

    def create_protocol_bridge_health_check(
        self,
        bridge_id: str,
        *,
        status: str,
        latency_ms: int,
        message: str,
    ) -> Row:
        """Persist a protocol bridge health check and update current bridge status."""

        if self.get_protocol_bridge(bridge_id) is None:
            raise ProtocolBridgeNotFoundError("Protocol bridge not found.")
        check_id = generate_id("pbhc")
        checked_at = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO protocol_bridge_health_checks (
                id, bridge_id, status, latency_ms, message, checked_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (check_id, bridge_id, status, latency_ms, message, checked_at),
        )
        self.connection.execute(
            """
            UPDATE protocol_bridges
            SET status = ?, updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (status, checked_at, bridge_id, self.organization_id, self.environment_id),
        )
        row = self.get_protocol_bridge_health_check(check_id)
        if row is None:
            raise ValueError("Created protocol bridge health check could not be loaded.")
        return row

    def get_protocol_bridge_health_check(self, check_id: str) -> Row | None:
        """Get one health check for a visible protocol bridge."""

        return self.connection.execute(
            """
            SELECT h.*
            FROM protocol_bridge_health_checks h
            JOIN protocol_bridges b ON b.id = h.bridge_id
            WHERE h.id = ?
              AND b.organization_id = ?
              AND b.environment_id = ?
            """,
            (check_id, self.organization_id, self.environment_id),
        ).fetchone()

    def latest_protocol_bridge_health_check(self, bridge_id: str) -> Row | None:
        """Return the latest health check for a visible bridge."""

        if self.get_protocol_bridge(bridge_id) is None:
            raise ProtocolBridgeNotFoundError("Protocol bridge not found.")
        return self.connection.execute(
            """
            SELECT h.*
            FROM protocol_bridge_health_checks h
            JOIN protocol_bridges b ON b.id = h.bridge_id
            WHERE h.bridge_id = ?
              AND b.organization_id = ?
              AND b.environment_id = ?
            ORDER BY h.checked_at DESC, h.id DESC
            LIMIT 1
            """,
            (bridge_id, self.organization_id, self.environment_id),
        ).fetchone()

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
            raise MeshAgentNotFoundError("Agent not found in current environment.")
        return row

    def _require_policy_binding(self, binding_id: str) -> Row:
        row = self.connection.execute(
            """
            SELECT *
            FROM policy_bindings
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND status != 'deleted'
            """,
            (binding_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise ProtocolBridgeReferenceNotFoundError(
                "Policy binding not found in current environment."
            )
        return row


def scrub_protocol_bridge_config(value: object) -> object:
    """Return config JSON with raw secrets redacted but secret references retained."""

    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for key, child in value.items():
            text_key = str(key)
            if _is_sensitive_config_key(text_key):
                sanitized[text_key] = REDACTED_CONFIG_VALUE
            else:
                sanitized[text_key] = scrub_protocol_bridge_config(child)
        return sanitized
    if isinstance(value, list):
        return [scrub_protocol_bridge_config(item) for item in value]
    return value


def _is_sensitive_config_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_").replace(".", "_")
    if normalized.endswith(SECRET_REFERENCE_SUFFIXES):
        return False
    return any(part in normalized for part in SENSITIVE_CONFIG_KEY_PARTS)


def mesh_message_response(row: Row) -> MeshMessageResponse:
    """Serialize a mesh message row."""

    return MeshMessageResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        source_agent_id=row["source_agent_id"],
        target_agent_id=row["target_agent_id"],
        protocol=row["protocol"],
        action=row["action"],
        decision=row["decision"],
        latency_ms=int(row["latency_ms"]),
        correlation_id=row["correlation_id"],
        payload_summary=json.loads(row["payload_summary_json"]),
        created_at=row["created_at"],
        source_agent_name=row["source_agent_name"] if "source_agent_name" in row.keys() else None,
        target_agent_name=row["target_agent_name"] if "target_agent_name" in row.keys() else None,
        source_trust_tier=row["source_trust_tier"] if "source_trust_tier" in row.keys() else None,
        target_trust_tier=row["target_trust_tier"] if "target_trust_tier" in row.keys() else None,
    )


def mesh_handoff_response(row: Row) -> MeshHandoffResponse:
    """Serialize a mesh handoff row."""

    return MeshHandoffResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        source_agent_id=row["source_agent_id"],
        target_agent_id=row["target_agent_id"],
        task_type=row["task_type"],
        required_capabilities=json.loads(row["required_capabilities_json"]),
        trust_result=row["trust_result"],
        policy_result=row["policy_result"],
        status=row["status"],
        reason=row["reason"],
        correlation_id=row["correlation_id"],
        metadata=json.loads(row["metadata_json"]),
        created_at=row["created_at"],
        source_agent_name=row["source_agent_name"] if "source_agent_name" in row.keys() else None,
        target_agent_name=row["target_agent_name"] if "target_agent_name" in row.keys() else None,
    )


def protocol_bridge_route_response(row: Row) -> ProtocolBridgeRouteResponse:
    """Serialize a protocol bridge route row."""

    return ProtocolBridgeRouteResponse(
        id=row["id"],
        bridge_id=row["bridge_id"],
        source_protocol=row["source_protocol"],
        target_protocol=row["target_protocol"],
        source_agent_id=row["source_agent_id"],
        target_agent_id=row["target_agent_id"],
        policy_binding_id=row["policy_binding_id"],
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        source_agent_name=row["source_agent_name"] if "source_agent_name" in row.keys() else None,
        target_agent_name=row["target_agent_name"] if "target_agent_name" in row.keys() else None,
    )


def protocol_bridge_health_check_response(row: Row) -> ProtocolBridgeHealthCheckResponse:
    """Serialize a protocol bridge health check row."""

    return ProtocolBridgeHealthCheckResponse(
        id=row["id"],
        bridge_id=row["bridge_id"],
        status=row["status"],
        latency_ms=int(row["latency_ms"]),
        message=row["message"],
        checked_at=row["checked_at"],
    )


def protocol_bridge_response(
    row: Row,
    *,
    current_health: ProtocolBridgeHealthCheckResponse | None = None,
    routes: list[ProtocolBridgeRouteResponse] | None = None,
) -> ProtocolBridgeResponse:
    """Serialize a protocol bridge row."""

    return ProtocolBridgeResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        name=row["name"],
        bridge_type=row["bridge_type"],
        status=row["status"],
        config=json.loads(row["config_json"]),
        current_health=current_health,
        routes=routes or [],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
