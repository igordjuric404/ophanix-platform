"""Tenant-scoped MCP registry persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from product_platform.db.postgres import Connection, IntegrityError, Row

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.mcp.discovery import NormalizedMCPToolDefinition, canonical_json
from product_platform.mcp.models import (
    MCPFindingResponse,
    MCPScanRunResponse,
    MCPServerCreateRequest,
    MCPServerPatchRequest,
    MCPServerResponse,
    MCPToolResponse,
    MCPToolVersionResponse,
SUPPORTED_MCP_FINDING_STATUSES,
)
from product_platform.mcp.scans import MCPScanFindingCandidate

BLOCKING_MCP_FINDING_STATUSES = {"open"}


class MCPServerNotFoundError(ValueError):
    """Raised when an MCP server is not visible in tenant scope."""


class MCPRegistryReferenceError(ValueError):
    """Raised when an MCP registry request references an invisible resource."""


class DuplicateMCPServerNameError(ValueError):
    """Raised when an MCP server name is already used in the environment."""


class MCPFindingNotFoundError(ValueError):
    """Raised when an MCP finding is not visible in tenant scope."""


class MCPFindingLifecycleError(ValueError):
    """Raised when a finding lifecycle transition is invalid."""


@dataclass(frozen=True)
class MCPToolSchemaChange:
    """Schema version change detected during tool discovery."""

    tool_id: str
    tool_name: str
    server_id: str
    version_id: str
    previous_schema_hash: str | None
    schema_hash: str


@dataclass(frozen=True)
class MCPToolDiscoveryPersistenceResult:
    """Rows and changes produced by a discovery persistence run."""

    rows: list[Row]
    schema_changes: list[MCPToolSchemaChange]


class MCPRegistryRepository:
    """Persistence for MCP server and tool registry records."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create_server(self, body: MCPServerCreateRequest) -> Row:
        """Create a tenant-scoped MCP server registry record."""

        self._require_owner_user(body.owner_user_id)
        if body.policy_pack_id:
            self._require_policy_pack(body.policy_pack_id)
        server_id = generate_id("mcpsrv")
        now = utc_now_iso()
        try:
            self.connection.execute(
                """
                INSERT INTO mcp_servers (
                    id, organization_id, environment_id, name, endpoint_url,
                    owner_user_id, auth_type, status, policy_pack_id,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    server_id,
                    self.organization_id,
                    self.environment_id,
                    body.name,
                    body.endpoint_url,
                    body.owner_user_id,
                    body.auth_type,
                    body.status,
                    body.policy_pack_id,
                    now,
                    now,
                ),
            )
        except IntegrityError as exc:
            raise DuplicateMCPServerNameError("MCP server name already exists.") from exc
        row = self.get_server(server_id)
        if row is None:
            raise MCPServerNotFoundError("Created MCP server could not be loaded.")
        return row

    def get_server(self, server_id: str) -> Row | None:
        """Get one MCP server in tenant scope."""

        return self.connection.execute(
            """
            SELECT
                s.*,
                u.display_name AS owner_display_name,
                u.email AS owner_email,
                (
                    SELECT COUNT(*)
                    FROM mcp_tools t
                    WHERE t.server_id = s.id
                ) AS tool_count
            FROM mcp_servers s
            LEFT JOIN users u ON u.id = s.owner_user_id
            WHERE s.id = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
            """,
            (server_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_servers(
        self,
        *,
        status: str | None = None,
        owner_user_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List MCP servers in tenant scope."""

        clauses = ["s.organization_id = ?", "s.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if status:
            clauses.append("s.status = ?")
            values.append(status)
        if owner_user_id:
            clauses.append("s.owner_user_id = ?")
            values.append(owner_user_id)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT
                s.*,
                u.display_name AS owner_display_name,
                u.email AS owner_email,
                (
                    SELECT COUNT(*)
                    FROM mcp_tools t
                    WHERE t.server_id = s.id
                ) AS tool_count
            FROM mcp_servers s
            LEFT JOIN users u ON u.id = s.owner_user_id
            WHERE {' AND '.join(clauses)}
            ORDER BY s.created_at DESC, s.id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def update_server(self, server_id: str, body: MCPServerPatchRequest) -> Row:
        """Patch MCP server registry metadata."""

        existing = self.get_server(server_id)
        if existing is None:
            raise MCPServerNotFoundError("MCP server not found.")
        fields: list[str] = []
        values: list[object] = []
        if "name" in body.model_fields_set and body.name is not None:
            fields.append("name = ?")
            values.append(body.name)
        if "endpoint_url" in body.model_fields_set and body.endpoint_url is not None:
            fields.append("endpoint_url = ?")
            values.append(body.endpoint_url)
        if "owner_user_id" in body.model_fields_set and body.owner_user_id is not None:
            self._require_owner_user(body.owner_user_id)
            fields.append("owner_user_id = ?")
            values.append(body.owner_user_id)
        if "auth_type" in body.model_fields_set and body.auth_type is not None:
            fields.append("auth_type = ?")
            values.append(body.auth_type)
        if "status" in body.model_fields_set and body.status is not None:
            fields.append("status = ?")
            values.append(body.status)
        if "policy_pack_id" in body.model_fields_set:
            if body.policy_pack_id:
                self._require_policy_pack(body.policy_pack_id)
            fields.append("policy_pack_id = ?")
            values.append(body.policy_pack_id)
        if not fields:
            return existing
        fields.append("updated_at = ?")
        values.append(utc_now_iso())
        values.extend([server_id, self.organization_id, self.environment_id])
        try:
            self.connection.execute(
                f"""
                UPDATE mcp_servers
                SET {', '.join(fields)}
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                values,
            )
        except IntegrityError as exc:
            raise DuplicateMCPServerNameError("MCP server name already exists.") from exc
        row = self.get_server(server_id)
        if row is None:
            raise MCPServerNotFoundError("MCP server not found.")
        return row

    def persist_discovered_tools(
        self,
        server_id: str,
        tools: list[NormalizedMCPToolDefinition],
    ) -> MCPToolDiscoveryPersistenceResult:
        """Persist discovered MCP tools and create versions only for new/changed schemas."""

        if self.get_server(server_id) is None:
            raise MCPServerNotFoundError("MCP server not found.")
        discovered_at = utc_now_iso()
        rows: list[Row] = []
        schema_changes: list[MCPToolSchemaChange] = []
        for tool in tools:
            tool_row = self._get_tool_by_name(server_id, tool.name)
            previous_schema_hash: str | None = None
            if tool_row is None:
                tool_id = generate_id("mcptool")
                self.connection.execute(
                    """
                    INSERT INTO mcp_tools (
                        id, server_id, name, description, current_version_id,
                        risk_level, status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tool_id,
                        server_id,
                        tool.name,
                        tool.description,
                        None,
                        "unknown",
                        "discovered",
                        discovered_at,
                        discovered_at,
                    ),
                )
            else:
                tool_id = tool_row["id"]
                current_version = self.current_tool_version(tool_row)
                if current_version is not None:
                    previous_schema_hash = current_version["schema_hash"]
                self.connection.execute(
                    """
                    UPDATE mcp_tools
                    SET description = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (tool.description, discovered_at, tool_id),
                )
            if previous_schema_hash == tool.schema_hash:
                row = self.get_tool(tool_id)
                if row is None:
                    raise ValueError("Discovered MCP tool could not be loaded.")
                rows.append(row)
                continue
            version_id = generate_id("mcptv")
            self.connection.execute(
                """
                INSERT INTO mcp_tool_versions (
                    id, tool_id, schema_json, schema_hash, definition_json,
                    discovered_at, scan_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    tool_id,
                    canonical_json(tool.schema),
                    tool.schema_hash,
                    canonical_json(tool.definition),
                    discovered_at,
                    "not_scanned",
                ),
            )
            tool_status = "changed" if previous_schema_hash is not None else "discovered"
            self.connection.execute(
                """
                UPDATE mcp_tools
                SET current_version_id = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (version_id, tool_status, discovered_at, tool_id),
            )
            schema_changes.append(
                MCPToolSchemaChange(
                    tool_id=tool_id,
                    tool_name=tool.name,
                    server_id=server_id,
                    version_id=version_id,
                    previous_schema_hash=previous_schema_hash,
                    schema_hash=tool.schema_hash,
                )
            )
            row = self.get_tool(tool_id)
            if row is None:
                raise ValueError("Discovered MCP tool could not be loaded.")
            rows.append(row)
        self.connection.execute(
            """
            UPDATE mcp_servers
            SET last_discovered_at = ?, updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (discovered_at, discovered_at, server_id, self.organization_id, self.environment_id),
        )
        return MCPToolDiscoveryPersistenceResult(rows=rows, schema_changes=schema_changes)

    def get_tool(self, tool_id: str) -> Row | None:
        """Get one MCP tool in tenant scope."""

        return self.connection.execute(
            """
            SELECT
                t.*,
                s.name AS server_name
            FROM mcp_tools t
            JOIN mcp_servers s ON s.id = t.server_id
            WHERE t.id = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
            """,
            (tool_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_tools(
        self,
        *,
        server_id: str | None = None,
        status: str | None = None,
        risk_level: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List MCP tools in tenant scope."""

        clauses = ["s.organization_id = ?", "s.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if server_id:
            clauses.append("t.server_id = ?")
            values.append(server_id)
        if status:
            clauses.append("t.status = ?")
            values.append(status)
        if risk_level:
            clauses.append("t.risk_level = ?")
            values.append(risk_level)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT
                t.*,
                s.name AS server_name
            FROM mcp_tools t
            JOIN mcp_servers s ON s.id = t.server_id
            WHERE {' AND '.join(clauses)}
            ORDER BY t.created_at DESC, t.id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def get_tool_version(self, version_id: str) -> Row | None:
        """Get one MCP tool version in tenant scope."""

        return self.connection.execute(
            """
            SELECT v.*
            FROM mcp_tool_versions v
            JOIN mcp_tools t ON t.id = v.tool_id
            JOIN mcp_servers s ON s.id = t.server_id
            WHERE v.id = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
            """,
            (version_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_tool_versions(self, tool_id: str) -> list[Row]:
        """List all schema versions for one visible MCP tool."""

        if self.get_tool(tool_id) is None:
            raise MCPRegistryReferenceError("MCP tool not found in current environment.")
        return self.connection.execute(
            """
            SELECT v.*
            FROM mcp_tool_versions v
            WHERE v.tool_id = ?
            ORDER BY v.discovered_at DESC, v.id DESC
            """,
            (tool_id,),
        ).fetchall()

    def current_tool_version(self, tool: Row) -> Row | None:
        """Return the current version for a tool row."""

        version_id = tool["current_version_id"]
        if version_id is None:
            return None
        return self.get_tool_version(version_id)

    def create_scan_run(self, server_id: str) -> Row:
        """Create a running MCP security scan run."""

        if self.get_server(server_id) is None:
            raise MCPServerNotFoundError("MCP server not found.")
        run_id = generate_id("mcpscan")
        started_at = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO mcp_scan_runs (
                id, server_id, status, started_at, finished_at, summary_json, error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, server_id, "running", started_at, None, "{}", None),
        )
        row = self.get_scan_run(run_id)
        if row is None:
            raise ValueError("Created MCP scan run could not be loaded.")
        return row

    def finish_scan_run(
        self,
        scan_run_id: str,
        *,
        status: str,
        summary: dict[str, object],
        error_message: str | None = None,
    ) -> Row:
        """Finish an MCP security scan run."""

        finished_at = utc_now_iso()
        self.connection.execute(
            """
            UPDATE mcp_scan_runs
            SET status = ?, finished_at = ?, summary_json = ?, error_message = ?
            WHERE id = ?
              AND server_id IN (
                SELECT id FROM mcp_servers
                WHERE organization_id = ? AND environment_id = ?
              )
            """,
            (
                status,
                finished_at,
                json.dumps(summary, sort_keys=True),
                error_message,
                scan_run_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        row = self.get_scan_run(scan_run_id)
        if row is None:
            raise ValueError("Finished MCP scan run could not be loaded.")
        return row

    def refresh_server_scan_gate_state(self, server_id: str) -> None:
        """Refresh tool/version gate state after a scan or finding lifecycle change."""

        if self.get_server(server_id) is None:
            raise MCPServerNotFoundError("MCP server not found.")
        for tool in self.list_tools(server_id=server_id, limit=500):
            version = self.current_tool_version(tool)
            if version is None:
                continue
            self.refresh_tool_scan_gate_state(tool["id"], version["id"])

    def refresh_tool_scan_gate_state(self, tool_id: str, version_id: str | None) -> None:
        """Mark a tool active or blocked based on current-version findings."""

        if version_id is None:
            return
        open_findings = self.connection.execute(
            """
            SELECT severity
            FROM mcp_findings
            WHERE tool_id = ?
              AND tool_version_id = ?
              AND status = 'open'
            """,
            (tool_id, version_id),
        ).fetchall()
        if open_findings:
            risk_level = _highest_mcp_risk(row["severity"] for row in open_findings)
            self.connection.execute(
                """
                UPDATE mcp_tool_versions
                SET scan_status = ?
                WHERE id = ?
                """,
                ("blocked", version_id),
            )
            self.connection.execute(
                """
                UPDATE mcp_tools
                SET status = ?, risk_level = ?, updated_at = ?
                WHERE id = ?
                """,
                ("blocked", risk_level, utc_now_iso(), tool_id),
            )
            return

        accepted = self.connection.execute(
            """
            SELECT 1
            FROM mcp_findings
            WHERE tool_id = ?
              AND tool_version_id = ?
              AND status = 'accepted_risk'
            LIMIT 1
            """,
            (tool_id, version_id),
        ).fetchone()
        scan_status = "accepted_risk" if accepted is not None else "passed"
        risk_level = "medium" if accepted is not None else "low"
        self.connection.execute(
            """
            UPDATE mcp_tool_versions
            SET scan_status = ?
            WHERE id = ?
            """,
            (scan_status, version_id),
        )
        self.connection.execute(
            """
            UPDATE mcp_tools
            SET status = ?, risk_level = ?, updated_at = ?
            WHERE id = ?
            """,
            ("active", risk_level, utc_now_iso(), tool_id),
        )

    def get_scan_run(self, scan_run_id: str) -> Row | None:
        """Get one MCP scan run in tenant scope."""

        return self.connection.execute(
            """
            SELECT
                r.*,
                s.name AS server_name
            FROM mcp_scan_runs r
            JOIN mcp_servers s ON s.id = r.server_id
            WHERE r.id = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
            """,
            (scan_run_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_scan_runs(
        self,
        *,
        server_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List MCP scan runs in tenant scope."""

        clauses = ["s.organization_id = ?", "s.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if server_id:
            clauses.append("r.server_id = ?")
            values.append(server_id)
        if status:
            clauses.append("r.status = ?")
            values.append(status)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT
                r.*,
                s.name AS server_name
            FROM mcp_scan_runs r
            JOIN mcp_servers s ON s.id = r.server_id
            WHERE {' AND '.join(clauses)}
            ORDER BY r.started_at DESC, r.id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def create_finding(
        self,
        scan_run_id: str,
        finding: MCPScanFindingCandidate,
    ) -> Row:
        """Persist a scanner finding for a visible scan run."""

        if self.get_scan_run(scan_run_id) is None:
            raise MCPRegistryReferenceError("MCP scan run not found in current environment.")
        finding_id = generate_id("mcpf")
        now = utc_now_iso()
        status = self._initial_finding_status(scan_run_id, finding)
        self.connection.execute(
            """
            INSERT INTO mcp_findings (
                id, scan_run_id, tool_id, tool_version_id, finding_type,
                severity, title, description, evidence_json, recommendation,
                status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                finding_id,
                scan_run_id,
                finding.tool_id,
                finding.tool_version_id,
                finding.finding_type,
                finding.severity,
                finding.title,
                finding.description,
                json.dumps(finding.evidence, sort_keys=True),
                finding.recommendation,
                status,
                now,
                now,
            ),
        )
        row = self.get_finding(finding_id)
        if row is None:
            raise ValueError("Created MCP finding could not be loaded.")
        return row

    def get_finding(self, finding_id: str) -> Row | None:
        """Get one MCP finding in tenant scope."""

        return self.connection.execute(
            """
            SELECT
                f.*,
                s.id AS server_id,
                s.name AS server_name,
                t.name AS tool_name
            FROM mcp_findings f
            JOIN mcp_scan_runs r ON r.id = f.scan_run_id
            JOIN mcp_tools t ON t.id = f.tool_id
            JOIN mcp_servers s ON s.id = r.server_id
            WHERE f.id = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
            """,
            (finding_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_findings(
        self,
        *,
        scan_run_id: str | None = None,
        server_id: str | None = None,
        tool_id: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List MCP findings in tenant scope."""

        clauses = ["s.organization_id = ?", "s.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        for column, value in [
            ("f.scan_run_id", scan_run_id),
            ("r.server_id", server_id),
            ("f.tool_id", tool_id),
            ("f.status", status),
            ("f.severity", severity),
        ]:
            if value:
                clauses.append(f"{column} = ?")
                values.append(value)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT
                f.*,
                s.id AS server_id,
                s.name AS server_name,
                t.name AS tool_name
            FROM mcp_findings f
            JOIN mcp_scan_runs r ON r.id = f.scan_run_id
            JOIN mcp_tools t ON t.id = f.tool_id
            JOIN mcp_servers s ON s.id = r.server_id
            WHERE {' AND '.join(clauses)}
            ORDER BY f.created_at DESC, f.id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def update_finding_status(
        self,
        finding_id: str,
        *,
        status: str,
        reason: str | None = None,
        actor_id: str | None = None,
    ) -> Row:
        """Update a finding lifecycle status and persist risk baselines when needed."""

        normalized_status = status.strip().lower()
        if normalized_status not in SUPPORTED_MCP_FINDING_STATUSES:
            supported = ", ".join(sorted(SUPPORTED_MCP_FINDING_STATUSES))
            raise MCPFindingLifecycleError(f"status must be one of: {supported}.")
        normalized_reason = reason.strip() if reason else None
        if normalized_status in {"accepted_risk", "false_positive"} and not normalized_reason:
            raise MCPFindingLifecycleError("reason is required for this finding status.")

        existing = self.get_finding(finding_id)
        if existing is None:
            raise MCPFindingNotFoundError("MCP finding not found.")

        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE mcp_findings
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (normalized_status, now, finding_id),
        )
        if normalized_status == "accepted_risk":
            self._upsert_scan_baseline(
                existing,
                accepted_by=actor_id or "system",
                accepted_at=now,
                reason=normalized_reason or "",
            )
        self.refresh_tool_scan_gate_state(existing["tool_id"], existing["tool_version_id"])
        updated = self.get_finding(finding_id)
        if updated is None:
            raise MCPFindingNotFoundError("MCP finding not found after update.")
        return updated

    def _require_owner_user(self, user_id: str) -> Row:
        row = self.connection.execute(
            """
            SELECT u.*
            FROM users u
            JOIN organization_memberships m ON m.user_id = u.id
            WHERE u.id = ?
              AND u.status = 'active'
              AND u.deleted_at IS NULL
              AND m.organization_id = ?
              AND m.status = 'active'
            """,
            (user_id, self.organization_id),
        ).fetchone()
        if row is None:
            raise MCPRegistryReferenceError("Owner user not found in current organization.")
        return row

    def _require_policy_pack(self, policy_pack_id: str) -> None:
        policy = self.connection.execute(
            """
            SELECT 1
            FROM policies
            WHERE id = ?
              AND organization_id = ?
              AND deleted_at IS NULL
            """,
            (policy_pack_id, self.organization_id),
        ).fetchone()
        if policy is not None:
            return
        placeholder = self.connection.execute(
            """
            SELECT 1
            FROM policy_placeholders
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND deleted_at IS NULL
            """,
            (policy_pack_id, self.organization_id, self.environment_id),
        ).fetchone()
        if placeholder is None:
            raise MCPRegistryReferenceError("Policy pack not found in current environment.")

    def _initial_finding_status(
        self,
        scan_run_id: str,
        finding: MCPScanFindingCandidate,
    ) -> str:
        if finding.tool_version_id is None:
            return "open"
        baseline = self.connection.execute(
            """
            SELECT 1
            FROM mcp_scan_baselines b
            JOIN mcp_scan_runs r ON r.server_id = b.server_id
            JOIN mcp_tool_versions v
              ON v.id = ?
             AND v.tool_id = b.tool_id
             AND v.schema_hash = b.schema_hash
            JOIN mcp_servers s ON s.id = r.server_id
            WHERE r.id = ?
              AND b.tool_id = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
            LIMIT 1
            """,
            (
                finding.tool_version_id,
                scan_run_id,
                finding.tool_id,
                self.organization_id,
                self.environment_id,
            ),
        ).fetchone()
        return "accepted_risk" if baseline is not None else "open"

    def _upsert_scan_baseline(
        self,
        finding: Row,
        *,
        accepted_by: str,
        accepted_at: str,
        reason: str,
    ) -> None:
        tool_version_id = finding["tool_version_id"]
        if tool_version_id is None:
            raise MCPFindingLifecycleError("finding is not linked to a tool version.")
        version = self.get_tool_version(tool_version_id)
        if version is None:
            raise MCPFindingLifecycleError("finding tool version is not visible.")
        existing = self.connection.execute(
            """
            SELECT id
            FROM mcp_scan_baselines
            WHERE server_id = ?
              AND tool_id = ?
              AND schema_hash = ?
            """,
            (finding["server_id"], finding["tool_id"], version["schema_hash"]),
        ).fetchone()
        if existing is not None:
            self.connection.execute(
                """
                UPDATE mcp_scan_baselines
                SET accepted_by = ?, accepted_at = ?, reason = ?
                WHERE id = ?
                """,
                (accepted_by, accepted_at, reason, existing["id"]),
            )
            return
        self.connection.execute(
            """
            INSERT INTO mcp_scan_baselines (
                id, server_id, tool_id, schema_hash, accepted_by, accepted_at, reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generate_id("mcpbase"),
                finding["server_id"],
                finding["tool_id"],
                version["schema_hash"],
                accepted_by,
                accepted_at,
                reason,
            ),
        )

    def _get_tool_by_name(self, server_id: str, name: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT t.*
            FROM mcp_tools t
            JOIN mcp_servers s ON s.id = t.server_id
            WHERE t.server_id = ?
              AND t.name = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
            """,
            (server_id, name, self.organization_id, self.environment_id),
        ).fetchone()


def mcp_server_response(row: Row) -> MCPServerResponse:
    """Serialize an MCP server row."""

    return MCPServerResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        name=row["name"],
        endpoint_url=row["endpoint_url"],
        owner_user_id=row["owner_user_id"],
        owner_display_name=row["owner_display_name"],
        owner_email=row["owner_email"],
        auth_type=row["auth_type"],
        status=row["status"],
        policy_pack_id=row["policy_pack_id"],
        tool_count=row["tool_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_discovered_at=row["last_discovered_at"],
    )


def mcp_tool_version_response(row: Row) -> MCPToolVersionResponse:
    """Serialize an MCP tool version row."""

    return MCPToolVersionResponse(
        id=row["id"],
        tool_id=row["tool_id"],
        input_schema=json.loads(row["schema_json"]),
        schema_hash=row["schema_hash"],
        definition=json.loads(row["definition_json"]),
        discovered_at=row["discovered_at"],
        scan_status=row["scan_status"],
    )


def mcp_tool_response(
    row: Row,
    *,
    current_version: MCPToolVersionResponse | None = None,
    versions: list[MCPToolVersionResponse] | None = None,
) -> MCPToolResponse:
    """Serialize an MCP tool row."""

    return MCPToolResponse(
        id=row["id"],
        server_id=row["server_id"],
        server_name=row["server_name"],
        name=row["name"],
        description=row["description"],
        current_version_id=row["current_version_id"],
        current_version=current_version,
        versions=versions or [],
        risk_level=row["risk_level"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def mcp_scan_run_response(
    row: Row,
    *,
    findings: list[MCPFindingResponse] | None = None,
) -> MCPScanRunResponse:
    """Serialize an MCP scan run row."""

    return MCPScanRunResponse(
        id=row["id"],
        server_id=row["server_id"],
        server_name=row["server_name"],
        status=row["status"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        summary=json.loads(row["summary_json"]),
        error_message=row["error_message"],
        findings=findings or [],
    )


def mcp_finding_response(row: Row) -> MCPFindingResponse:
    """Serialize an MCP finding row."""

    return MCPFindingResponse(
        id=row["id"],
        scan_run_id=row["scan_run_id"],
        server_id=row["server_id"],
        server_name=row["server_name"],
        tool_id=row["tool_id"],
        tool_name=row["tool_name"],
        tool_version_id=row["tool_version_id"],
        finding_type=row["finding_type"],
        severity=row["severity"],
        title=row["title"],
        description=row["description"],
        evidence=json.loads(row["evidence_json"]),
        recommendation=row["recommendation"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _highest_mcp_risk(severities: object) -> str:
    order = {
        "critical": 5,
        "high": 4,
        "warning": 3,
        "medium": 3,
        "low": 2,
        "info": 1,
    }
    highest = "warning"
    highest_score = 0
    for severity in severities:
        normalized = str(severity).strip().lower()
        score = order.get(normalized, 3)
        if score > highest_score:
            highest = "critical" if normalized == "critical" else normalized
            highest_score = score
    return highest
