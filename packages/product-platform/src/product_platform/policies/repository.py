"""Repositories and helpers for policy library persistence."""

from __future__ import annotations

import hashlib
import json
import re
from sqlite3 import Connection, Row

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.policies.models import (
    PolicyCreateRequest,
    PolicyDetailResponse,
    PolicyExportResponse,
    PolicyAffectedResource,
    PolicyAffectedResourcesResponse,
    PolicyImportResponse,
    PolicyLintIssue,
    PolicyLintResponse,
    PolicyResponse,
    PolicyVersionCreateRequest,
    PolicyVersionResponse,
)


class PolicyNotFoundError(ValueError):
    """Raised when a policy or version is not visible in the tenant scope."""


class DuplicatePolicySlugError(ValueError):
    """Raised when a policy slug is already used in an organization."""


def calculate_policy_checksum(body_text: str) -> str:
    """Return a stable checksum for an immutable policy body."""

    digest = hashlib.sha256(body_text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def slugify_policy_name(name: str) -> str:
    """Create a URL-safe slug from a policy name."""

    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "policy"


class PolicyRepository:
    """Organization-scoped policy library repository."""

    def __init__(self, connection: Connection, organization_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id

    def create_policy(self, body: PolicyCreateRequest, *, actor_id: str) -> Row:
        """Create a policy library entry."""

        slug = body.slug or slugify_policy_name(body.name)
        self._ensure_unique_slug(slug)
        now = utc_now_iso()
        policy_id = generate_id("policy")
        self.connection.execute(
            """
            INSERT INTO policies (
                id, organization_id, name, slug, description, scope, owner_user_id,
                status, tags_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                policy_id,
                self.organization_id,
                body.name,
                slug,
                body.description,
                body.scope,
                body.owner_user_id or actor_id,
                body.status,
                json.dumps(body.tags, sort_keys=True),
                now,
                now,
            ),
        )
        row = self.get_policy(policy_id)
        if row is None:
            raise PolicyNotFoundError("Created policy could not be loaded.")
        return row

    def list_policies(
        self,
        *,
        scope: str | None = None,
        owner_user_id: str | None = None,
        backend: str | None = None,
        status: str | None = None,
        tag: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List policies visible in the current organization."""

        clauses = ["p.organization_id = ?", "p.deleted_at IS NULL"]
        values: list[object] = [self.organization_id]
        for column, value in [
            ("p.scope", scope),
            ("p.owner_user_id", owner_user_id),
            ("p.status", status),
        ]:
            if value:
                clauses.append(f"{column} = ?")
                values.append(value)
        if backend:
            clauses.append(
                """
                EXISTS (
                    SELECT 1 FROM policy_versions pv
                    WHERE pv.policy_id = p.id AND pv.backend = ?
                )
                """
            )
            values.append(backend)
        values.extend([limit, offset])
        rows = self.connection.execute(
            f"""
            {self._policy_select()}
            WHERE {' AND '.join(clauses)}
            ORDER BY p.updated_at DESC, p.name ASC, p.id ASC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()
        if not tag:
            return rows
        normalized_tag = tag.strip().lower()
        return [row for row in rows if normalized_tag in _loads_list(row["tags_json"])]

    def get_policy(self, policy_id: str) -> Row | None:
        """Get one policy row by organization scope."""

        return self.connection.execute(
            f"""
            {self._policy_select()}
            WHERE p.id = ?
              AND p.organization_id = ?
              AND p.deleted_at IS NULL
            """,
            (policy_id, self.organization_id),
        ).fetchone()

    def create_version(
        self,
        policy_id: str,
        body: PolicyVersionCreateRequest,
        *,
        actor_id: str,
    ) -> Row:
        """Create an immutable version body for a policy."""

        policy = self.get_policy(policy_id)
        if policy is None:
            raise PolicyNotFoundError("Policy not found.")
        version_number = self._next_version_number(policy_id)
        now = utc_now_iso()
        version_id = generate_id("pver")
        self.connection.execute(
            """
            INSERT INTO policy_versions (
                id, policy_id, version_number, body_format, body_text, backend,
                checksum, status, created_by, created_at, activated_at, archived_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                policy_id,
                version_number,
                body.body_format,
                body.body_text,
                body.backend,
                calculate_policy_checksum(body.body_text),
                body.status,
                actor_id,
                now,
                now if body.status == "active" else None,
                now if body.status == "archived" else None,
            ),
        )
        row = self.get_version(policy_id, version_id)
        if row is None:
            raise PolicyNotFoundError("Created policy version could not be loaded.")
        return row

    def activate_version(self, policy_id: str, version_id: str) -> Row:
        """Activate a policy version and deactivate any prior active version."""

        version = self.get_version(policy_id, version_id)
        if version is None:
            raise PolicyNotFoundError("Policy version not found.")
        if version["status"] == "archived" or version["archived_at"] is not None:
            raise ValueError("Archived policy versions cannot be activated.")
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE policy_versions
            SET status = 'inactive'
            WHERE policy_id = ?
              AND status = 'active'
              AND id != ?
            """,
            (policy_id, version_id),
        )
        self.connection.execute(
            """
            UPDATE policy_versions
            SET status = 'active',
                activated_at = COALESCE(activated_at, ?)
            WHERE id = ? AND policy_id = ?
            """,
            (now, version_id, policy_id),
        )
        self.connection.execute(
            """
            UPDATE policies
            SET status = 'active', updated_at = ?
            WHERE id = ? AND organization_id = ? AND deleted_at IS NULL
            """,
            (now, policy_id, self.organization_id),
        )
        row = self.get_version(policy_id, version_id)
        if row is None:
            raise PolicyNotFoundError("Policy version not found.")
        return row

    def archive_version(self, policy_id: str, version_id: str) -> Row:
        """Archive a policy version so it cannot be activated."""

        version = self.get_version(policy_id, version_id)
        if version is None:
            raise PolicyNotFoundError("Policy version not found.")
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE policy_versions
            SET status = 'archived',
                archived_at = COALESCE(archived_at, ?)
            WHERE id = ? AND policy_id = ?
            """,
            (now, version_id, policy_id),
        )
        row = self.get_version(policy_id, version_id)
        if row is None:
            raise PolicyNotFoundError("Policy version not found.")
        return row

    def list_versions(self, policy_id: str) -> list[Row]:
        """List immutable versions for a visible policy."""

        if self.get_policy(policy_id) is None:
            raise PolicyNotFoundError("Policy not found.")
        return self.connection.execute(
            """
            SELECT pv.*
            FROM policy_versions pv
            JOIN policies p ON p.id = pv.policy_id
            WHERE pv.policy_id = ?
              AND p.organization_id = ?
              AND p.deleted_at IS NULL
            ORDER BY pv.version_number DESC, pv.created_at DESC, pv.id DESC
            """,
            (policy_id, self.organization_id),
        ).fetchall()

    def get_version(self, policy_id: str, version_id: str) -> Row | None:
        """Get one policy version by tenant scope."""

        return self.connection.execute(
            """
            SELECT pv.*
            FROM policy_versions pv
            JOIN policies p ON p.id = pv.policy_id
            WHERE pv.id = ?
              AND pv.policy_id = ?
              AND p.organization_id = ?
              AND p.deleted_at IS NULL
            """,
            (version_id, policy_id, self.organization_id),
        ).fetchone()

    def latest_export_version(self, policy_id: str, version_id: str | None = None) -> Row | None:
        """Return a requested, active, or latest version for export."""

        if version_id is not None:
            return self.get_version(policy_id, version_id)
        return self.connection.execute(
            """
            SELECT pv.*
            FROM policy_versions pv
            JOIN policies p ON p.id = pv.policy_id
            WHERE pv.policy_id = ?
              AND p.organization_id = ?
              AND p.deleted_at IS NULL
            ORDER BY
                CASE WHEN pv.status = 'active' THEN 0 ELSE 1 END,
                pv.version_number DESC,
                pv.created_at DESC,
                pv.id DESC
            LIMIT 1
            """,
            (policy_id, self.organization_id),
        ).fetchone()

    def record_import(
        self,
        *,
        source_type: str,
        source_path: str | None,
        status: str,
        summary: dict,
    ) -> Row:
        """Persist a policy import summary."""

        import_id = generate_id("pimp")
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO policy_imports (
                id, organization_id, source_type, source_path, status, summary_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                import_id,
                self.organization_id,
                source_type,
                source_path,
                status,
                json.dumps(summary, sort_keys=True),
                now,
            ),
        )
        row = self.connection.execute(
            """
            SELECT *
            FROM policy_imports
            WHERE id = ? AND organization_id = ?
            """,
            (import_id, self.organization_id),
        ).fetchone()
        if row is None:
            raise PolicyNotFoundError("Created policy import could not be loaded.")
        return row

    def replace_lint_results(
        self,
        policy_id: str,
        version_id: str,
        lint_result: PolicyLintResponse,
    ) -> list[Row]:
        """Replace persisted lint issues for a saved policy version."""

        if self.get_version(policy_id, version_id) is None:
            raise PolicyNotFoundError("Policy version not found.")
        self.connection.execute(
            "DELETE FROM policy_lint_results WHERE policy_version_id = ?",
            (version_id,),
        )
        now = utc_now_iso()
        for issue in lint_result.issues:
            self.connection.execute(
                """
                INSERT INTO policy_lint_results (
                    id, policy_version_id, severity, code, message, path,
                    line_number, fatal, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generate_id("lint"),
                    version_id,
                    issue.severity,
                    issue.code,
                    issue.message,
                    issue.path,
                    issue.line,
                    1 if issue.fatal else 0,
                    now,
                ),
            )
        return self.list_lint_results(policy_id, version_id)

    def list_lint_results(self, policy_id: str, version_id: str) -> list[Row]:
        """List persisted lint issues for a saved policy version."""

        if self.get_version(policy_id, version_id) is None:
            raise PolicyNotFoundError("Policy version not found.")
        return self.connection.execute(
            """
            SELECT lr.*
            FROM policy_lint_results lr
            JOIN policy_versions pv ON pv.id = lr.policy_version_id
            JOIN policies p ON p.id = pv.policy_id
            WHERE lr.policy_version_id = ?
              AND pv.policy_id = ?
              AND p.organization_id = ?
              AND p.deleted_at IS NULL
            ORDER BY lr.created_at ASC, lr.id ASC
            """,
            (version_id, policy_id, self.organization_id),
        ).fetchall()

    def affected_resources(self, policy_id: str) -> PolicyAffectedResourcesResponse:
        """Return resources currently referencing a policy in this organization."""

        if self.get_policy(policy_id) is None:
            raise PolicyNotFoundError("Policy not found.")
        resources: list[PolicyAffectedResource] = []
        rows = self.connection.execute(
            """
            SELECT
                a.id AS target_id,
                a.name AS label,
                a.status,
                a.environment_id,
                s.selection_type AS mode
            FROM agent_policy_selections s
            JOIN agents a ON a.id = s.agent_id
            WHERE s.policy_id = ?
              AND a.organization_id = ?
              AND a.deleted_at IS NULL
            ORDER BY a.name ASC, a.id ASC
            """,
            (policy_id, self.organization_id),
        ).fetchall()
        for row in rows:
            resources.append(
                PolicyAffectedResource(
                    target_type="agent",
                    target_id=row["target_id"],
                    label=row["label"],
                    status=row["status"],
                    mode=row["mode"],
                    environment_id=row["environment_id"],
                )
            )
        active_binding_count = 0
        if self._table_exists("policy_bindings"):
            binding_rows = self.connection.execute(
                """
                SELECT target_type, target_id, mode, status, environment_id
                FROM policy_bindings
                WHERE policy_id = ?
                  AND organization_id = ?
                ORDER BY priority DESC, created_at DESC, id DESC
                """,
                (policy_id, self.organization_id),
            ).fetchall()
            for row in binding_rows:
                if row["status"] == "active" and row["mode"] != "disabled":
                    active_binding_count += 1
                resources.append(
                    PolicyAffectedResource(
                        target_type=row["target_type"],
                        target_id=row["target_id"],
                        label=row["target_id"],
                        status=row["status"],
                        mode=row["mode"],
                        environment_id=row["environment_id"],
                    )
                )
        return PolicyAffectedResourcesResponse(
            policy_id=policy_id,
            resources=resources,
            active_binding_count=active_binding_count,
        )

    def _next_version_number(self, policy_id: str) -> int:
        row = self.connection.execute(
            """
            SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version
            FROM policy_versions
            WHERE policy_id = ?
            """,
            (policy_id,),
        ).fetchone()
        return int(row["next_version"])

    def _ensure_unique_slug(self, slug: str) -> None:
        row = self.connection.execute(
            """
            SELECT id
            FROM policies
            WHERE organization_id = ?
              AND slug = ?
              AND deleted_at IS NULL
            LIMIT 1
            """,
            (self.organization_id, slug),
        ).fetchone()
        if row is not None:
            raise DuplicatePolicySlugError("Policy slug already exists in this organization.")

    def _table_exists(self, table_name: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _policy_select() -> str:
        return """
            SELECT
                p.*,
                active.id AS active_version_id,
                active.version_number AS active_version_number,
                COALESCE(version_counts.version_count, 0) AS version_count
            FROM policies p
            LEFT JOIN policy_versions active
                ON active.policy_id = p.id
               AND active.status = 'active'
            LEFT JOIN (
                SELECT policy_id, COUNT(*) AS version_count
                FROM policy_versions
                GROUP BY policy_id
            ) version_counts ON version_counts.policy_id = p.id
        """


def policy_response(row: Row) -> PolicyResponse:
    """Serialize a policy row."""

    return PolicyResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        name=row["name"],
        slug=row["slug"],
        description=row["description"],
        scope=row["scope"],
        owner_user_id=row["owner_user_id"],
        status=row["status"],
        tags=_loads_list(row["tags_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        active_version_id=row["active_version_id"],
        active_version_number=row["active_version_number"],
        version_count=row["version_count"],
    )


def policy_detail_response(repository: PolicyRepository, row: Row) -> PolicyDetailResponse:
    """Serialize a policy row with versions."""

    base = policy_response(row)
    return PolicyDetailResponse(
        **base.model_dump(),
        versions=[policy_version_response(version) for version in repository.list_versions(row["id"])],
    )


def policy_version_response(row: Row) -> PolicyVersionResponse:
    """Serialize a policy version row."""

    return PolicyVersionResponse(
        id=row["id"],
        policy_id=row["policy_id"],
        version_number=row["version_number"],
        body_format=row["body_format"],
        body_text=row["body_text"],
        backend=row["backend"],
        checksum=row["checksum"],
        status=row["status"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        activated_at=row["activated_at"],
        archived_at=row["archived_at"],
    )


def policy_import_response(
    import_row: Row,
    *,
    policy: PolicyResponse,
    version: PolicyVersionResponse,
) -> PolicyImportResponse:
    """Serialize a policy import row."""

    summary = json.loads(import_row["summary_json"])
    warnings = summary.get("warnings", [])
    return PolicyImportResponse(
        id=import_row["id"],
        source_type=import_row["source_type"],
        source_path=import_row["source_path"],
        status=import_row["status"],
        summary=summary,
        warnings=[str(warning) for warning in warnings if str(warning)],
        policy=policy,
        version=version,
        created_at=import_row["created_at"],
    )


def policy_export_response(policy_row: Row, version_row: Row) -> PolicyExportResponse:
    """Serialize an exported policy body."""

    policy = policy_response(policy_row)
    version = policy_version_response(version_row)
    extension = {
        "yaml": "yaml",
        "json": "json",
        "rego": "rego",
        "cedar": "cedar",
    }.get(version.body_format, "txt")
    content_type = {
        "yaml": "application/x-yaml",
        "json": "application/json",
        "rego": "text/plain",
        "cedar": "text/plain",
    }.get(version.body_format, "text/plain")
    return PolicyExportResponse(
        filename=f"{policy.slug}-v{version.version_number}.{extension}",
        content_type=content_type,
        policy=policy,
        version=version,
        body_text=version.body_text,
        checksum=version.checksum,
    )


def policy_lint_issue_response(row: Row) -> PolicyLintIssue:
    """Serialize a persisted lint issue row."""

    return PolicyLintIssue(
        severity=row["severity"],
        code=row["code"],
        message=row["message"],
        path=row["path"],
        line=row["line_number"],
        fatal=bool(row["fatal"]),
    )


def _loads_list(raw_json: str) -> list[str]:
    parsed = json.loads(raw_json)
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]
