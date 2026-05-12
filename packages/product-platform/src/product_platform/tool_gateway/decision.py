"""Deterministic Tool Gateway policy decisions."""

from __future__ import annotations

import json
import re
from product_platform.db.postgres import Connection, Row
from typing import Any

from pydantic import BaseModel, Field, field_validator

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.tool_gateway.auth import GatewayPrincipal
from product_platform.tool_gateway.repository import ToolRegistryRepository

TOOL_POLICY_DECISIONS = {"allow", "deny"}
TOOL_POLICY_REASON_CODES = {
    "agent_missing",
    "agent_inactive",
    "tool_missing",
    "tool_inactive",
    "permission_missing",
    "scope_insufficient",
    "policy_denied",
    "policy_error",
    "allowed",
}
MAX_PAYLOAD_SUMMARY_DEPTH = 8
MAX_PAYLOAD_SUMMARY_ITEMS = 50
MAX_PAYLOAD_SUMMARY_STRING_LENGTH = 120
MAX_PAYLOAD_SUMMARY_TOTAL_CHARS = 16_384
REDACTED_PAYLOAD_VALUE = "[redacted]"
SECRET_LIKE_KEY_TOKENS = (
    "authorization",
    "api_key",
    "address",
    "credential",
    "email",
    "password",
    "phone",
    "secret",
    "social_security_number",
    "ssn",
    "token",
    "key",
)
SECRET_LIKE_VALUE_PATTERNS = (
    re.compile(r"\b(?:sk|pk|tok|key|secret|ghp|glpat|xox[baprs])-[A-Za-z0-9_\-]{8,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b", re.IGNORECASE),
)
TOOL_POLICY_REASON_MESSAGES = {
    "agent_missing": "Authenticated agent identity was not found.",
    "agent_inactive": "Agent is not active.",
    "tool_missing": "Requested tool was not found.",
    "tool_inactive": "Requested tool is not active.",
    "permission_missing": "No active permission binding was found.",
    "scope_insufficient": "Permission or credential scope is insufficient for the tool.",
    "policy_denied": "Policy hook denied the tool call.",
    "policy_error": "Policy hook failed closed.",
    "allowed": "Tool call is allowed.",
}


class ToolPolicyDecisionCreate(BaseModel):
    """Internal persistence request for a Tool Gateway policy decision."""

    agent_id: str | None = None
    tool_id: str | None = None
    permission_id: str | None = None
    decision: str
    reason_code: str
    reason_message: str = Field(min_length=1)
    matched_policy_id: str | None = None
    request_id: str = Field(min_length=1)
    correlation_id: str | None = None
    payload_summary: dict[str, Any] = Field(default_factory=dict)

    @field_validator("decision")
    @classmethod
    def _validate_decision(cls, value: str) -> str:
        decision = value.strip().lower()
        if decision not in TOOL_POLICY_DECISIONS:
            supported = ", ".join(sorted(TOOL_POLICY_DECISIONS))
            raise ValueError(f"decision must be one of: {supported}.")
        return decision

    @field_validator("reason_code")
    @classmethod
    def _validate_reason_code(cls, value: str) -> str:
        reason_code = value.strip().lower()
        if reason_code not in TOOL_POLICY_REASON_CODES:
            supported = ", ".join(sorted(TOOL_POLICY_REASON_CODES))
            raise ValueError(f"reason_code must be one of: {supported}.")
        return reason_code

    @field_validator("reason_message", "request_id")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("agent_id", "tool_id", "permission_id", "matched_policy_id", "correlation_id")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ToolPolicyDecisionResult(BaseModel):
    """Persisted Tool Gateway policy decision."""

    id: str
    organization_id: str
    environment_id: str
    agent_id: str | None = None
    tool_id: str | None = None
    permission_id: str | None = None
    decision: str
    reason_code: str
    reason_message: str
    matched_policy_id: str | None = None
    request_id: str
    correlation_id: str | None = None
    payload_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ToolPolicyHookContext(BaseModel):
    """Input passed to optional policy hooks after deterministic checks pass."""

    organization_id: str
    environment_id: str
    agent_id: str
    tool_id: str
    tool_name: str
    permission_id: str
    required_scope: str
    payload_summary: dict[str, Any]
    request_id: str
    correlation_id: str | None = None


class ToolPolicyHookResult(BaseModel):
    """Result returned by a simple Tool Gateway policy hook."""

    decision: str
    matched_policy_id: str | None = None
    reason_message: str | None = None

    @field_validator("decision")
    @classmethod
    def _validate_decision(cls, value: str) -> str:
        decision = value.strip().lower()
        if decision not in TOOL_POLICY_DECISIONS:
            supported = ", ".join(sorted(TOOL_POLICY_DECISIONS))
            raise ValueError(f"decision must be one of: {supported}.")
        return decision

    @field_validator("matched_policy_id", "reason_message")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ToolPolicyDecisionRepository:
    """Persistence for Tool Gateway policy decisions."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create_decision(self, body: ToolPolicyDecisionCreate) -> Row:
        """Persist a policy decision and return the stored row."""

        decision_id = generate_id("decision")
        self.connection.execute(
            """
            INSERT INTO tool_policy_decisions (
                id, organization_id, environment_id, agent_id, tool_id,
                permission_id, decision, reason_code, reason_message,
                matched_policy_id, request_id, correlation_id,
                payload_summary_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                self.organization_id,
                self.environment_id,
                body.agent_id,
                body.tool_id,
                body.permission_id,
                body.decision,
                body.reason_code,
                body.reason_message,
                body.matched_policy_id,
                body.request_id,
                body.correlation_id,
                json.dumps(body.payload_summary, sort_keys=True, separators=(",", ":")),
                utc_now_iso(),
            ),
        )
        row = self.get_decision(decision_id)
        if row is None:
            raise ValueError("Created tool policy decision could not be loaded.")
        return row

    def get_decision(self, decision_id: str) -> Row | None:
        """Get one decision in tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM tool_policy_decisions
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (decision_id, self.organization_id, self.environment_id),
        ).fetchone()


class ToolPolicyDecisionService:
    """Evaluate deterministic Tool Gateway policy decisions."""

    def __init__(
        self,
        connection: Connection,
        organization_id: str,
        environment_id: str,
        *,
        policy_hook: Any | None = None,
    ) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id
        self.policy_hook = policy_hook
        self.registry = ToolRegistryRepository(connection, organization_id, environment_id)
        self.decisions = ToolPolicyDecisionRepository(connection, organization_id, environment_id)

    def evaluate_tool_call(
        self,
        principal: GatewayPrincipal | None,
        tool_name: str,
        payload: dict[str, Any],
        *,
        request_id: str,
        correlation_id: str | None = None,
        now: str | None = None,
    ) -> ToolPolicyDecisionResult:
        """Evaluate and persist a fail-closed allow/deny decision."""

        payload_summary = summarize_tool_payload(payload)
        if (
            principal is None
            or not principal.agent_id
            or principal.organization_id != self.organization_id
            or principal.environment_id != self.environment_id
        ):
            return self._persist(
                agent_id=None,
                tool_id=None,
                permission_id=None,
                decision="deny",
                reason_code="agent_missing",
                matched_policy_id=None,
                request_id=request_id,
                correlation_id=correlation_id,
                payload_summary=payload_summary,
            )

        agent = self._get_agent(principal.agent_id)
        if agent is None:
            return self._persist(
                agent_id=None,
                tool_id=None,
                permission_id=None,
                decision="deny",
                reason_code="agent_missing",
                matched_policy_id=None,
                request_id=request_id,
                correlation_id=correlation_id,
                payload_summary=payload_summary,
            )
        if agent["status"] != "active":
            return self._persist(
                agent_id=agent["id"],
                tool_id=None,
                permission_id=None,
                decision="deny",
                reason_code="agent_inactive",
                matched_policy_id=None,
                request_id=request_id,
                correlation_id=correlation_id,
                payload_summary=payload_summary,
            )

        tool = self._get_tool_by_name_any_status(tool_name)
        if tool is None:
            return self._persist(
                agent_id=agent["id"],
                tool_id=None,
                permission_id=None,
                decision="deny",
                reason_code="tool_missing",
                matched_policy_id=None,
                request_id=request_id,
                correlation_id=correlation_id,
                payload_summary=payload_summary,
            )
        if tool["status"] != "active":
            return self._persist(
                agent_id=agent["id"],
                tool_id=tool["id"],
                permission_id=None,
                decision="deny",
                reason_code="tool_inactive",
                matched_policy_id=None,
                request_id=request_id,
                correlation_id=correlation_id,
                payload_summary=payload_summary,
            )

        required_scope = str(tool["required_scope"])
        permission = self.registry.find_active_agent_tool_permission(
            agent_id=agent["id"],
            tool_id=tool["id"],
            scope=required_scope,
            now=now,
        )
        if permission is None:
            active_any_scope = self.registry.find_active_agent_tool_permission(
                agent_id=agent["id"],
                tool_id=tool["id"],
                now=now,
            )
            if active_any_scope is None:
                return self._persist(
                    agent_id=agent["id"],
                    tool_id=tool["id"],
                    permission_id=None,
                    decision="deny",
                    reason_code="permission_missing",
                    matched_policy_id=None,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    payload_summary=payload_summary,
                )
            return self._persist(
                agent_id=agent["id"],
                tool_id=tool["id"],
                permission_id=active_any_scope["id"],
                decision="deny",
                reason_code="scope_insufficient",
                matched_policy_id=None,
                request_id=request_id,
                correlation_id=correlation_id,
                payload_summary=payload_summary,
            )
        if not principal.allows_tool_scope(
            required_scope,
            tool_id=str(tool["id"]),
            tool_name=str(tool["name"]),
        ):
            return self._persist(
                agent_id=agent["id"],
                tool_id=tool["id"],
                permission_id=permission["id"],
                decision="deny",
                reason_code="scope_insufficient",
                matched_policy_id=None,
                request_id=request_id,
                correlation_id=correlation_id,
                payload_summary=payload_summary,
            )

        if self.policy_hook is not None:
            context = ToolPolicyHookContext(
                organization_id=self.organization_id,
                environment_id=self.environment_id,
                agent_id=agent["id"],
                tool_id=tool["id"],
                tool_name=tool["name"],
                permission_id=permission["id"],
                required_scope=required_scope,
                payload_summary=payload_summary,
                request_id=request_id,
                correlation_id=correlation_id,
            )
            try:
                hook_result = ToolPolicyHookResult.model_validate(self.policy_hook.evaluate(context))
            except Exception:
                return self._persist(
                    agent_id=agent["id"],
                    tool_id=tool["id"],
                    permission_id=permission["id"],
                    decision="deny",
                    reason_code="policy_error",
                    matched_policy_id=None,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    payload_summary=payload_summary,
                )
            if hook_result.decision == "deny":
                return self._persist(
                    agent_id=agent["id"],
                    tool_id=tool["id"],
                    permission_id=permission["id"],
                    decision="deny",
                    reason_code="policy_denied",
                    matched_policy_id=hook_result.matched_policy_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    payload_summary=payload_summary,
                    reason_message=hook_result.reason_message,
                )
            return self._persist(
                agent_id=agent["id"],
                tool_id=tool["id"],
                permission_id=permission["id"],
                decision="allow",
                reason_code="allowed",
                matched_policy_id=hook_result.matched_policy_id,
                request_id=request_id,
                correlation_id=correlation_id,
                payload_summary=payload_summary,
                reason_message=hook_result.reason_message,
            )

        return self._persist(
            agent_id=agent["id"],
            tool_id=tool["id"],
            permission_id=permission["id"],
            decision="allow",
            reason_code="allowed",
            matched_policy_id=None,
            request_id=request_id,
            correlation_id=correlation_id,
            payload_summary=payload_summary,
        )

    def _get_agent(self, agent_id: str) -> Row | None:
        return self.connection.execute(
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

    def _get_tool_by_name_any_status(self, tool_name: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT *
            FROM tool_definitions
            WHERE organization_id = ?
              AND environment_id = ?
              AND lower(name) = lower(?)
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (self.organization_id, self.environment_id, tool_name),
        ).fetchone()

    def _persist(
        self,
        *,
        agent_id: str | None,
        tool_id: str | None,
        permission_id: str | None,
        decision: str,
        reason_code: str,
        matched_policy_id: str | None,
        request_id: str,
        correlation_id: str | None,
        payload_summary: dict[str, Any],
        reason_message: str | None = None,
    ) -> ToolPolicyDecisionResult:
        row = self.decisions.create_decision(
            ToolPolicyDecisionCreate(
                agent_id=agent_id,
                tool_id=tool_id,
                permission_id=permission_id,
                decision=decision,
                reason_code=reason_code,
                reason_message=reason_message or TOOL_POLICY_REASON_MESSAGES[reason_code],
                matched_policy_id=matched_policy_id,
                request_id=request_id,
                correlation_id=correlation_id,
                payload_summary=payload_summary,
            )
        )
        return tool_policy_decision_response(row)


def summarize_tool_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a deterministic, redacted payload summary for decision records."""

    summary = {
        str(key): _summarize_value(str(key), value, depth=0)
        for key, value in _sorted_limited_items(payload)
    }
    serialized = json.dumps(summary, sort_keys=True, default=str)
    if len(serialized) > MAX_PAYLOAD_SUMMARY_TOTAL_CHARS:
        return {"summary_truncated": True, "summary_excerpt": serialized[:MAX_PAYLOAD_SUMMARY_TOTAL_CHARS]}
    return summary


def tool_policy_decision_response(row: Row) -> ToolPolicyDecisionResult:
    """Serialize a persisted policy decision."""

    return ToolPolicyDecisionResult(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        agent_id=row["agent_id"],
        tool_id=row["tool_id"],
        permission_id=row["permission_id"],
        decision=row["decision"],
        reason_code=row["reason_code"],
        reason_message=row["reason_message"],
        matched_policy_id=row["matched_policy_id"],
        request_id=row["request_id"],
        correlation_id=row["correlation_id"],
        payload_summary=json.loads(row["payload_summary_json"]),
        created_at=row["created_at"],
    )


def _summarize_value(key: str, value: Any, *, depth: int) -> Any:
    if depth > MAX_PAYLOAD_SUMMARY_DEPTH:
        return "[truncated]"
    lowered_key = key.lower()
    if any(token in lowered_key for token in SECRET_LIKE_KEY_TOKENS):
        return REDACTED_PAYLOAD_VALUE
    if isinstance(value, dict):
        return {
            str(child_key): _summarize_value(str(child_key), child_value, depth=depth + 1)
            for child_key, child_value in _sorted_limited_items(value)
        }
    if isinstance(value, list):
        return [_summarize_value(key, item, depth=depth + 1) for item in value[:10]]
    if isinstance(value, str):
        if _looks_secret_like(value):
            return REDACTED_PAYLOAD_VALUE
        if len(value) > MAX_PAYLOAD_SUMMARY_STRING_LENGTH:
            return f"{value[:MAX_PAYLOAD_SUMMARY_STRING_LENGTH - 3]}..."
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _looks_secret_like(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_LIKE_VALUE_PATTERNS)


def _sorted_limited_items(value: dict[Any, Any]) -> list[tuple[Any, Any]]:
    return sorted(value.items(), key=lambda item: str(item[0]))[:MAX_PAYLOAD_SUMMARY_ITEMS]
