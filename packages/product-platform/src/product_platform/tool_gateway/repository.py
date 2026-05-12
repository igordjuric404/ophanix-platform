"""Tenant-scoped Tool Gateway registry persistence."""

from __future__ import annotations

import json
from product_platform.db.postgres import Connection, IntegrityError, Row
from typing import Any

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.tool_gateway.models import (
    SUPPORTED_AGENT_TOOL_PERMISSION_STATUSES,
    SUPPORTED_TOOL_STATUSES,
    AgentToolPermissionGrantRequest,
    AgentToolPermissionHistoryResponse,
    AgentToolPermissionPatchRequest,
    AgentToolPermissionResponse,
    GatewayToolDefinitionResponse,
    ToolDefinitionCreateRequest,
    ToolDefinitionPatchRequest,
    ToolDefinitionResponse,
    ToolDefinitionVersionResponse,
    ToolUpstreamHealthResponse,
    ToolUpstreamTargetCreateRequest,
    ToolUpstreamTargetPatchRequest,
    ToolUpstreamTargetResponse,
    ToolResponsePolicyPatchRequest,
    ToolResponsePolicyResponse,
    normalize_query_parameter_allowlist,
    validate_upstream_auth_configuration,
)
from product_platform.tool_gateway.schemas import validate_tool_contract_schema


DEFAULT_RESPONSE_REDACTION_RULES = {
    "redact_keys": [
        "address",
        "authorization",
        "api_key",
        "credential",
        "email",
        "password",
        "phone",
        "secret",
        "ssn",
        "token",
        "key",
    ],
    "redact_patterns": [
        r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}",
        r"(?i)\b(?:api[-_\s]?key|authorization|password|secret|token)\s*[:=]\s*['\"]?[^,'\"\s]{8,}",
        r"(?i)\b(?:ssn|social[-_\s]?security[-_\s]?number)\s*[:=]\s*['\"]?\d{3}-?\d{2}-?\d{4}\b",
    ],
}


class ToolDefinitionNotFoundError(ValueError):
    """Raised when a tool definition is not visible in tenant scope."""


class DuplicateToolNameError(ValueError):
    """Raised when an open tool name already exists in the environment."""


class ToolLifecycleError(ValueError):
    """Raised when a lifecycle transition is invalid."""


class ToolUpstreamTargetNotFoundError(ValueError):
    """Raised when an upstream target is not visible in tenant scope."""


class DuplicateToolUpstreamTargetError(ValueError):
    """Raised when a tool already has an active upstream target."""


class ToolUpstreamTargetValidationError(ValueError):
    """Raised when a target references an invalid tool or lifecycle state."""


class AgentToolPermissionNotFoundError(ValueError):
    """Raised when an agent-tool permission is not visible in tenant scope."""


class DuplicateAgentToolPermissionError(ValueError):
    """Raised when an active or paused agent-tool permission already exists."""


class AgentToolPermissionValidationError(ValueError):
    """Raised when an agent-tool permission references an invalid resource."""


class ToolRegistryRepository:
    """Persistence for tenant-scoped Tool Gateway tool definitions."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create_tool(self, body: ToolDefinitionCreateRequest, *, created_by: str) -> Row:
        """Create a tool definition and its initial version."""

        self._validate_contract_schemas(
            input_schema_json=body.input_schema_json,
            output_schema_json=body.output_schema_json,
        )
        tool_id = generate_id("tool")
        now = utc_now_iso()
        try:
            self.connection.execute(
                """
                INSERT INTO tool_definitions (
                    id, organization_id, environment_id, name, display_name,
                    description, owner_team, status, required_scope, input_schema_json,
                    output_schema_json, created_by, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tool_id,
                    self.organization_id,
                    self.environment_id,
                    body.name,
                    body.display_name,
                    body.description,
                    body.owner_team,
                    body.status,
                    body.required_scope,
                    _schema_to_json(body.input_schema_json),
                    _schema_to_json(body.output_schema_json),
                    created_by,
                    now,
                    now,
                ),
            )
        except IntegrityError as exc:
            raise DuplicateToolNameError("Tool name already exists in this environment.") from exc
        self._create_version(
            tool_id=tool_id,
            version=1,
            input_schema_json=body.input_schema_json,
            output_schema_json=body.output_schema_json,
            required_scope=body.required_scope,
            change_summary="initial tool contract",
            created_by=created_by,
            created_at=now,
        )
        self._create_default_response_policy(tool_id=tool_id, created_at=now)
        row = self.get_tool(tool_id)
        if row is None:
            raise ToolDefinitionNotFoundError("Created tool definition could not be loaded.")
        return row

    def get_response_policy(self, tool_id: str) -> Row | None:
        """Get response handling policy for a visible tool."""

        if self.get_tool(tool_id) is None:
            raise ToolDefinitionNotFoundError("Tool definition not found.")
        return self.connection.execute(
            """
            SELECT *
            FROM tool_response_policies
            WHERE tool_id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (tool_id, self.organization_id, self.environment_id),
        ).fetchone()

    def update_response_policy(self, tool_id: str, body: ToolResponsePolicyPatchRequest) -> Row:
        """Patch response handling policy for one visible tool."""

        existing = self.get_response_policy(tool_id)
        if existing is None:
            raise ToolDefinitionNotFoundError("Response policy not found.")
        fields: list[str] = []
        values: list[object] = []
        field_map = {
            "max_response_bytes": "max_response_bytes",
            "redaction_rules_json": "redaction_rules_json",
            "expose_to_agent": "expose_to_agent",
            "store_full_response": "store_full_response",
            "strict_output_validation": "strict_output_validation",
            "status": "status",
        }
        for model_field, column in field_map.items():
            if model_field in body.model_fields_set:
                value = getattr(body, model_field)
                if value is not None:
                    if model_field == "redaction_rules_json":
                        value = json.dumps(value, sort_keys=True, separators=(",", ":"))
                    if model_field in {"expose_to_agent", "store_full_response", "strict_output_validation"}:
                        value = 1 if value else 0
                    fields.append(f"{column} = ?")
                    values.append(value)
        if fields:
            fields.append("updated_at = ?")
            values.append(utc_now_iso())
            values.extend([tool_id, self.organization_id, self.environment_id])
            self.connection.execute(
                f"""
                UPDATE tool_response_policies
                SET {', '.join(fields)}
                WHERE tool_id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                values,
            )
        row = self.get_response_policy(tool_id)
        if row is None:
            raise ToolDefinitionNotFoundError("Response policy not found.")
        return row

    def get_tool(self, tool_id: str) -> Row | None:
        """Get one tool definition in tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM tool_definitions
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (tool_id, self.organization_id, self.environment_id),
        ).fetchone()

    def get_tool_by_name(self, name: str, *, active_only: bool = False) -> Row | None:
        """Resolve a tool by stable name in tenant scope."""

        clauses = [
            "organization_id = ?",
            "environment_id = ?",
            "lower(name) = lower(?)",
        ]
        values: list[object] = [self.organization_id, self.environment_id, name]
        if active_only:
            clauses.append("status = 'active'")
        else:
            clauses.append("status != 'retired'")
        return self.connection.execute(
            f"""
            SELECT *
            FROM tool_definitions
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            values,
        ).fetchone()

    def list_tools(
        self,
        *,
        status: str | None = None,
        owner_team: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List tool definitions in tenant scope."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if status:
            normalized_status = status.strip().lower()
            if normalized_status not in SUPPORTED_TOOL_STATUSES:
                supported = ", ".join(sorted(SUPPORTED_TOOL_STATUSES))
                raise ValueError(f"status must be one of: {supported}.")
            clauses.append("status = ?")
            values.append(normalized_status)
        if owner_team:
            clauses.append("owner_team = ?")
            values.append(owner_team.strip())
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT *
            FROM tool_definitions
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def list_tools_for_gateway_principal(
        self,
        *,
        agent_id: str,
        credential_id: str,
        owner_team: str | None = None,
        limit: int = 50,
        offset: int = 0,
        now: str | None = None,
    ) -> list[Row]:
        """List active tools callable by one authenticated gateway principal."""

        normalized_agent_id = agent_id.strip()
        if not normalized_agent_id:
            return []
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset must be greater than or equal to zero")
        normalized_credential_id = credential_id.strip()
        if not normalized_credential_id:
            return []
        comparison_time = now or utc_now_iso()
        clauses = [
            "d.organization_id = ?",
            "d.environment_id = ?",
            "d.status = 'active'",
            "p.agent_id = ?",
            "p.status = 'active'",
            "(p.expires_at IS NULL OR p.expires_at > ?)",
            "p.scope = d.required_scope",
            """
            EXISTS (
                SELECT 1
                FROM credential_scopes s
                WHERE s.credential_id = ?
                  AND s.scope = d.required_scope
                  AND s.resource_type = 'tool'
                  AND (
                    s.resource_id IS NULL
                    OR s.resource_id = d.id
                    OR lower(s.resource_id) = lower(d.name)
                  )
            )
            """,
        ]
        values: list[object] = [
            self.organization_id,
            self.environment_id,
            normalized_agent_id,
            comparison_time,
            normalized_credential_id,
        ]
        if owner_team:
            clauses.append("d.owner_team = ?")
            values.append(owner_team.strip())
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT d.*
            FROM tool_definitions d
            JOIN agent_tool_permissions p
              ON p.organization_id = d.organization_id
             AND p.environment_id = d.environment_id
             AND p.tool_id = d.id
            WHERE {' AND '.join(clauses)}
            ORDER BY d.updated_at DESC, d.id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def list_tools_for_gateway_principal_cursor(
        self,
        *,
        agent_id: str,
        credential_id: str,
        owner_team: str | None = None,
        limit: int = 50,
        snapshot_before: str,
        last_updated_at: str | None = None,
        last_id: str | None = None,
        now: str | None = None,
    ) -> list[Row]:
        """List active callable tools using stable snapshot/keyset pagination."""

        normalized_agent_id = agent_id.strip()
        normalized_credential_id = credential_id.strip()
        if not normalized_agent_id or not normalized_credential_id:
            return []
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if (last_updated_at is None) != (last_id is None):
            raise ValueError("last_updated_at and last_id must be provided together")
        comparison_time = now or utc_now_iso()
        clauses = [
            "d.organization_id = ?",
            "d.environment_id = ?",
            "d.status = 'active'",
            "d.updated_at <= ?",
            "p.agent_id = ?",
            "p.status = 'active'",
            "(p.expires_at IS NULL OR p.expires_at > ?)",
            "p.scope = d.required_scope",
            """
            EXISTS (
                SELECT 1
                FROM credential_scopes s
                WHERE s.credential_id = ?
                  AND s.scope = d.required_scope
                  AND s.resource_type = 'tool'
                  AND (
                    s.resource_id IS NULL
                    OR s.resource_id = d.id
                    OR lower(s.resource_id) = lower(d.name)
                  )
            )
            """,
        ]
        values: list[object] = [
            self.organization_id,
            self.environment_id,
            snapshot_before,
            normalized_agent_id,
            comparison_time,
            normalized_credential_id,
        ]
        if owner_team:
            clauses.append("d.owner_team = ?")
            values.append(owner_team.strip())
        if last_updated_at is not None and last_id is not None:
            clauses.append("(d.updated_at < ? OR (d.updated_at = ? AND d.id < ?))")
            values.extend([last_updated_at, last_updated_at, last_id])
        values.append(limit)
        return self.connection.execute(
            f"""
            SELECT d.*
            FROM tool_definitions d
            JOIN agent_tool_permissions p
              ON p.organization_id = d.organization_id
             AND p.environment_id = d.environment_id
             AND p.tool_id = d.id
            WHERE {' AND '.join(clauses)}
            ORDER BY d.updated_at DESC, d.id DESC
            LIMIT ?
            """,
            values,
        ).fetchall()

    def update_tool(
        self,
        tool_id: str,
        body: ToolDefinitionPatchRequest,
        *,
        updated_by: str,
    ) -> Row:
        """Patch a tool definition and create a version when contract fields change."""

        existing = self.get_tool(tool_id)
        if existing is None:
            raise ToolDefinitionNotFoundError("Tool definition not found.")
        self._validate_contract_schemas(
            input_schema_json=body.input_schema_json
            if "input_schema_json" in body.model_fields_set
            else None,
            output_schema_json=body.output_schema_json
            if "output_schema_json" in body.model_fields_set
            else None,
        )

        fields: list[str] = []
        values: list[object | None] = []
        version_input_schema = _schema_from_json(existing["input_schema_json"])
        version_output_schema = _schema_from_json(existing["output_schema_json"])
        version_required_scope = str(existing["required_scope"])
        contract_changed = False

        for column in ["display_name", "description", "owner_team"]:
            if column in body.model_fields_set:
                fields.append(f"{column} = ?")
                values.append(getattr(body, column))
        if "required_scope" in body.model_fields_set and body.required_scope is not None:
            fields.append("required_scope = ?")
            values.append(body.required_scope)
            if body.required_scope != existing["required_scope"]:
                contract_changed = True
                version_required_scope = body.required_scope
        if "input_schema_json" in body.model_fields_set:
            fields.append("input_schema_json = ?")
            values.append(_schema_to_json(body.input_schema_json))
            new_json = _schema_to_json(body.input_schema_json)
            if new_json != existing["input_schema_json"]:
                contract_changed = True
                version_input_schema = body.input_schema_json
        if "output_schema_json" in body.model_fields_set:
            fields.append("output_schema_json = ?")
            values.append(_schema_to_json(body.output_schema_json))
            new_json = _schema_to_json(body.output_schema_json)
            if new_json != existing["output_schema_json"]:
                contract_changed = True
                version_output_schema = body.output_schema_json

        if fields:
            fields.append("updated_at = ?")
            values.append(utc_now_iso())
            values.extend([tool_id, self.organization_id, self.environment_id])
            self.connection.execute(
                f"""
                UPDATE tool_definitions
                SET {', '.join(fields)}
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                values,
            )
        if contract_changed:
            self._create_version(
                tool_id=tool_id,
                version=self._next_version(tool_id),
                input_schema_json=version_input_schema,
                output_schema_json=version_output_schema,
                required_scope=version_required_scope,
                change_summary=body.change_summary or "tool contract updated",
                created_by=updated_by,
                created_at=utc_now_iso(),
            )
        row = self.get_tool(tool_id)
        if row is None:
            raise ToolDefinitionNotFoundError("Tool definition not found.")
        return row

    def activate_tool(
        self,
        tool_id: str,
        *,
        actor_id: str,
        reason: str | None = None,
    ) -> Row:
        """Activate a draft or disabled tool after validating its schemas."""

        existing = self.get_tool(tool_id)
        if existing is None:
            raise ToolDefinitionNotFoundError("Tool definition not found.")
        input_schema = _schema_from_json(existing["input_schema_json"])
        output_schema = _schema_from_json(existing["output_schema_json"])
        if input_schema is None:
            raise ToolLifecycleError("Input schema is required before activation.")
        self._validate_contract_schemas(
            input_schema_json=input_schema,
            output_schema_json=output_schema,
        )
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE tool_definitions
            SET status = ?, updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            ("active", now, tool_id, self.organization_id, self.environment_id),
        )
        row = self.get_tool(tool_id)
        if row is None:
            raise ToolDefinitionNotFoundError("Tool definition not found.")
        return row

    def disable_tool(
        self,
        tool_id: str,
        *,
        actor_id: str,
        reason: str | None = None,
    ) -> Row:
        """Disable a tool without deleting its version history."""

        if self.get_tool(tool_id) is None:
            raise ToolDefinitionNotFoundError("Tool definition not found.")
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE tool_definitions
            SET status = ?, updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            ("disabled", now, tool_id, self.organization_id, self.environment_id),
        )
        row = self.get_tool(tool_id)
        if row is None:
            raise ToolDefinitionNotFoundError("Tool definition not found.")
        return row

    def list_versions(self, tool_id: str) -> list[Row]:
        """List tool contract versions for one visible tool."""

        if self.get_tool(tool_id) is None:
            raise ToolDefinitionNotFoundError("Tool definition not found.")
        return self.connection.execute(
            """
            SELECT *
            FROM tool_definition_versions
            WHERE tool_id = ?
            ORDER BY version DESC, id DESC
            """,
            (tool_id,),
        ).fetchall()

    def latest_version(self, tool_id: str) -> Row | None:
        """Return the newest version for a visible tool."""

        if self.get_tool(tool_id) is None:
            raise ToolDefinitionNotFoundError("Tool definition not found.")
        return self.connection.execute(
            """
            SELECT *
            FROM tool_definition_versions
            WHERE tool_id = ?
            ORDER BY version DESC, id DESC
            LIMIT 1
            """,
            (tool_id,),
        ).fetchone()

    def _create_version(
        self,
        *,
        tool_id: str,
        version: int,
        input_schema_json: dict[str, Any] | None,
        output_schema_json: dict[str, Any] | None,
        required_scope: str,
        change_summary: str,
        created_by: str,
        created_at: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO tool_definition_versions (
                id, tool_id, version, input_schema_json, output_schema_json,
                required_scope, change_summary, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generate_id("toolv"),
                tool_id,
                version,
                _schema_to_json(input_schema_json),
                _schema_to_json(output_schema_json),
                required_scope,
                change_summary,
                created_by,
                created_at,
            ),
        )

    def _create_default_response_policy(self, *, tool_id: str, created_at: str) -> None:
        self.connection.execute(
            """
            INSERT INTO tool_response_policies (
                id, organization_id, environment_id, tool_id, max_response_bytes,
                redaction_rules_json, expose_to_agent, store_full_response,
                strict_output_validation, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            (
                generate_id("toolresp"),
                self.organization_id,
                self.environment_id,
                tool_id,
                32_768,
                json.dumps(DEFAULT_RESPONSE_REDACTION_RULES, sort_keys=True, separators=(",", ":")),
                1,
                0,
                1,
                "active",
                created_at,
                created_at,
            ),
        )

    def _next_version(self, tool_id: str) -> int:
        row = self.connection.execute(
            """
            SELECT COALESCE(MAX(version), 0) + 1 AS next_version
            FROM tool_definition_versions
            WHERE tool_id = ?
            """,
            (tool_id,),
        ).fetchone()
        return int(row["next_version"])

    def _validate_contract_schemas(
        self,
        *,
        input_schema_json: dict[str, Any] | None,
        output_schema_json: dict[str, Any] | None,
    ) -> None:
        validate_tool_contract_schema(input_schema_json, field="input_schema_json")
        validate_tool_contract_schema(output_schema_json, field="output_schema_json")

    def create_upstream_target(
        self,
        tool_id: str,
        body: ToolUpstreamTargetCreateRequest,
    ) -> Row:
        """Create an upstream target and default health-check configuration."""

        tool = self.get_tool(tool_id)
        if tool is None:
            raise ToolDefinitionNotFoundError("Tool definition not found.")
        if tool["status"] in {"disabled", "retired"}:
            raise ToolUpstreamTargetValidationError("Cannot create upstream target for disabled or retired tool.")
        validate_upstream_auth_configuration(body.auth_mode, body.auth_config_json)
        target_id = generate_id("target")
        now = utc_now_iso()
        try:
            self.connection.execute(
                """
                INSERT INTO tool_upstream_targets (
                    id, organization_id, environment_id, tool_id, base_url,
                    path_template, method, auth_mode, auth_config_json, timeout_ms,
                    status, query_parameter_allowlist_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_id,
                    self.organization_id,
                    self.environment_id,
                    tool_id,
                    body.base_url,
                    body.path_template,
                    body.method,
                    body.auth_mode,
                    _auth_config_to_json(body.auth_config_json),
                    body.timeout_ms,
                    body.status,
                    _query_allowlist_to_json(body.query_parameter_allowlist),
                    now,
                    now,
                ),
            )
        except IntegrityError as exc:
            raise DuplicateToolUpstreamTargetError("Tool already has an active upstream target.") from exc
        self.connection.execute(
            """
            INSERT INTO tool_upstream_health_checks (
                id, target_id, health_url, expected_status, interval_seconds,
                last_status, last_checked_at, last_error, enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generate_id("targethc"),
                target_id,
                body.health_url or f"{body.base_url}/health",
                body.expected_status,
                body.interval_seconds,
                None,
                None,
                None,
                1 if body.health_enabled else 0,
            ),
        )
        row = self.get_upstream_target(target_id)
        if row is None:
            raise ToolUpstreamTargetNotFoundError("Created upstream target could not be loaded.")
        return row

    def get_upstream_target(self, target_id: str) -> Row | None:
        """Get one upstream target in tenant scope."""

        return self.connection.execute(
            """
            SELECT
                t.*,
                d.name AS tool_name
            FROM tool_upstream_targets t
            JOIN tool_definitions d ON d.id = t.tool_id
            WHERE t.id = ?
              AND t.organization_id = ?
              AND t.environment_id = ?
              AND d.organization_id = ?
              AND d.environment_id = ?
            """,
            (
                target_id,
                self.organization_id,
                self.environment_id,
                self.organization_id,
                self.environment_id,
            ),
        ).fetchone()

    def get_upstream_target_for_tool(self, tool_id: str) -> Row | None:
        """Return the active/configured target for one visible tool."""

        return self.connection.execute(
            """
            SELECT
                t.*,
                d.name AS tool_name
            FROM tool_upstream_targets t
            JOIN tool_definitions d ON d.id = t.tool_id
            WHERE t.tool_id = ?
              AND t.organization_id = ?
              AND t.environment_id = ?
              AND t.status IN ('configured', 'healthy', 'degraded', 'unhealthy')
              AND d.organization_id = ?
              AND d.environment_id = ?
            ORDER BY t.updated_at DESC, t.id DESC
            LIMIT 1
            """,
            (
                tool_id,
                self.organization_id,
                self.environment_id,
                self.organization_id,
                self.environment_id,
            ),
        ).fetchone()

    def resolve_upstream_target_by_tool_name(self, tool_name: str) -> Row | None:
        """Resolve an active tool's upstream target by stable tool name."""

        tool = self.get_tool_by_name(tool_name, active_only=True)
        if tool is None:
            return None
        return self.get_upstream_target_for_tool(tool["id"])

    def update_upstream_target(
        self,
        target_id: str,
        body: ToolUpstreamTargetPatchRequest,
    ) -> Row:
        """Patch upstream target settings and health-check configuration."""

        existing = self.get_upstream_target(target_id)
        if existing is None:
            raise ToolUpstreamTargetNotFoundError("Upstream target not found.")
        effective_auth_mode = (
            body.auth_mode
            if "auth_mode" in body.model_fields_set and body.auth_mode is not None
            else str(existing["auth_mode"])
        )
        if "auth_config_json" in body.model_fields_set:
            effective_auth_config = body.auth_config_json
        elif "auth_mode" in body.model_fields_set and effective_auth_mode == "none":
            effective_auth_config = None
        else:
            effective_auth_config = _auth_config_from_json(existing["auth_config_json"])
        validate_upstream_auth_configuration(effective_auth_mode, effective_auth_config)
        target_fields: list[str] = []
        target_values: list[object | None] = []
        for column in ["base_url", "path_template", "method", "auth_mode", "timeout_ms", "status"]:
            if column in body.model_fields_set:
                value = getattr(body, column)
                if value is not None:
                    target_fields.append(f"{column} = ?")
                    target_values.append(value)
        if "auth_config_json" in body.model_fields_set:
            target_fields.append("auth_config_json = ?")
            target_values.append(_auth_config_to_json(effective_auth_config))
        elif "auth_mode" in body.model_fields_set and effective_auth_mode == "none":
            target_fields.append("auth_config_json = ?")
            target_values.append(None)
        if "query_parameter_allowlist" in body.model_fields_set:
            target_fields.append("query_parameter_allowlist_json = ?")
            target_values.append(_query_allowlist_to_json(body.query_parameter_allowlist or []))
        if target_fields:
            target_fields.append("updated_at = ?")
            target_values.append(utc_now_iso())
            target_values.extend([target_id, self.organization_id, self.environment_id])
            try:
                self.connection.execute(
                    f"""
                    UPDATE tool_upstream_targets
                    SET {', '.join(target_fields)}
                    WHERE id = ?
                      AND organization_id = ?
                      AND environment_id = ?
                    """,
                    target_values,
                )
            except IntegrityError as exc:
                raise DuplicateToolUpstreamTargetError(
                    "Tool already has an active upstream target."
                ) from exc
        health_fields: list[str] = []
        health_values: list[object | None] = []
        health_field_map = {
            "health_url": "health_url",
            "expected_status": "expected_status",
            "interval_seconds": "interval_seconds",
            "health_enabled": "enabled",
        }
        for model_field, column in health_field_map.items():
            if model_field in body.model_fields_set:
                value = getattr(body, model_field)
                if model_field == "health_enabled" and value is not None:
                    value = 1 if value else 0
                if value is not None:
                    health_fields.append(f"{column} = ?")
                    health_values.append(value)
        if health_fields:
            health_values.append(target_id)
            self.connection.execute(
                f"""
                UPDATE tool_upstream_health_checks
                SET {', '.join(health_fields)}
                WHERE target_id = ?
                """,
                health_values,
            )
        row = self.get_upstream_target(target_id)
        if row is None:
            raise ToolUpstreamTargetNotFoundError("Upstream target not found.")
        return row

    def get_upstream_health(self, target_id: str) -> Row | None:
        """Get health-check state for one visible upstream target."""

        if self.get_upstream_target(target_id) is None:
            return None
        return self.connection.execute(
            """
            SELECT *
            FROM tool_upstream_health_checks
            WHERE target_id = ?
            """,
            (target_id,),
        ).fetchone()

    def record_upstream_health(
        self,
        target_id: str,
        *,
        status: str,
        checked_at: str,
        error: str | None,
    ) -> Row:
        """Persist a health check result and mirror status on the target."""

        if self.get_upstream_target(target_id) is None:
            raise ToolUpstreamTargetNotFoundError("Upstream target not found.")
        self.connection.execute(
            """
            UPDATE tool_upstream_health_checks
            SET last_status = ?, last_checked_at = ?, last_error = ?
            WHERE target_id = ?
            """,
            (status, checked_at, error, target_id),
        )
        self.connection.execute(
            """
            UPDATE tool_upstream_targets
            SET status = ?, updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (status, checked_at, target_id, self.organization_id, self.environment_id),
        )
        row = self.get_upstream_health(target_id)
        if row is None:
            raise ToolUpstreamTargetNotFoundError("Upstream health not found.")
        return row

    def grant_agent_tool_permission(
        self,
        agent_id: str,
        body: AgentToolPermissionGrantRequest,
        *,
        granted_by: str,
    ) -> Row:
        """Grant an active agent access to an active tool."""

        self._require_active_agent(agent_id)
        self._require_active_tool(body.tool_id)
        permission_id = generate_id("agtperm")
        now = utc_now_iso()
        try:
            self.connection.execute(
                """
                INSERT INTO agent_tool_permissions (
                    id, organization_id, environment_id, agent_id, tool_id, scope,
                    status, granted_by, granted_reason, granted_at, expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    permission_id,
                    self.organization_id,
                    self.environment_id,
                    agent_id,
                    body.tool_id,
                    body.scope,
                    "active",
                    granted_by,
                    body.granted_reason or "",
                    now,
                    body.expires_at,
                ),
            )
        except IntegrityError as exc:
            raise DuplicateAgentToolPermissionError(
                "Agent already has an active permission for this tool."
            ) from exc
        self._record_agent_tool_permission_history(
            permission_id=permission_id,
            action="granted",
            actor_user_id=granted_by,
            reason=body.granted_reason or None,
            previous_status=None,
            new_status="active",
            created_at=now,
        )
        row = self.get_agent_tool_permission(permission_id)
        if row is None:
            raise AgentToolPermissionNotFoundError("Created agent-tool permission could not be loaded.")
        return row

    def get_agent_tool_permission(self, permission_id: str) -> Row | None:
        """Get one agent-tool permission in tenant scope."""

        return self.connection.execute(
            """
            SELECT
                p.*,
                a.name AS agent_name,
                a.status AS agent_status,
                d.name AS tool_name,
                d.display_name AS tool_display_name,
                d.status AS tool_status
            FROM agent_tool_permissions p
            JOIN agents a ON a.id = p.agent_id
                AND a.organization_id = p.organization_id
                AND a.environment_id = p.environment_id
            JOIN tool_definitions d ON d.id = p.tool_id
                AND d.organization_id = p.organization_id
                AND d.environment_id = p.environment_id
            WHERE p.id = ?
              AND p.organization_id = ?
              AND p.environment_id = ?
            """,
            (permission_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_agent_tool_permissions(
        self,
        *,
        agent_id: str | None = None,
        tool_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List agent-tool permissions with agent and tool metadata."""

        clauses = ["p.organization_id = ?", "p.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if agent_id is not None:
            clauses.append("p.agent_id = ?")
            values.append(agent_id)
        if tool_id is not None:
            clauses.append("p.tool_id = ?")
            values.append(tool_id)
        if status is not None:
            normalized_status = status.strip().lower()
            if normalized_status not in SUPPORTED_AGENT_TOOL_PERMISSION_STATUSES:
                supported = ", ".join(sorted(SUPPORTED_AGENT_TOOL_PERMISSION_STATUSES))
                raise ValueError(f"status must be one of: {supported}.")
            clauses.append("p.status = ?")
            values.append(normalized_status)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT
                p.*,
                a.name AS agent_name,
                a.status AS agent_status,
                d.name AS tool_name,
                d.display_name AS tool_display_name,
                d.status AS tool_status
            FROM agent_tool_permissions p
            JOIN agents a ON a.id = p.agent_id
                AND a.organization_id = p.organization_id
                AND a.environment_id = p.environment_id
            JOIN tool_definitions d ON d.id = p.tool_id
                AND d.organization_id = p.organization_id
                AND d.environment_id = p.environment_id
            WHERE {' AND '.join(clauses)}
            ORDER BY p.granted_at DESC, p.id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def find_active_agent_tool_permission(
        self,
        *,
        agent_id: str,
        tool_id: str,
        scope: str | None = None,
        now: str | None = None,
    ) -> Row | None:
        """Find an active, unexpired permission for policy decisions."""

        comparison_time = now or utc_now_iso()
        clauses = [
            "p.organization_id = ?",
            "p.environment_id = ?",
            "p.agent_id = ?",
            "p.tool_id = ?",
            "p.status = 'active'",
            "(p.expires_at IS NULL OR p.expires_at > ?)",
        ]
        values: list[object] = [
            self.organization_id,
            self.environment_id,
            agent_id,
            tool_id,
            comparison_time,
        ]
        if scope is not None:
            clauses.append("p.scope = ?")
            values.append(scope)
        return self.connection.execute(
            f"""
            SELECT
                p.*,
                a.name AS agent_name,
                a.status AS agent_status,
                d.name AS tool_name,
                d.display_name AS tool_display_name,
                d.status AS tool_status
            FROM agent_tool_permissions p
            JOIN agents a ON a.id = p.agent_id
                AND a.organization_id = p.organization_id
                AND a.environment_id = p.environment_id
            JOIN tool_definitions d ON d.id = p.tool_id
                AND d.organization_id = p.organization_id
                AND d.environment_id = p.environment_id
            WHERE {' AND '.join(clauses)}
            ORDER BY p.granted_at DESC, p.id DESC
            LIMIT 1
            """,
            values,
        ).fetchone()

    def update_agent_tool_permission(
        self,
        permission_id: str,
        body: AgentToolPermissionPatchRequest,
        *,
        actor_id: str,
    ) -> Row:
        """Patch mutable permission fields and record history."""

        existing = self.get_agent_tool_permission(permission_id)
        if existing is None:
            raise AgentToolPermissionNotFoundError("Agent-tool permission not found.")
        fields: list[str] = []
        values: list[object | None] = []
        for column in ["scope", "expires_at"]:
            if column in body.model_fields_set:
                fields.append(f"{column} = ?")
                values.append(getattr(body, column))
        if fields:
            values.append(permission_id)
            values.extend([self.organization_id, self.environment_id])
            self.connection.execute(
                f"""
                UPDATE agent_tool_permissions
                SET {', '.join(fields)}
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                values,
            )
            self._record_agent_tool_permission_history(
                permission_id=permission_id,
                action="updated",
                actor_user_id=actor_id,
                reason=None,
                previous_status=existing["status"],
                new_status=existing["status"],
                created_at=utc_now_iso(),
            )
        row = self.get_agent_tool_permission(permission_id)
        if row is None:
            raise AgentToolPermissionNotFoundError("Agent-tool permission not found.")
        return row

    def pause_agent_tool_permission(
        self,
        permission_id: str,
        *,
        actor_id: str,
        reason: str,
    ) -> Row:
        """Pause an active permission without permanently revoking it."""

        return self._transition_agent_tool_permission(
            permission_id,
            action="paused",
            new_status="paused",
            actor_id=actor_id,
            reason=reason,
        )

    def revoke_agent_tool_permission(
        self,
        permission_id: str,
        *,
        actor_id: str,
        reason: str,
    ) -> Row:
        """Revoke an agent-tool permission permanently."""

        existing = self.get_agent_tool_permission(permission_id)
        if existing is None:
            raise AgentToolPermissionNotFoundError("Agent-tool permission not found.")
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE agent_tool_permissions
            SET status = ?, revoked_by = ?, revoked_reason = ?, revoked_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (
                "revoked",
                actor_id,
                reason,
                now,
                permission_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        self._record_agent_tool_permission_history(
            permission_id=permission_id,
            action="revoked",
            actor_user_id=actor_id,
            reason=reason,
            previous_status=existing["status"],
            new_status="revoked",
            created_at=now,
        )
        row = self.get_agent_tool_permission(permission_id)
        if row is None:
            raise AgentToolPermissionNotFoundError("Agent-tool permission not found.")
        return row

    def list_agent_tool_permission_history(self, permission_id: str) -> list[Row]:
        """List lifecycle history for one visible permission."""

        if self.get_agent_tool_permission(permission_id) is None:
            raise AgentToolPermissionNotFoundError("Agent-tool permission not found.")
        return self.connection.execute(
            """
            SELECT *
            FROM agent_tool_permission_history
            WHERE permission_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (permission_id,),
        ).fetchall()

    def mark_expired_agent_tool_permissions(self, *, now: str | None = None) -> int:
        """Mark stale active or paused permissions as expired."""

        comparison_time = now or utc_now_iso()
        rows = self.connection.execute(
            """
            SELECT id, status, expires_at
            FROM agent_tool_permissions
            WHERE organization_id = ?
              AND environment_id = ?
              AND status IN ('active', 'paused')
              AND expires_at IS NOT NULL
              AND expires_at <= ?
            ORDER BY expires_at ASC, id ASC
            """,
            (self.organization_id, self.environment_id, comparison_time),
        ).fetchall()
        for row in rows:
            marked_at = utc_now_iso()
            self.connection.execute(
                """
                UPDATE agent_tool_permissions
                SET status = ?
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                ("expired", row["id"], self.organization_id, self.environment_id),
            )
            self._record_agent_tool_permission_history(
                permission_id=row["id"],
                action="expired",
                actor_user_id="system",
                reason=f"Permission expired at {row['expires_at']}.",
                previous_status=row["status"],
                new_status="expired",
                created_at=marked_at,
            )
        return len(rows)

    def _transition_agent_tool_permission(
        self,
        permission_id: str,
        *,
        action: str,
        new_status: str,
        actor_id: str,
        reason: str,
    ) -> Row:
        existing = self.get_agent_tool_permission(permission_id)
        if existing is None:
            raise AgentToolPermissionNotFoundError("Agent-tool permission not found.")
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE agent_tool_permissions
            SET status = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (new_status, permission_id, self.organization_id, self.environment_id),
        )
        self._record_agent_tool_permission_history(
            permission_id=permission_id,
            action=action,
            actor_user_id=actor_id,
            reason=reason,
            previous_status=existing["status"],
            new_status=new_status,
            created_at=now,
        )
        row = self.get_agent_tool_permission(permission_id)
        if row is None:
            raise AgentToolPermissionNotFoundError("Agent-tool permission not found.")
        return row

    def _require_active_agent(self, agent_id: str) -> Row:
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
            raise AgentToolPermissionValidationError("Permission grants require a visible active agent.")
        if row["status"] != "active":
            raise AgentToolPermissionValidationError("Permission grants require an active agent.")
        return row

    def _require_active_tool(self, tool_id: str) -> Row:
        row = self.get_tool(tool_id)
        if row is None:
            raise AgentToolPermissionValidationError("Permission grants require a visible active tool.")
        if row["status"] != "active":
            raise AgentToolPermissionValidationError("Permission grants require an active tool.")
        return row

    def _record_agent_tool_permission_history(
        self,
        *,
        permission_id: str,
        action: str,
        actor_user_id: str,
        reason: str | None,
        previous_status: str | None,
        new_status: str,
        created_at: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO agent_tool_permission_history (
                id, permission_id, action, actor_user_id, reason,
                previous_status, new_status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generate_id("agtpermhist"),
                permission_id,
                action,
                actor_user_id,
                reason,
                previous_status,
                new_status,
                created_at,
            ),
        )


def tool_definition_version_response(row: Row) -> ToolDefinitionVersionResponse:
    """Serialize a persisted tool definition version."""

    return ToolDefinitionVersionResponse(
        id=row["id"],
        tool_id=row["tool_id"],
        version=int(row["version"]),
        input_schema_json=_schema_from_json(row["input_schema_json"]),
        output_schema_json=_schema_from_json(row["output_schema_json"]),
        required_scope=row["required_scope"],
        change_summary=row["change_summary"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def tool_definition_response(
    repository: ToolRegistryRepository,
    row: Row,
    *,
    include_versions: bool = False,
) -> ToolDefinitionResponse:
    """Serialize a persisted tool definition."""

    latest_row = repository.latest_version(row["id"])
    return ToolDefinitionResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        name=row["name"],
        display_name=row["display_name"],
        description=row["description"],
        owner_team=row["owner_team"],
        status=row["status"],
        required_scope=row["required_scope"],
        input_schema_json=_schema_from_json(row["input_schema_json"]),
        output_schema_json=_schema_from_json(row["output_schema_json"]),
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        latest_version=tool_definition_version_response(latest_row) if latest_row else None,
        versions=[
            tool_definition_version_response(version)
            for version in (repository.list_versions(row["id"]) if include_versions else [])
        ],
    )


def gateway_tool_definition_response(row: Row) -> GatewayToolDefinitionResponse:
    """Serialize a tool definition for authenticated agent discovery."""

    return GatewayToolDefinitionResponse(
        id=row["id"],
        name=row["name"],
        display_name=row["display_name"],
        description=row["description"],
        owner_team=row["owner_team"],
        status=row["status"],
        required_scope=row["required_scope"],
        input_schema_json=_schema_from_json(row["input_schema_json"]),
        output_schema_json=_schema_from_json(row["output_schema_json"]),
    )


def tool_upstream_health_response(row: Row) -> ToolUpstreamHealthResponse:
    """Serialize upstream health-check state."""

    return ToolUpstreamHealthResponse(
        id=row["id"],
        target_id=row["target_id"],
        health_url=row["health_url"],
        expected_status=int(row["expected_status"]),
        interval_seconds=int(row["interval_seconds"]),
        last_status=row["last_status"],
        last_checked_at=row["last_checked_at"],
        last_error=row["last_error"],
        enabled=bool(row["enabled"]),
    )


def tool_upstream_target_response(
    repository: ToolRegistryRepository,
    row: Row,
) -> ToolUpstreamTargetResponse:
    """Serialize upstream target settings with health state."""

    health = repository.get_upstream_health(row["id"])
    return ToolUpstreamTargetResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        tool_id=row["tool_id"],
        tool_name=row["tool_name"],
        base_url=row["base_url"],
        path_template=row["path_template"],
        method=row["method"],
        auth_mode=row["auth_mode"],
        timeout_ms=int(row["timeout_ms"]),
        status=row["status"],
        query_parameter_allowlist=_query_allowlist_from_json(
            row["query_parameter_allowlist_json"]
            if "query_parameter_allowlist_json" in row.keys()
            else None
        ),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        health=tool_upstream_health_response(health) if health is not None else None,
    )


def agent_tool_permission_history_response(row: Row) -> AgentToolPermissionHistoryResponse:
    """Serialize a persisted permission history entry."""

    return AgentToolPermissionHistoryResponse(
        id=row["id"],
        permission_id=row["permission_id"],
        action=row["action"],
        actor_user_id=row["actor_user_id"],
        reason=row["reason"],
        previous_status=row["previous_status"],
        new_status=row["new_status"],
        created_at=row["created_at"],
    )


def agent_tool_permission_response(row: Row) -> AgentToolPermissionResponse:
    """Serialize a persisted agent-tool permission."""

    return AgentToolPermissionResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        agent_id=row["agent_id"],
        agent_name=row["agent_name"],
        tool_id=row["tool_id"],
        tool_name=row["tool_name"],
        tool_display_name=row["tool_display_name"],
        scope=row["scope"],
        status=row["status"],
        granted_by=row["granted_by"],
        granted_reason=row["granted_reason"],
        granted_at=row["granted_at"],
        revoked_by=row["revoked_by"],
        revoked_reason=row["revoked_reason"],
        revoked_at=row["revoked_at"],
        expires_at=row["expires_at"],
    )


def tool_response_policy_response(row: Row) -> ToolResponsePolicyResponse:
    """Serialize a tool response handling policy."""

    return ToolResponsePolicyResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        tool_id=row["tool_id"],
        max_response_bytes=int(row["max_response_bytes"]),
        redaction_rules_json=json.loads(row["redaction_rules_json"]),
        expose_to_agent=bool(row["expose_to_agent"]),
        store_full_response=bool(row["store_full_response"]),
        strict_output_validation=bool(row["strict_output_validation"]),
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _schema_to_json(schema: dict[str, Any] | None) -> str | None:
    if schema is None:
        return None
    return json.dumps(schema, sort_keys=True, separators=(",", ":"))


def _schema_from_json(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return json.loads(value)


def _auth_config_to_json(config: dict[str, Any] | None) -> str | None:
    if not config:
        return None
    return json.dumps(config, sort_keys=True, separators=(",", ":"))


def _auth_config_from_json(value: str | None) -> dict[str, Any] | None:
    if value is None or not str(value).strip():
        return None
    loaded = json.loads(value)
    if not isinstance(loaded, dict):
        raise ToolUpstreamTargetValidationError("Stored upstream auth config is invalid.")
    return loaded


def _query_allowlist_to_json(value: list[str]) -> str:
    return json.dumps(
        normalize_query_parameter_allowlist(value),
        sort_keys=True,
        separators=(",", ":"),
    )


def _query_allowlist_from_json(value: str | None) -> list[str]:
    if value is None or not str(value).strip():
        return []
    loaded = json.loads(value)
    if not isinstance(loaded, list) or not all(isinstance(item, str) for item in loaded):
        return []
    return normalize_query_parameter_allowlist(loaded)
