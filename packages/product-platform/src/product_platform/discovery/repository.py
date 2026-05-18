"""Repositories for product discovery scan targets and runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from product_platform.db.postgres import Connection, Row
from typing import Any

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.discovery.models import (
    DiscoveryRawFindingResponse,
    DiscoveryRunResponse,
    DiscoveryTargetCreateRequest,
    DiscoveryTargetResponse,
    DiscoveryTargetSchedulePatch,
)
from product_platform.discovery.registry import DiscoveryScannerRegistry
from product_platform.worker.scheduler import JobScheduleRepository, calculate_next_run


TARGET_TYPES_BY_SCANNER: dict[str, set[str]] = {
    "process": {"host"},
    "config": {"filesystem"},
    "github": {"github_repo", "github_org"},
}


class DiscoveryTargetNotFoundError(ValueError):
    """Raised when a discovery target is not visible in the tenant scope."""


class DiscoveryRepository:
    """Persistence for tenant-scoped discovery scanner configuration."""

    def __init__(
        self,
        connection: Connection,
        organization_id: str,
        environment_id: str,
        scanner_registry: DiscoveryScannerRegistry | None = None,
    ) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id
        self.scanner_registry = scanner_registry or DiscoveryScannerRegistry.default()

    def create_target(self, body: DiscoveryTargetCreateRequest) -> Row:
        """Validate and persist a discovery target."""

        scanner = self.scanner_registry.scanner_registry.get(body.scanner_type)
        if scanner is None:
            raise ValueError(f"Unknown scanner type: {body.scanner_type}")
        allowed_target_types = TARGET_TYPES_BY_SCANNER.get(body.scanner_type, set())
        if body.target_type not in allowed_target_types:
            raise ValueError(
                f"Target type '{body.target_type}' is not supported for "
                f"{body.scanner_type} scanner."
            )
        normalized_config = self._normalize_target_config(body)
        errors = self.scanner_registry.validate_config(body.scanner_type, normalized_config)
        if errors:
            raise ValueError("; ".join(errors))

        now = utc_now_iso()
        target_id = generate_id("target")
        self.connection.execute(
            """
            INSERT INTO discovery_targets (
                id, organization_id, environment_id, scanner_id, scanner_type,
                target_type, target_value, credentials_ref, schedule_id, enabled,
                config_json, created_at, updated_at, deleted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                target_id,
                self.organization_id,
                self.environment_id,
                f"scanner_{body.scanner_type}",
                body.scanner_type,
                body.target_type,
                body.target_value,
                body.credentials_ref,
                body.schedule_id,
                1 if body.enabled else 0,
                json.dumps(normalized_config, sort_keys=True),
                now,
                now,
            ),
        )
        row = self.get_target(target_id)
        if row is None:
            raise DiscoveryTargetNotFoundError("Created discovery target could not be loaded.")
        return row

    def list_targets(self) -> list[Row]:
        """List active targets scoped to the selected environment."""

        return self.connection.execute(
            """
            SELECT t.*,
                   s.cron_expression AS schedule_expression,
                   s.enabled AS schedule_enabled,
                   s.next_run_at AS next_run_at,
                   s.last_run_at AS last_run_at
            FROM discovery_targets t
            LEFT JOIN job_schedules s ON s.id = t.schedule_id
            WHERE t.organization_id = ?
              AND t.environment_id = ?
              AND t.deleted_at IS NULL
            ORDER BY t.created_at ASC, t.id ASC
            """,
            (self.organization_id, self.environment_id),
        ).fetchall()

    def get_target(self, target_id: str) -> Row | None:
        """Get a target by tenant scope."""

        return self.connection.execute(
            """
            SELECT t.*,
                   s.cron_expression AS schedule_expression,
                   s.enabled AS schedule_enabled,
                   s.next_run_at AS next_run_at,
                   s.last_run_at AS last_run_at
            FROM discovery_targets t
            LEFT JOIN job_schedules s ON s.id = t.schedule_id
            WHERE t.id = ?
              AND t.organization_id = ?
              AND t.environment_id = ?
              AND t.deleted_at IS NULL
            """,
            (target_id, self.organization_id, self.environment_id),
        ).fetchone()

    def update_target_schedule(
        self,
        target_id: str,
        body: DiscoveryTargetSchedulePatch,
    ) -> Row:
        """Attach or update a job schedule for a discovery target."""

        target = self.get_target(target_id)
        if target is None:
            raise DiscoveryTargetNotFoundError("Discovery target not found.")

        if body.mode == "manual":
            if target["schedule_id"]:
                self.connection.execute(
                    "UPDATE job_schedules SET enabled = 0, updated_at = ? WHERE id = ?",
                    (utc_now_iso(), target["schedule_id"]),
                )
            self.connection.execute(
                """
                UPDATE discovery_targets
                SET schedule_id = NULL, updated_at = ?
                WHERE id = ? AND organization_id = ? AND environment_id = ?
                """,
                (utc_now_iso(), target_id, self.organization_id, self.environment_id),
            )
            updated = self.get_target(target_id)
            if updated is None:
                raise DiscoveryTargetNotFoundError("Discovery target not found.")
            return updated

        expression = _schedule_expression(body.mode)
        next_run_at = body.next_run_at or calculate_next_run(
            expression,
            datetime.now(timezone.utc),
        ).isoformat()
        payload = {"target_id": target_id}
        schedules = JobScheduleRepository(self.connection)
        if target["schedule_id"]:
            self.connection.execute(
                """
                UPDATE job_schedules
                SET job_type = ?,
                    cron_expression = ?,
                    payload_json = ?,
                    enabled = ?,
                    next_run_at = ?,
                    updated_at = ?
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                (
                    "discovery.scan",
                    expression,
                    json.dumps(payload, sort_keys=True),
                    1 if body.enabled else 0,
                    next_run_at,
                    utc_now_iso(),
                    target["schedule_id"],
                    self.organization_id,
                    self.environment_id,
                ),
            )
        else:
            schedule = schedules.create_schedule(
                organization_id=self.organization_id,
                environment_id=self.environment_id,
                job_type="discovery.scan",
                expression=expression,
                payload=payload,
                enabled=body.enabled,
                next_run_at=next_run_at,
            )
            self.connection.execute(
                """
                UPDATE discovery_targets
                SET schedule_id = ?, updated_at = ?
                WHERE id = ? AND organization_id = ? AND environment_id = ?
                """,
                (
                    schedule["id"],
                    utc_now_iso(),
                    target_id,
                    self.organization_id,
                    self.environment_id,
                ),
            )
        updated = self.get_target(target_id)
        if updated is None:
            raise DiscoveryTargetNotFoundError("Discovery target not found.")
        return updated

    def create_run(self, target: Row) -> Row:
        """Create a running discovery scan record."""

        now = utc_now_iso()
        run_id = generate_id("run")
        self.connection.execute(
            """
            INSERT INTO discovery_runs (
                id, organization_id, environment_id, scanner_id, scanner_type,
                target_id, status, started_at, finished_at, error_message,
                summary_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?)
            ON CONFLICT (organization_id, environment_id, target_id)
            WHERE status = 'running'
            DO NOTHING
            """,
            (
                run_id,
                self.organization_id,
                self.environment_id,
                target["scanner_id"],
                target["scanner_type"],
                target["id"],
                "running",
                now,
                "{}",
                now,
                now,
            ),
        )
        row = self.get_run(run_id)
        if row is None:
            return self._create_skipped_overlap_run(target, now=now)
        return row

    def _create_skipped_overlap_run(self, target: Row, *, now: str) -> Row:
        run_id = generate_id("run")
        reason = "A discovery scan is already running for this target."
        summary = {"overlap": True, "raw_finding_count": 0}
        self.connection.execute(
            """
            INSERT INTO discovery_runs (
                id, organization_id, environment_id, scanner_id, scanner_type,
                target_id, status, started_at, finished_at, error_message,
                summary_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                self.organization_id,
                self.environment_id,
                target["scanner_id"],
                target["scanner_type"],
                target["id"],
                "skipped",
                now,
                now,
                reason,
                json.dumps(summary, sort_keys=True),
                now,
                now,
            ),
        )
        row = self.get_run(run_id)
        if row is None:
            raise DiscoveryTargetNotFoundError("Created discovery run could not be loaded.")
        return row

    def has_running_run_for_target(
        self,
        target_id: str,
        *,
        exclude_run_id: str | None = None,
    ) -> bool:
        """Return whether a target already has a running scan."""

        clauses = [
            "target_id = ?",
            "organization_id = ?",
            "environment_id = ?",
            "status = 'running'",
        ]
        values: list[object] = [target_id, self.organization_id, self.environment_id]
        if exclude_run_id is not None:
            clauses.append("id != ?")
            values.append(exclude_run_id)
        row = self.connection.execute(
            f"SELECT 1 FROM discovery_runs WHERE {' AND '.join(clauses)} LIMIT 1",
            values,
        ).fetchone()
        return row is not None

    def mark_run_succeeded(self, run_id: str, *, summary: dict[str, Any]) -> Row:
        """Mark a run as succeeded."""

        return self._finish_run(run_id, status="succeeded", summary=summary)

    def mark_run_failed(
        self,
        run_id: str,
        *,
        error_message: str,
        summary: dict[str, Any] | None = None,
    ) -> Row:
        """Mark a run as failed with an operator-visible error."""

        return self._finish_run(
            run_id,
            status="failed",
            error_message=error_message,
            summary=summary or {"raw_finding_count": 0, "errors": [error_message]},
        )

    def mark_run_skipped(self, run_id: str, *, reason: str) -> Row:
        """Mark a run as skipped without invoking the scanner."""

        return self._finish_run(
            run_id,
            status="skipped",
            error_message=reason,
            summary={"raw_finding_count": 0, "overlap": True, "reason": reason},
        )

    def persist_raw_findings(
        self,
        run_id: str,
        findings: list[dict[str, Any]],
    ) -> list[Row]:
        """Persist scanner findings exactly as emitted for later reconciliation."""

        now = utc_now_iso()
        for finding in findings:
            self.connection.execute(
                """
                INSERT INTO discovery_raw_findings (
                    id, run_id, raw_payload_json, fingerprint, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    generate_id("raw"),
                    run_id,
                    json.dumps(finding, sort_keys=True),
                    str(finding.get("fingerprint") or generate_id("fp")),
                    now,
                ),
            )
        return self.list_raw_findings(run_id)

    def list_runs(self) -> list[Row]:
        """List scan runs scoped to the selected environment."""

        return self.connection.execute(
            """
            SELECT *
            FROM discovery_runs
            WHERE organization_id = ?
              AND environment_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (self.organization_id, self.environment_id),
        ).fetchall()

    def get_run(self, run_id: str) -> Row | None:
        """Get a scan run by tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM discovery_runs
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (run_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_raw_findings(self, run_id: str) -> list[Row]:
        """List raw findings for a scan run."""

        return self.connection.execute(
            """
            SELECT f.*
            FROM discovery_raw_findings f
            JOIN discovery_runs r ON r.id = f.run_id
            WHERE f.run_id = ?
              AND r.organization_id = ?
              AND r.environment_id = ?
            ORDER BY f.created_at ASC, f.id ASC
            """,
            (run_id, self.organization_id, self.environment_id),
        ).fetchall()

    def _normalize_target_config(self, body: DiscoveryTargetCreateRequest) -> dict[str, Any]:
        config = dict(body.config_json)
        if body.scanner_type == "config":
            config.setdefault("paths", [body.target_value])
        if body.scanner_type == "process":
            config.setdefault("include_command_line", False)
        if body.scanner_type == "github":
            if not body.credentials_ref:
                raise ValueError("credentials_ref is required for GitHub discovery targets.")
            config.setdefault("token_ref", body.credentials_ref)
            if body.target_type == "github_repo":
                config.setdefault("repos", [body.target_value])
            if body.target_type == "github_org":
                config.setdefault("org", body.target_value)
        return config

    def _finish_run(
        self,
        run_id: str,
        *,
        status: str,
        summary: dict[str, Any],
        error_message: str | None = None,
    ) -> Row:
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE discovery_runs
            SET status = ?,
                finished_at = ?,
                error_message = ?,
                summary_json = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (
                status,
                now,
                error_message,
                json.dumps(summary, sort_keys=True),
                now,
                run_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        row = self.get_run(run_id)
        if row is None:
            raise DiscoveryTargetNotFoundError("Discovery run not found.")
        return row


def discovery_target_response(row: Row) -> DiscoveryTargetResponse:
    """Serialize a discovery target database row."""

    schedule_expression = _optional_row_value(row, "schedule_expression")
    return DiscoveryTargetResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        scanner_id=row["scanner_id"],
        scanner_type=row["scanner_type"],
        target_type=row["target_type"],
        target_value=row["target_value"],
        credentials_ref=row["credentials_ref"],
        schedule_id=row["schedule_id"],
        schedule_mode=_schedule_mode(schedule_expression),
        schedule_enabled=bool(_optional_row_value(row, "schedule_enabled") or False),
        next_run_at=_optional_row_value(row, "next_run_at"),
        last_run_at=_optional_row_value(row, "last_run_at"),
        enabled=bool(row["enabled"]),
        config_json=json.loads(row["config_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _schedule_expression(mode: str) -> str:
    return {"hourly": "@hourly", "daily": "interval:1d"}[mode]


def _schedule_mode(expression: str | None) -> str:
    if expression == "@hourly":
        return "hourly"
    if expression == "interval:1d":
        return "daily"
    return "manual"


def _optional_row_value(row: Row, key: str) -> Any:
    return row[key] if key in row.keys() else None


def discovery_raw_finding_response(row: Row) -> DiscoveryRawFindingResponse:
    """Serialize a raw finding database row."""

    return DiscoveryRawFindingResponse(
        id=row["id"],
        run_id=row["run_id"],
        fingerprint=row["fingerprint"],
        raw_payload_json=json.loads(row["raw_payload_json"]),
        created_at=row["created_at"],
    )


def discovery_run_response(
    repository: DiscoveryRepository,
    row: Row,
    *,
    include_findings: bool = False,
) -> DiscoveryRunResponse:
    """Serialize a discovery run row."""

    findings = repository.list_raw_findings(row["id"])
    return DiscoveryRunResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        scanner_id=row["scanner_id"],
        scanner_type=row["scanner_type"],
        target_id=row["target_id"],
        status=row["status"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        error_message=row["error_message"],
        summary_json=json.loads(row["summary_json"]),
        raw_finding_count=len(findings),
        raw_findings=[
            discovery_raw_finding_response(finding) for finding in findings
        ]
        if include_findings
        else [],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
