"""Emergency kill-switch persistence and local target handling."""

from __future__ import annotations

import sys
import json
from pathlib import Path
from product_platform.db.postgres import Connection, Row
from typing import Any

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.runtime.models import (
    SUPPORTED_KILL_SWITCH_TARGET_TYPES,
    KillSwitchEventResponse,
    KillSwitchRequest,
)


class KillSwitchValidationError(ValueError):
    """Raised when a kill-switch request is invalid."""


class KillSwitchTargetNotFoundError(ValueError):
    """Raised when a kill-switch target is not visible in tenant scope."""


class KillSwitchRepository:
    """Tenant-scoped kill-switch repository."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def trigger(self, body: KillSwitchRequest, *, actor_id: str) -> Row:
        """Validate, apply local stop effects, and persist a kill-switch event."""

        self._validate_request(body)
        self._require_target(body.target_type, body.target_id)
        self._apply_local_stop(body.target_type, body.target_id, body.reason)
        _hypervisor_kill(body.target_type, body.target_id, body.reason)
        event_id = generate_id("kill")
        self.connection.execute(
            """
            INSERT INTO kill_switch_events (
                id, organization_id, environment_id, target_type, target_id,
                scope, reason, actor_id, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                self.organization_id,
                self.environment_id,
                body.target_type,
                body.target_id,
                body.scope,
                body.reason,
                actor_id,
                "triggered",
                utc_now_iso(),
            ),
        )
        row = self.get_event(event_id)
        if row is None:
            raise KillSwitchValidationError("Created kill-switch event could not be loaded.")
        return row

    def get_event(self, event_id: str) -> Row | None:
        """Get one kill-switch event."""

        return self.connection.execute(
            """
            SELECT *
            FROM kill_switch_events
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (event_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_events(self, *, limit: int = 50, offset: int = 0) -> list[Row]:
        """List kill-switch events."""

        return self.connection.execute(
            """
            SELECT *
            FROM kill_switch_events
            WHERE organization_id = ?
              AND environment_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (self.organization_id, self.environment_id, limit, offset),
        ).fetchall()

    def agent_id_for_event(self, row: Row) -> str | None:
        """Resolve an agent id for audit/trust mapping where possible."""

        if row["target_type"] == "agent":
            return row["target_id"]
        if row["target_type"] == "session":
            session = self.connection.execute(
                """
                SELECT agent_id
                FROM runtime_sessions
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                (row["target_id"], self.organization_id, self.environment_id),
            ).fetchone()
            return session["agent_id"] if session is not None else None
        return None

    def _validate_request(self, body: KillSwitchRequest) -> None:
        if body.target_type not in SUPPORTED_KILL_SWITCH_TARGET_TYPES:
            supported = ", ".join(sorted(SUPPORTED_KILL_SWITCH_TARGET_TYPES))
            raise KillSwitchValidationError(f"Unsupported kill-switch target_type. Supported values: {supported}.")
        expected_confirmation = f"KILL {body.target_type}:{body.target_id}"
        if body.confirmation != expected_confirmation:
            raise KillSwitchValidationError(f"Confirmation must exactly match: {expected_confirmation}")

    def _require_target(self, target_type: str, target_id: str) -> None:
        queries = {
            "agent": (
                """
                SELECT 1
                FROM agents
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                  AND deleted_at IS NULL
                """,
                (target_id, self.organization_id, self.environment_id),
            ),
            "session": (
                """
                SELECT 1
                FROM runtime_sessions
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                (target_id, self.organization_id, self.environment_id),
            ),
            "mcp_server": (
                """
                SELECT 1
                FROM mcp_servers
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                (target_id, self.organization_id, self.environment_id),
            ),
            "tool": (
                """
                SELECT 1
                FROM mcp_tools t
                JOIN mcp_servers s ON s.id = t.server_id
                WHERE t.id = ?
                  AND s.organization_id = ?
                  AND s.environment_id = ?
                """,
                (target_id, self.organization_id, self.environment_id),
            ),
        }
        if target_type == "plugin":
            return
        query = queries[target_type]
        row = self.connection.execute(query[0], query[1]).fetchone()
        if row is None:
            raise KillSwitchTargetNotFoundError("Kill-switch target not found.")

    def _apply_local_stop(self, target_type: str, target_id: str, reason: str) -> None:
        now = utc_now_iso()
        if target_type == "agent":
            self.connection.execute(
                """
                UPDATE agents
                SET status = 'suspended',
                    updated_at = ?
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                  AND deleted_at IS NULL
                """,
                (now, target_id, self.organization_id, self.environment_id),
            )
        if target_type == "session":
            session = self.connection.execute(
                """
                SELECT metadata_json
                FROM runtime_sessions
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                (target_id, self.organization_id, self.environment_id),
            ).fetchone()
            metadata = json.loads(session["metadata_json"]) if session is not None else {}
            metadata["kill_switch_reason"] = reason
            self.connection.execute(
                """
                UPDATE runtime_sessions
                SET state = 'archived',
                    ended_at = ?,
                    metadata_json = ?
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                  AND state = 'active'
                """,
                (now, json.dumps(metadata, sort_keys=True), target_id, self.organization_id, self.environment_id),
            )
        if target_type == "mcp_server":
            self.connection.execute(
                """
                UPDATE mcp_servers
                SET status = 'disabled',
                    updated_at = ?
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                (now, target_id, self.organization_id, self.environment_id),
            )
        if target_type == "tool":
            self.connection.execute(
                """
                UPDATE mcp_tools
                SET status = 'disabled',
                    updated_at = ?
                WHERE id = ?
                """,
                (now, target_id),
            )


def kill_switch_event_response(row: Row) -> KillSwitchEventResponse:
    """Serialize a kill-switch event row."""

    return KillSwitchEventResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        scope=row["scope"],
        reason=row["reason"],
        actor_id=row["actor_id"],
        status=row["status"],
        created_at=row["created_at"],
    )


def _hypervisor_kill(target_type: str, target_id: str, reason: str) -> None:
    KillSwitch, KillReason = _load_hypervisor_kill_switch_classes()
    agent_did = target_id if target_type == "agent" else f"{target_type}:{target_id}"
    session_id = target_id if target_type == "session" else ""
    KillSwitch().kill(
        agent_did=agent_did,
        session_id=session_id,
        reason=KillReason.MANUAL,
        details=reason,
    )


def _load_hypervisor_kill_switch_classes() -> tuple[Any, Any]:
    try:
        from hypervisor.security.kill_switch import KillReason, KillSwitch

        return KillSwitch, KillReason
    except ModuleNotFoundError:
        hypervisor_src = Path(__file__).resolve().parents[4] / "agent-hypervisor" / "src"
        if str(hypervisor_src) not in sys.path:
            sys.path.insert(0, str(hypervisor_src))
        from hypervisor.security.kill_switch import KillReason, KillSwitch

        return KillSwitch, KillReason
