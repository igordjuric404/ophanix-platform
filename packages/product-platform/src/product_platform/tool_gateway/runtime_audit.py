"""Runtime action audit persistence for Tool Gateway invocations."""

from __future__ import annotations

import json
from sqlite3 import Connection, IntegrityError, Row
from typing import Any

from pydantic import BaseModel, Field, field_validator

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.tool_gateway.decision import summarize_tool_payload

TOOL_RUNTIME_ACTION_STATUSES = {
    "authentication_failed",
    "denied",
    "validation_failed",
    "allowed",
    "forwarded",
    "upstream_failed",
    "response_blocked",
    "completed",
}


class ToolRuntimeActionCreate(BaseModel):
    """Create a runtime action record for one gateway invocation."""

    request_id: str = Field(min_length=1)
    correlation_id: str | None = None
    agent_id: str | None = None
    credential_id: str | None = None
    tool_id: str | None = None
    permission_id: str | None = None
    decision_id: str | None = None
    action_status: str
    reason_code: str | None = None
    upstream_status_code: int | None = Field(default=None, ge=100, le=599)
    latency_ms: float | None = Field(default=None, ge=0)
    payload_summary: dict[str, Any] = Field(default_factory=dict)
    response_summary: dict[str, Any] | None = None
    redaction_applied: bool = False
    error_code: str | None = None

    @field_validator("request_id")
    @classmethod
    def _strip_request_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("request_id must not be blank.")
        return stripped

    @field_validator("action_status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        status = value.strip().lower()
        if status not in TOOL_RUNTIME_ACTION_STATUSES:
            supported = ", ".join(sorted(TOOL_RUNTIME_ACTION_STATUSES))
            raise ValueError(f"action_status must be one of: {supported}.")
        return status


class ToolRuntimeActionUpdate(BaseModel):
    """Patch runtime action status and execution metadata."""

    action_status: str | None = None
    reason_code: str | None = None
    upstream_status_code: int | None = Field(default=None, ge=100, le=599)
    latency_ms: float | None = Field(default=None, ge=0)
    response_summary: dict[str, Any] | None = None
    redaction_applied: bool | None = None
    error_code: str | None = None

    @field_validator("action_status")
    @classmethod
    def _validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        status = value.strip().lower()
        if status not in TOOL_RUNTIME_ACTION_STATUSES:
            supported = ", ".join(sorted(TOOL_RUNTIME_ACTION_STATUSES))
            raise ValueError(f"action_status must be one of: {supported}.")
        return status


class ToolRuntimeActionEventCreate(BaseModel):
    """Append one timeline event to a runtime action."""

    event_type: str = Field(min_length=1)
    event_summary: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_type")
    @classmethod
    def _strip_event_type(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("event_type must not be blank.")
        return stripped


class ToolRuntimeActionQuery(BaseModel):
    """Scoped runtime action list filters."""

    decision_id: str | None = None
    correlation_id: str | None = None
    action_status: str | None = None
    agent_id: str | None = None
    tool_id: str | None = None
    created_from: str | None = None
    created_to: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @field_validator("action_status")
    @classmethod
    def _validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        status = value.strip().lower()
        if status not in TOOL_RUNTIME_ACTION_STATUSES:
            supported = ", ".join(sorted(TOOL_RUNTIME_ACTION_STATUSES))
            raise ValueError(f"action_status must be one of: {supported}.")
        return status


class ToolRuntimeActionEventResponse(BaseModel):
    """One runtime action timeline event."""

    id: str
    runtime_action_id: str
    event_type: str
    event_summary: dict[str, Any]
    created_at: str


class ToolRuntimeActionResponse(BaseModel):
    """Runtime action list/detail row."""

    id: str
    organization_id: str
    environment_id: str
    request_id: str
    correlation_id: str | None = None
    agent_id: str | None = None
    credential_id: str | None = None
    tool_id: str | None = None
    permission_id: str | None = None
    decision_id: str | None = None
    action_status: str
    reason_code: str | None = None
    upstream_status_code: int | None = None
    latency_ms: float | None = None
    payload_summary: dict[str, Any]
    response_summary: dict[str, Any] | None = None
    redaction_applied: bool
    error_code: str | None = None
    created_at: str
    updated_at: str


class ToolRuntimeActionDetailResponse(ToolRuntimeActionResponse):
    """Runtime action detail including event timeline."""

    events: list[ToolRuntimeActionEventResponse] = Field(default_factory=list)


class ToolRuntimeActionRepository:
    """Persistence for tenant-scoped Tool Gateway runtime actions."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create_action(
        self,
        body: ToolRuntimeActionCreate,
        *,
        created_at: str | None = None,
    ) -> Row:
        """Create a runtime action with sanitized summaries."""

        action_id = generate_id("toolrun")
        now = created_at or utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO tool_runtime_actions (
                id, organization_id, environment_id, request_id, correlation_id,
                agent_id, credential_id, tool_id, permission_id, decision_id,
                action_status, reason_code, upstream_status_code, latency_ms,
                payload_summary_json, response_summary_json, redaction_applied,
                error_code, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_id,
                self.organization_id,
                self.environment_id,
                body.request_id,
                body.correlation_id,
                body.agent_id,
                body.credential_id,
                body.tool_id,
                body.permission_id,
                body.decision_id,
                body.action_status,
                body.reason_code,
                body.upstream_status_code,
                body.latency_ms,
                _summary_to_json(body.payload_summary),
                _optional_summary_to_json(body.response_summary),
                1 if body.redaction_applied else 0,
                body.error_code,
                now,
                now,
            ),
        )
        row = self.get_action(action_id)
        if row is None:
            raise ValueError("Created tool runtime action could not be loaded.")
        return row

    def update_action(
        self,
        action_id: str,
        body: ToolRuntimeActionUpdate,
        *,
        updated_at: str | None = None,
    ) -> Row:
        """Update runtime action status and execution metadata."""

        fields: list[str] = []
        values: list[object | None] = []
        field_map = {
            "action_status": "action_status",
            "reason_code": "reason_code",
            "upstream_status_code": "upstream_status_code",
            "latency_ms": "latency_ms",
            "response_summary": "response_summary_json",
            "redaction_applied": "redaction_applied",
            "error_code": "error_code",
        }
        for model_field, column in field_map.items():
            if model_field in body.model_fields_set:
                value = getattr(body, model_field)
                if model_field == "response_summary":
                    value = _optional_summary_to_json(value)
                if model_field == "redaction_applied" and value is not None:
                    value = 1 if value else 0
                fields.append(f"{column} = ?")
                values.append(value)
        if fields:
            fields.append("updated_at = ?")
            values.append(updated_at or utc_now_iso())
            values.extend([action_id, self.organization_id, self.environment_id])
            self.connection.execute(
                f"""
                UPDATE tool_runtime_actions
                SET {', '.join(fields)}
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                values,
            )
        row = self.get_action(action_id)
        if row is None:
            raise ValueError("Tool runtime action not found.")
        return row

    def append_event(
        self,
        action_id: str,
        body: ToolRuntimeActionEventCreate,
        *,
        created_at: str | None = None,
    ) -> Row:
        """Append a sanitized event to a visible runtime action."""

        if self.get_action(action_id) is None:
            raise ValueError("Tool runtime action not found.")
        event_id = generate_id("toolrunevt")
        self.connection.execute(
            """
            INSERT INTO tool_runtime_action_events (
                id, runtime_action_id, event_type, event_summary_json, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event_id,
                action_id,
                body.event_type,
                _summary_to_json(body.event_summary),
                created_at or utc_now_iso(),
            ),
        )
        row = self.connection.execute(
            """
            SELECT *
            FROM tool_runtime_action_events
            WHERE id = ?
            """,
            (event_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Created tool runtime action event could not be loaded.")
        return row

    def get_action(self, action_id: str) -> Row | None:
        """Get one runtime action in tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM tool_runtime_actions
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (action_id, self.organization_id, self.environment_id),
        ).fetchone()

    def get_action_detail(self, action_id: str) -> dict[str, Any] | None:
        """Get one runtime action plus event timeline."""

        row = self.get_action(action_id)
        if row is None:
            return None
        return {"action": row, "events": self.list_events(action_id)}

    def list_events(self, action_id: str) -> list[Row]:
        """List ordered events for one visible runtime action."""

        if self.get_action(action_id) is None:
            return []
        return self.connection.execute(
            """
            SELECT *
            FROM tool_runtime_action_events
            WHERE runtime_action_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (action_id,),
        ).fetchall()

    def list_actions(self, query: ToolRuntimeActionQuery | None = None) -> list[Row]:
        """List runtime actions in tenant scope."""

        query = query or ToolRuntimeActionQuery()
        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        for column, value in [
            ("decision_id", query.decision_id),
            ("correlation_id", query.correlation_id),
            ("action_status", query.action_status),
            ("agent_id", query.agent_id),
            ("tool_id", query.tool_id),
        ]:
            if value is not None:
                clauses.append(f"{column} = ?")
                values.append(value)
        if query.created_from is not None:
            clauses.append("created_at >= ?")
            values.append(query.created_from)
        if query.created_to is not None:
            clauses.append("created_at <= ?")
            values.append(query.created_to)
        values.extend([query.limit, query.offset])
        return self.connection.execute(
            f"""
            SELECT *
            FROM tool_runtime_actions
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()


class ToolInvocationIdempotencyConflictError(ValueError):
    """Raised when an idempotency key is reused with different request content."""


class ToolInvocationIdempotencyInProgressError(ValueError):
    """Raised when an idempotent invocation is already running and has no replay yet."""


class ToolInvocationIdempotencyRepository:
    """Persistence for idempotent Tool Gateway invocation replay records."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def begin_invocation(
        self,
        *,
        credential_id: str,
        tool_id: str,
        idempotency_key: str,
        request_hash: str,
        request_id: str,
        correlation_id: str | None,
    ) -> tuple[bool, Row]:
        """Create or load a replay record.

        Returns `(True, row)` for a new invocation and `(False, row)` for a
        previously completed invocation that can be replayed.
        """

        existing = self.get_record(
            credential_id=credential_id,
            tool_id=tool_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return False, self._validated_existing(existing, request_hash=request_hash)
        record_id = generate_id("toolidem")
        now = utc_now_iso()
        try:
            self.connection.execute(
                """
                INSERT INTO tool_invocation_idempotency_records (
                    id, organization_id, environment_id, credential_id, tool_id,
                    idempotency_key, request_hash, request_id, correlation_id,
                    status, response_status_code, response_body_json, error_code,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    self.organization_id,
                    self.environment_id,
                    credential_id,
                    tool_id,
                    idempotency_key,
                    request_hash,
                    request_id,
                    correlation_id,
                    "in_progress",
                    None,
                    None,
                    None,
                    now,
                    now,
                ),
            )
        except IntegrityError:
            existing = self.get_record(
                credential_id=credential_id,
                tool_id=tool_id,
                idempotency_key=idempotency_key,
            )
            if existing is None:
                raise
            return False, self._validated_existing(existing, request_hash=request_hash)
        row = self.get_record(
            credential_id=credential_id,
            tool_id=tool_id,
            idempotency_key=idempotency_key,
        )
        if row is None:
            raise ValueError("Created idempotency record could not be loaded.")
        return True, row

    def complete_invocation(
        self,
        record_id: str,
        *,
        response_status_code: int,
        response_body: dict[str, Any],
        error_code: str | None = None,
    ) -> Row:
        """Store the public gateway response for future idempotent replays."""

        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE tool_invocation_idempotency_records
            SET status = ?,
                response_status_code = ?,
                response_body_json = ?,
                error_code = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (
                "completed",
                response_status_code,
                json.dumps(response_body, sort_keys=True, separators=(",", ":")),
                error_code,
                now,
                record_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        row = self.get_record_by_id(record_id)
        if row is None:
            raise ValueError("Idempotency record not found.")
        return row

    def get_record_by_id(self, record_id: str) -> Row | None:
        """Get one idempotency record by id in tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM tool_invocation_idempotency_records
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (record_id, self.organization_id, self.environment_id),
        ).fetchone()

    def get_record(
        self,
        *,
        credential_id: str,
        tool_id: str,
        idempotency_key: str,
    ) -> Row | None:
        """Get one idempotency record by its external replay key."""

        return self.connection.execute(
            """
            SELECT *
            FROM tool_invocation_idempotency_records
            WHERE organization_id = ?
              AND environment_id = ?
              AND credential_id = ?
              AND tool_id = ?
              AND idempotency_key = ?
            """,
            (
                self.organization_id,
                self.environment_id,
                credential_id,
                tool_id,
                idempotency_key,
            ),
        ).fetchone()

    def _validated_existing(self, row: Row, *, request_hash: str) -> Row:
        if row["request_hash"] != request_hash:
            raise ToolInvocationIdempotencyConflictError(
                "Idempotency key was already used with different request content."
            )
        if row["status"] != "completed" or row["response_body_json"] is None:
            raise ToolInvocationIdempotencyInProgressError(
                "Idempotent invocation is still in progress."
            )
        return row


def idempotency_response_body(row: Row) -> dict[str, Any]:
    """Return the stored public response body for a completed replay record."""

    value = row["response_body_json"]
    if not isinstance(value, str) or not value:
        raise ToolInvocationIdempotencyInProgressError(
            "Idempotent invocation is still in progress."
        )
    loaded = json.loads(value)
    if not isinstance(loaded, dict):
        raise ValueError("Stored idempotency response is not an object.")
    return loaded


def tool_runtime_action_response(row: Row) -> ToolRuntimeActionResponse:
    """Serialize one runtime action row."""

    return ToolRuntimeActionResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        request_id=row["request_id"],
        correlation_id=row["correlation_id"],
        agent_id=row["agent_id"],
        credential_id=row["credential_id"],
        tool_id=row["tool_id"],
        permission_id=row["permission_id"],
        decision_id=row["decision_id"],
        action_status=row["action_status"],
        reason_code=row["reason_code"],
        upstream_status_code=row["upstream_status_code"],
        latency_ms=row["latency_ms"],
        payload_summary=_loads_mapping(row["payload_summary_json"]),
        response_summary=_loads_optional_mapping(row["response_summary_json"]),
        redaction_applied=bool(row["redaction_applied"]),
        error_code=row["error_code"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def tool_runtime_action_event_response(row: Row) -> ToolRuntimeActionEventResponse:
    """Serialize one runtime action event row."""

    return ToolRuntimeActionEventResponse(
        id=row["id"],
        runtime_action_id=row["runtime_action_id"],
        event_type=row["event_type"],
        event_summary=_loads_mapping(row["event_summary_json"]),
        created_at=row["created_at"],
    )


def tool_runtime_action_detail_response(detail: dict[str, Any] | None) -> ToolRuntimeActionDetailResponse:
    """Serialize a runtime action with timeline events."""

    if detail is None:
        raise ValueError("Tool runtime action not found.")
    base = tool_runtime_action_response(detail["action"]).model_dump()
    return ToolRuntimeActionDetailResponse(
        **base,
        events=[tool_runtime_action_event_response(row) for row in detail["events"]],
    )


def _summary_to_json(value: dict[str, Any]) -> str:
    return json.dumps(
        summarize_tool_payload(value),
        sort_keys=True,
        separators=(",", ":"),
    )


def _optional_summary_to_json(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return _summary_to_json(value)


def _loads_mapping(value: str) -> dict[str, Any]:
    loaded = json.loads(value)
    return loaded if isinstance(loaded, dict) else {}


def _loads_optional_mapping(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return _loads_mapping(value)
