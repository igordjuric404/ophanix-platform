"""Demo Lab scenario persistence helpers."""

from __future__ import annotations

import json
from product_platform.db.postgres import Connection, Row
from typing import Any

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.demo.evidence import build_evidence_links, build_proof_checklist
from product_platform.demo.models import (
    DemoRunResponse,
    DemoRunStatus,
    DemoScenarioDetailResponse,
    DemoScenarioStepResponse,
    DemoScenarioSummaryResponse,
    DemoStepRunResponse,
    DemoStepRunStatus,
    parse_proof_links,
    parse_required_services,
)


class DemoScenarioNotFoundError(ValueError):
    """Raised when a scenario is not visible in the current tenant/environment."""


class DemoScenarioRepository:
    """Organization and environment scoped Demo Lab scenario repository."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def list_scenarios(self, *, status: str | None = None) -> list[Row]:
        """List scenarios in stable catalog order."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if status:
            clauses.append("status = ?")
            values.append(status)
        return self.connection.execute(
            f"""
            SELECT *
            FROM demo_scenarios
            WHERE {' AND '.join(clauses)}
            ORDER BY name ASC, id ASC
            """,
            values,
        ).fetchall()

    def get_scenario(self, scenario_id: str) -> Row | None:
        """Get a scenario row by id or slug."""

        return self.connection.execute(
            """
            SELECT *
            FROM demo_scenarios
            WHERE (id = ? OR slug = ?)
              AND organization_id = ?
              AND environment_id = ?
            """,
            (scenario_id, scenario_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_steps(self, scenario_id: str) -> list[Row]:
        """List scenario steps in execution order."""

        scenario = self.get_scenario(scenario_id)
        if scenario is None:
            raise DemoScenarioNotFoundError("Scenario not found.")
        return self.connection.execute(
            """
            SELECT *
            FROM demo_steps
            WHERE scenario_id = ?
            ORDER BY step_order ASC, id ASC
            """,
            (scenario["id"],),
        ).fetchall()

    def get_step(self, step_id: str) -> Row | None:
        """Get one scenario step visible in the current tenant/environment."""

        return self.connection.execute(
            """
            SELECT ds.*
            FROM demo_steps ds
            JOIN demo_scenarios sc ON sc.id = ds.scenario_id
            WHERE ds.id = ?
              AND sc.organization_id = ?
              AND sc.environment_id = ?
            """,
            (step_id, self.organization_id, self.environment_id),
        ).fetchone()

    def get_detail(self, scenario_id: str) -> DemoScenarioDetailResponse | None:
        """Return one scenario with ordered steps."""

        row = self.get_scenario(scenario_id)
        if row is None:
            return None
        steps = [demo_step_response(step) for step in self.list_steps(row["id"])]
        return DemoScenarioDetailResponse(
            **demo_scenario_summary_response(row).model_dump(),
            steps=steps,
        )

    def create_run(self, scenario_id: str, *, started_by: str) -> Row:
        """Create a run and pending step-run rows for every scenario step."""

        scenario = self.get_scenario(scenario_id)
        if scenario is None:
            raise DemoScenarioNotFoundError("Scenario not found.")
        steps = self.list_steps(scenario["id"])
        now = utc_now_iso()
        run_id = generate_id("demo_run")
        summary = _run_summary(total_steps=len(steps))
        self.connection.execute(
            """
            INSERT INTO demo_runs (
                id, organization_id, environment_id, scenario_id, status,
                started_by, started_at, finished_at, summary_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                self.organization_id,
                self.environment_id,
                scenario["id"],
                DemoRunStatus.RUNNING,
                started_by,
                now,
                None,
                _json(summary),
                now,
                now,
            ),
        )
        for step in steps:
            self.connection.execute(
                """
                INSERT INTO demo_step_runs (
                    id, demo_run_id, demo_step_id, status, result_json,
                    started_at, finished_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generate_id("demo_step_run"),
                    run_id,
                    step["id"],
                    DemoStepRunStatus.PENDING,
                    "{}",
                    None,
                    None,
                    now,
                    now,
                ),
            )
        row = self.get_run(run_id)
        if row is None:
            raise DemoScenarioNotFoundError("Created run could not be loaded.")
        return row

    def get_run(self, run_id: str) -> Row | None:
        """Get one run by tenant and environment scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM demo_runs
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (run_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_step_runs(self, run_id: str) -> list[Row]:
        """List step runs in scenario execution order."""

        if self.get_run(run_id) is None:
            raise DemoScenarioNotFoundError("Run not found.")
        return self.connection.execute(
            """
            SELECT dsr.*
            FROM demo_step_runs dsr
            JOIN demo_steps ds ON ds.id = dsr.demo_step_id
            WHERE dsr.demo_run_id = ?
            ORDER BY ds.step_order ASC, ds.id ASC
            """,
            (run_id,),
        ).fetchall()

    def next_pending_step_run(self, run_id: str) -> Row | None:
        """Return the next pending step run by scenario order."""

        return self.connection.execute(
            """
            SELECT dsr.*
            FROM demo_step_runs dsr
            JOIN demo_steps ds ON ds.id = dsr.demo_step_id
            JOIN demo_runs dr ON dr.id = dsr.demo_run_id
            WHERE dsr.demo_run_id = ?
              AND dsr.status = ?
              AND dr.organization_id = ?
              AND dr.environment_id = ?
            ORDER BY ds.step_order ASC, ds.id ASC
            LIMIT 1
            """,
            (
                run_id,
                DemoStepRunStatus.PENDING,
                self.organization_id,
                self.environment_id,
            ),
        ).fetchone()

    def mark_step_running(self, step_run_id: str) -> Row:
        """Mark one pending step run as running."""

        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE demo_step_runs
            SET status = ?, started_at = COALESCE(started_at, ?), updated_at = ?
            WHERE id = ? AND status = ?
            """,
            (DemoStepRunStatus.RUNNING, now, now, step_run_id, DemoStepRunStatus.PENDING),
        )
        return self._get_step_run(step_run_id)

    def mark_step_succeeded(self, step_run_id: str, result: dict[str, Any]) -> Row:
        """Mark one running step as succeeded and persist its result."""

        return self._finish_step(step_run_id, DemoStepRunStatus.SUCCEEDED, result)

    def mark_step_failed(self, step_run_id: str, result: dict[str, Any]) -> Row:
        """Mark one running step as failed and persist its result."""

        return self._finish_step(step_run_id, DemoStepRunStatus.FAILED, result)

    def refresh_run_status(self, run_id: str) -> Row:
        """Refresh aggregate run status from its step runs."""

        row = self.get_run(run_id)
        if row is None:
            raise DemoScenarioNotFoundError("Run not found.")
        if row["status"] in {DemoRunStatus.FAILED, DemoRunStatus.SUCCEEDED, DemoRunStatus.CANCELED}:
            return row
        steps = self.list_step_runs(run_id)
        statuses = [step["status"] for step in steps]
        completed_count = statuses.count(DemoStepRunStatus.SUCCEEDED)
        failed_count = statuses.count(DemoStepRunStatus.FAILED)
        summary = _run_summary(
            total_steps=len(steps),
            completed_steps=completed_count,
            failed_steps=failed_count,
        )
        status = DemoRunStatus.RUNNING
        finished_at = None
        if failed_count:
            status = DemoRunStatus.FAILED
            finished_at = utc_now_iso()
        elif steps and completed_count == len(steps):
            status = DemoRunStatus.SUCCEEDED
            finished_at = utc_now_iso()
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE demo_runs
            SET status = ?, finished_at = COALESCE(finished_at, ?),
                summary_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, finished_at, _json(summary), now, run_id),
        )
        refreshed = self.get_run(run_id)
        if refreshed is None:
            raise DemoScenarioNotFoundError("Run not found.")
        return refreshed

    def cancel_run(self, run_id: str, *, reason: str | None = None) -> Row:
        """Cancel a non-terminal run and mark remaining steps canceled."""

        row = self.get_run(run_id)
        if row is None:
            raise DemoScenarioNotFoundError("Run not found.")
        terminal = {DemoRunStatus.FAILED, DemoRunStatus.SUCCEEDED, DemoRunStatus.CANCELED}
        if row["status"] in terminal:
            return row
        now = utc_now_iso()
        result = {"reason": reason or "Run cancelled."}
        self.connection.execute(
            """
            UPDATE demo_step_runs
            SET status = ?, result_json = ?, finished_at = ?, updated_at = ?
            WHERE demo_run_id = ? AND status IN (?, ?)
            """,
            (
                DemoStepRunStatus.CANCELED,
                _json(result),
                now,
                now,
                run_id,
                DemoStepRunStatus.PENDING,
                DemoStepRunStatus.RUNNING,
            ),
        )
        steps = self.list_step_runs(run_id)
        summary = _run_summary(
            total_steps=len(steps),
            completed_steps=sum(1 for step in steps if step["status"] == DemoStepRunStatus.SUCCEEDED),
            failed_steps=sum(1 for step in steps if step["status"] == DemoStepRunStatus.FAILED),
            canceled_steps=sum(1 for step in steps if step["status"] == DemoStepRunStatus.CANCELED),
        )
        self.connection.execute(
            """
            UPDATE demo_runs
            SET status = ?, finished_at = ?, summary_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (DemoRunStatus.CANCELED, now, _json(summary), now, run_id),
        )
        canceled = self.get_run(run_id)
        if canceled is None:
            raise DemoScenarioNotFoundError("Run not found.")
        return canceled

    def _finish_step(self, step_run_id: str, status: str, result: dict[str, Any]) -> Row:
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE demo_step_runs
            SET status = ?, result_json = ?, finished_at = ?, updated_at = ?
            WHERE id = ? AND status = ?
            """,
            (status, _json(result), now, now, step_run_id, DemoStepRunStatus.RUNNING),
        )
        return self._get_step_run(step_run_id)

    def _get_step_run(self, step_run_id: str) -> Row:
        row = self.connection.execute(
            """
            SELECT dsr.*
            FROM demo_step_runs dsr
            JOIN demo_runs dr ON dr.id = dsr.demo_run_id
            WHERE dsr.id = ?
              AND dr.organization_id = ?
              AND dr.environment_id = ?
            """,
            (step_run_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise DemoScenarioNotFoundError("Step run not found.")
        return row


def demo_scenario_summary_response(row: Row) -> DemoScenarioSummaryResponse:
    """Serialize a scenario row for catalog responses."""

    return DemoScenarioSummaryResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        name=row["name"],
        slug=row["slug"],
        description=row["description"],
        value_proof=row["value_proof"],
        status=row["status"],
        required_services=parse_required_services(row["required_services_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def demo_step_response(row: Row) -> DemoScenarioStepResponse:
    """Serialize a scenario step row."""

    return DemoScenarioStepResponse(
        id=row["id"],
        scenario_id=row["scenario_id"],
        step_order=row["step_order"],
        title=row["title"],
        expected_result=row["expected_result"],
        action_type=row["action_type"],
        action_config=_loads_object(row["action_config_json"]),
        proof_links=parse_proof_links(row["proof_links_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def demo_run_response(repository: DemoScenarioRepository, row: Row) -> DemoRunResponse:
    """Serialize a run with scenario and ordered step-run details."""

    scenario = repository.get_scenario(row["scenario_id"])
    return DemoRunResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        scenario_id=row["scenario_id"],
        status=row["status"],
        started_by=row["started_by"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        summary=_loads_object(row["summary_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        scenario=demo_scenario_summary_response(scenario) if scenario is not None else None,
        step_runs=[
            demo_step_run_response(repository, step_run)
            for step_run in repository.list_step_runs(row["id"])
        ],
    )


def demo_step_run_response(
    repository: DemoScenarioRepository,
    row: Row,
) -> DemoStepRunResponse:
    """Serialize a step-run row with its static step definition."""

    step = repository.get_step(row["demo_step_id"])
    result = _loads_object(row["result_json"])
    step_response = demo_step_response(step) if step is not None else None
    return DemoStepRunResponse(
        id=row["id"],
        demo_run_id=row["demo_run_id"],
        demo_step_id=row["demo_step_id"],
        status=row["status"],
        result=result,
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        step=step_response,
        actual_result=_optional_str(result.get("actual_result")),
        evidence_links=build_evidence_links(step_response, result) if step_response else [],
        proof_checklist=build_proof_checklist(
            step_response,
            step_status=row["status"],
            result=result,
        )
        if step_response
        else [],
    )


def _loads_object(raw_json: str) -> dict[str, Any]:
    parsed = json.loads(raw_json)
    if not isinstance(parsed, dict):
        raise ValueError("JSON payload must be an object.")
    return parsed


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _run_summary(
    *,
    total_steps: int,
    completed_steps: int = 0,
    failed_steps: int = 0,
    canceled_steps: int = 0,
) -> dict[str, int]:
    return {
        "total_steps": total_steps,
        "completed_steps": completed_steps,
        "failed_steps": failed_steps,
        "canceled_steps": canceled_steps,
    }
