"""Observability persistence repositories."""

from __future__ import annotations

import json
from sqlite3 import Connection, Row

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.observability.models import (
    ChaosExperimentCreateRequest,
    ChaosExperimentResponse,
    ChaosRunCreateRequest,
    ChaosRunResponse,
    CostBudgetCreateRequest,
    CostBudgetResponse,
    CostDashboardResponse,
    CostEventCreateRequest,
    CostEventResponse,
    IncidentCreateRequest,
    IncidentFromEventRequest,
    IncidentResolveRequest,
    IncidentResponse,
    RolloutAdvanceRequest,
    RolloutCreateRequest,
    RolloutEventResponse,
    RolloutRollbackRequest,
    RolloutResponse,
    SloMeasurementCreateRequest,
    SloMeasurementResponse,
    SloObjectiveCreateRequest,
    SloObjectiveResponse,
)
from product_platform.observability.costs import evaluate_cost_budget
from product_platform.observability.chaos import evaluate_chaos_run
from product_platform.observability.rollouts import evaluate_rollout_gates
from product_platform.observability.slo import evaluate_slo_measurement


class SloObjectiveNotFoundError(ValueError):
    """Raised when an SLO objective is not visible in tenant scope."""


class CostBudgetNotFoundError(ValueError):
    """Raised when a cost budget is not visible in tenant scope."""


class IncidentNotFoundError(ValueError):
    """Raised when an incident is not visible in tenant scope."""


class IncidentStateError(ValueError):
    """Raised when an incident lifecycle transition is invalid."""


class ChaosExperimentNotFoundError(ValueError):
    """Raised when a chaos experiment is not visible in tenant scope."""


class ChaosExperimentValidationError(ValueError):
    """Raised when a chaos experiment definition violates safety controls."""


class ChaosRunNotFoundError(ValueError):
    """Raised when a chaos run is not visible in tenant scope."""


class RolloutNotFoundError(ValueError):
    """Raised when a rollout is not visible in tenant scope."""


class ObservabilityRepository:
    """Tenant-scoped observability repository."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create_slo(self, body: SloObjectiveCreateRequest, *, created_by: str) -> Row:
        """Create an SLO objective."""

        now = utc_now_iso()
        slo_id = generate_id("slo")
        self.connection.execute(
            """
            INSERT INTO slo_objectives (
                id, organization_id, environment_id, name, target_type,
                target_id, sli, target_value, window, status, created_by,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                slo_id,
                self.organization_id,
                self.environment_id,
                body.name,
                body.target_type,
                body.target_id,
                body.sli,
                body.target_value,
                body.window,
                "unknown",
                created_by,
                now,
                now,
            ),
        )
        row = self.get_slo(slo_id)
        if row is None:
            raise SloObjectiveNotFoundError("Created SLO could not be loaded.")
        return row

    def list_slos(
        self,
        *,
        target_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List SLO objectives in tenant scope."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if target_type:
            clauses.append("target_type = ?")
            values.append(target_type)
        if status:
            clauses.append("status = ?")
            values.append(status)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT *
            FROM slo_objectives
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC, created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def get_slo(self, slo_id: str) -> Row | None:
        """Get an SLO objective in tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM slo_objectives
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (slo_id, self.organization_id, self.environment_id),
        ).fetchone()

    def create_slo_measurement(self, slo_id: str, body: SloMeasurementCreateRequest) -> Row:
        """Persist one SLO measurement and update objective status."""

        objective = self.get_slo(slo_id)
        if objective is None:
            raise SloObjectiveNotFoundError("SLO objective not found.")
        evaluation = evaluate_slo_measurement(
            target_value=float(objective["target_value"]),
            value=body.value,
            good_events=body.good_events,
            total_events=body.total_events,
        )
        measurement_id = generate_id("slomeas")
        measured_at = body.measured_at or utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO slo_measurements (
                id, slo_id, value, good_events, total_events,
                error_budget_remaining, burn_rate, status, metadata_json,
                measured_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                measurement_id,
                slo_id,
                body.value,
                evaluation.good_events,
                evaluation.total_events,
                evaluation.error_budget_remaining,
                evaluation.burn_rate,
                evaluation.status,
                json.dumps(body.metadata, sort_keys=True, separators=(",", ":")),
                measured_at,
            ),
        )
        self.connection.execute(
            """
            UPDATE slo_objectives
            SET status = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (evaluation.status, measured_at, slo_id, self.organization_id, self.environment_id),
        )
        row = self.get_slo_measurement(measurement_id)
        if row is None:
            raise SloObjectiveNotFoundError("Created SLO measurement could not be loaded.")
        return row

    def list_slo_measurements(self, slo_id: str, *, limit: int = 20) -> list[Row]:
        """List recent measurements for an objective."""

        if self.get_slo(slo_id) is None:
            raise SloObjectiveNotFoundError("SLO objective not found.")
        return self.connection.execute(
            """
            SELECT *
            FROM slo_measurements
            WHERE slo_id = ?
            ORDER BY measured_at DESC, id DESC
            LIMIT ?
            """,
            (slo_id, limit),
        ).fetchall()

    def get_slo_measurement(self, measurement_id: str) -> Row | None:
        """Get a measurement in tenant scope."""

        return self.connection.execute(
            """
            SELECT m.*
            FROM slo_measurements m
            JOIN slo_objectives s ON s.id = m.slo_id
            WHERE m.id = ?
              AND s.organization_id = ?
              AND s.environment_id = ?
            """,
            (measurement_id, self.organization_id, self.environment_id),
        ).fetchone()

    def create_cost_budget(self, body: CostBudgetCreateRequest, *, created_by: str) -> Row:
        """Create a cost budget."""

        now = utc_now_iso()
        budget_id = generate_id("costbud")
        self.connection.execute(
            """
            INSERT INTO cost_budgets (
                id, organization_id, environment_id, target_type, target_id,
                period, amount_limit, used_amount, action_on_breach,
                breach_action, status, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                budget_id,
                self.organization_id,
                self.environment_id,
                body.target_type,
                body.target_id,
                body.period,
                body.amount_limit,
                0.0,
                body.action_on_breach,
                "none",
                "active",
                created_by,
                now,
                now,
            ),
        )
        row = self.get_cost_budget(budget_id)
        if row is None:
            raise CostBudgetNotFoundError("Created cost budget could not be loaded.")
        return row

    def list_cost_budgets(
        self,
        *,
        target_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List cost budgets in tenant scope."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if target_type:
            clauses.append("target_type = ?")
            values.append(target_type)
        if status:
            clauses.append("status = ?")
            values.append(status)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT *
            FROM cost_budgets
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC, created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def get_cost_budget(self, budget_id: str) -> Row | None:
        """Get one cost budget in tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM cost_budgets
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (budget_id, self.organization_id, self.environment_id),
        ).fetchone()

    def create_cost_event(self, body: CostEventCreateRequest) -> Row:
        """Persist a cost event and update matching budgets."""

        now = body.created_at or utc_now_iso()
        event_id = generate_id("costevt")
        self.connection.execute(
            """
            INSERT INTO cost_events (
                id, organization_id, environment_id, target_type, target_id,
                provider, model, amount, units, correlation_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                self.organization_id,
                self.environment_id,
                body.target_type,
                body.target_id,
                body.provider,
                body.model,
                body.amount,
                body.units,
                body.correlation_id,
                now,
            ),
        )
        for budget in self._matching_budgets(body.target_type, body.target_id):
            used_amount = float(budget["used_amount"]) + body.amount
            evaluation = evaluate_cost_budget(
                amount_limit=float(budget["amount_limit"]),
                used_amount=used_amount,
                action_on_breach=budget["action_on_breach"],
            )
            self.connection.execute(
                """
                UPDATE cost_budgets
                SET used_amount = ?,
                    status = ?,
                    breach_action = ?,
                    updated_at = ?
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                (
                    used_amount,
                    evaluation.status,
                    evaluation.breach_action,
                    now,
                    budget["id"],
                    self.organization_id,
                    self.environment_id,
                ),
            )
        row = self.get_cost_event(event_id)
        if row is None:
            raise CostBudgetNotFoundError("Created cost event could not be loaded.")
        return row

    def list_cost_events(self, *, limit: int = 100) -> list[Row]:
        """List recent cost events in tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM cost_events
            WHERE organization_id = ?
              AND environment_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (self.organization_id, self.environment_id, limit),
        ).fetchall()

    def get_cost_event(self, event_id: str) -> Row | None:
        """Get a cost event in tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM cost_events
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (event_id, self.organization_id, self.environment_id),
        ).fetchone()

    def _matching_budgets(self, target_type: str, target_id: str) -> list[Row]:
        return self.connection.execute(
            """
            SELECT *
            FROM cost_budgets
            WHERE organization_id = ?
              AND environment_id = ?
              AND target_type = ?
              AND target_id = ?
            """,
            (self.organization_id, self.environment_id, target_type, target_id),
        ).fetchall()

    def create_incident(self, body: IncidentCreateRequest) -> Row:
        """Create a manual incident."""

        now = utc_now_iso()
        incident_id = generate_id("inc")
        self.connection.execute(
            """
            INSERT INTO incidents (
                id, organization_id, environment_id, severity, status,
                title, summary, owner_user_id, correlation_id, source_event_id,
                resolution_note, started_at, acknowledged_at, resolved_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id,
                self.organization_id,
                self.environment_id,
                body.severity,
                "open",
                body.title,
                body.summary,
                body.owner_user_id,
                body.correlation_id,
                body.source_event_id,
                None,
                now,
                None,
                None,
                now,
            ),
        )
        row = self.get_incident(incident_id)
        if row is None:
            raise IncidentNotFoundError("Created incident could not be loaded.")
        return row

    def create_incident_from_event(self, body: IncidentFromEventRequest) -> Row:
        """Create an incident from a high-severity audit event."""

        event = self._get_audit_event(body.source_event_id)
        if event is None:
            raise IncidentNotFoundError("Audit event not found.")
        severity = event["severity"] if event["severity"] in {"warning", "critical"} else "warning"
        title = body.title or f"{event['event_type']} incident"
        summary = f"Incident created from {event['event_type']} audit event {event['id']}."
        return self.create_incident(
            IncidentCreateRequest(
                severity=severity,
                title=title,
                summary=summary,
                owner_user_id=body.owner_user_id,
                correlation_id=event["correlation_id"],
                source_event_id=event["id"],
            )
        )

    def list_incidents(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List incidents in tenant scope."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if status:
            clauses.append("status = ?")
            values.append(status)
        if severity:
            clauses.append("severity = ?")
            values.append(severity)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT *
            FROM incidents
            WHERE {' AND '.join(clauses)}
            ORDER BY started_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def get_incident(self, incident_id: str) -> Row | None:
        """Get an incident in tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM incidents
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (incident_id, self.organization_id, self.environment_id),
        ).fetchone()

    def acknowledge_incident(self, incident_id: str, *, actor_id: str) -> Row:
        """Acknowledge an open incident."""

        incident = self.get_incident(incident_id)
        if incident is None:
            raise IncidentNotFoundError("Incident not found.")
        if incident["status"] == "resolved":
            raise IncidentStateError("Resolved incidents cannot be acknowledged.")
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE incidents
            SET status = ?,
                owner_user_id = COALESCE(owner_user_id, ?),
                acknowledged_at = COALESCE(acknowledged_at, ?),
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            ("acknowledged", actor_id, now, now, incident_id, self.organization_id, self.environment_id),
        )
        row = self.get_incident(incident_id)
        if row is None:
            raise IncidentNotFoundError("Incident not found.")
        return row

    def resolve_incident(self, incident_id: str, body: IncidentResolveRequest) -> Row:
        """Resolve an incident with a required note."""

        incident = self.get_incident(incident_id)
        if incident is None:
            raise IncidentNotFoundError("Incident not found.")
        if incident["status"] == "resolved":
            raise IncidentStateError("Incident is already resolved.")
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE incidents
            SET status = ?,
                resolution_note = ?,
                resolved_at = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            ("resolved", body.resolution_note, now, now, incident_id, self.organization_id, self.environment_id),
        )
        row = self.get_incident(incident_id)
        if row is None:
            raise IncidentNotFoundError("Incident not found.")
        return row

    def related_audit_event_ids(self, incident: Row) -> list[str]:
        """Return audit event ids linked by source event or correlation id."""

        if incident["correlation_id"]:
            rows = self.connection.execute(
                """
                SELECT id
                FROM audit_events
                WHERE organization_id = ?
                  AND environment_id = ?
                  AND correlation_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 25
                """,
                (self.organization_id, self.environment_id, incident["correlation_id"]),
            ).fetchall()
            return [row["id"] for row in rows]
        if incident["source_event_id"]:
            return [incident["source_event_id"]]
        return []

    def _get_audit_event(self, event_id: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT *
            FROM audit_events
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (event_id, self.organization_id, self.environment_id),
        ).fetchone()

    def create_chaos_experiment(
        self,
        body: ChaosExperimentCreateRequest,
        *,
        created_by: str,
        allow_production_targets: bool = False,
    ) -> Row:
        """Create a guarded chaos experiment definition."""

        if _is_production_chaos_target(body) and not allow_production_targets:
            raise ChaosExperimentValidationError("Production chaos targets require an explicit feature flag.")
        now = utc_now_iso()
        experiment_id = generate_id("chaos")
        self.connection.execute(
            """
            INSERT INTO chaos_experiments (
                id, organization_id, environment_id, name, fault_type,
                target_type, target_id, blast_radius_json, guardrails_json,
                status, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                self.organization_id,
                self.environment_id,
                body.name,
                body.fault_type,
                body.target_type,
                body.target_id,
                json.dumps(body.blast_radius, sort_keys=True, separators=(",", ":")),
                json.dumps(body.guardrails, sort_keys=True, separators=(",", ":")),
                body.status,
                created_by,
                now,
                now,
            ),
        )
        row = self.get_chaos_experiment(experiment_id)
        if row is None:
            raise ChaosExperimentNotFoundError("Created chaos experiment could not be loaded.")
        return row

    def list_chaos_experiments(
        self,
        *,
        status: str | None = None,
        target_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List chaos experiments in tenant scope."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if status:
            clauses.append("status = ?")
            values.append(status)
        if target_type:
            clauses.append("target_type = ?")
            values.append(target_type)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT *
            FROM chaos_experiments
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def get_chaos_experiment(self, experiment_id: str) -> Row | None:
        """Get a chaos experiment in tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM chaos_experiments
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (experiment_id, self.organization_id, self.environment_id),
        ).fetchone()

    def create_chaos_run(self, experiment_id: str, body: ChaosRunCreateRequest) -> Row:
        """Start and finish a deterministic demo chaos run."""

        experiment = self.get_chaos_experiment(experiment_id)
        if experiment is None:
            raise ChaosExperimentNotFoundError("Chaos experiment not found.")
        guardrails = json.loads(experiment["guardrails_json"])
        evaluation = evaluate_chaos_run(guardrails, body.observed_metrics)
        now = utc_now_iso()
        run_id = generate_id("chaosrun")
        result = {
            "guardrail_breached": evaluation.guardrail_breached,
            "breached_guardrails": evaluation.breached_guardrails,
            "observed_metrics": evaluation.observed_metrics,
            "fault_type": experiment["fault_type"],
            "target_type": experiment["target_type"],
            "target_id": experiment["target_id"],
        }
        self.connection.execute(
            """
            INSERT INTO chaos_runs (
                id, experiment_id, status, started_at, finished_at, result_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                experiment_id,
                evaluation.status,
                now,
                now,
                json.dumps(result, sort_keys=True, separators=(",", ":")),
            ),
        )
        row = self.get_chaos_run(run_id)
        if row is None:
            raise ChaosRunNotFoundError("Created chaos run could not be loaded.")
        return row

    def stop_chaos_run(self, run_id: str) -> Row:
        """Stop a chaos run."""

        run = self.get_chaos_run(run_id)
        if run is None:
            raise ChaosRunNotFoundError("Chaos run not found.")
        result = json.loads(run["result_json"])
        result["stopped_by_user"] = True
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE chaos_runs
            SET status = ?,
                finished_at = ?,
                result_json = ?
            WHERE id = ?
            """,
            ("stopped", now, json.dumps(result, sort_keys=True, separators=(",", ":")), run_id),
        )
        row = self.get_chaos_run(run_id)
        if row is None:
            raise ChaosRunNotFoundError("Chaos run not found.")
        return row

    def get_chaos_run(self, run_id: str) -> Row | None:
        """Get a chaos run in tenant scope."""

        return self.connection.execute(
            """
            SELECT r.*
            FROM chaos_runs r
            JOIN chaos_experiments e ON e.id = r.experiment_id
            WHERE r.id = ?
              AND e.organization_id = ?
              AND e.environment_id = ?
            """,
            (run_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_chaos_runs(self, experiment_id: str) -> list[Row]:
        """List runs for a chaos experiment."""

        if self.get_chaos_experiment(experiment_id) is None:
            raise ChaosExperimentNotFoundError("Chaos experiment not found.")
        return self.connection.execute(
            """
            SELECT *
            FROM chaos_runs
            WHERE experiment_id = ?
            ORDER BY started_at DESC, id DESC
            """,
            (experiment_id,),
        ).fetchall()

    def create_rollout(self, body: RolloutCreateRequest, *, created_by: str) -> Row:
        """Create a staged rollout and initial event."""

        now = utc_now_iso()
        rollout_id = generate_id("rollout")
        self.connection.execute(
            """
            INSERT INTO rollouts (
                id, organization_id, environment_id, name, target_type,
                target_id, strategy, status, current_stage, config_json,
                created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rollout_id,
                self.organization_id,
                self.environment_id,
                body.name,
                body.target_type,
                body.target_id,
                body.strategy,
                "ready",
                0,
                json.dumps(body.config, sort_keys=True, separators=(",", ":")),
                created_by,
                now,
                now,
            ),
        )
        self._record_rollout_event(
            rollout_id,
            stage=0,
            decision="created",
            metrics={"strategy": body.strategy, "config": body.config},
            created_at=now,
        )
        row = self.get_rollout(rollout_id)
        if row is None:
            raise RolloutNotFoundError("Created rollout could not be loaded.")
        return row

    def list_rollouts(
        self,
        *,
        status: str | None = None,
        target_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List rollouts in tenant scope."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if status:
            clauses.append("status = ?")
            values.append(status)
        if target_type:
            clauses.append("target_type = ?")
            values.append(target_type)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT *
            FROM rollouts
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC, created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def get_rollout(self, rollout_id: str) -> Row | None:
        """Get a rollout in tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM rollouts
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (rollout_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_rollout_events(self, rollout_id: str) -> list[Row]:
        """List rollout events."""

        if self.get_rollout(rollout_id) is None:
            raise RolloutNotFoundError("Rollout not found.")
        return self.connection.execute(
            """
            SELECT *
            FROM rollout_events
            WHERE rollout_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (rollout_id,),
        ).fetchall()

    def advance_rollout(self, rollout_id: str, body: RolloutAdvanceRequest) -> Row:
        """Advance a rollout when gates allow it."""

        rollout = self.get_rollout(rollout_id)
        if rollout is None:
            raise RolloutNotFoundError("Rollout not found.")
        config = json.loads(rollout["config_json"])
        gates = dict(config.get("gates") or {})
        signals = {
            **self._rollout_signals(rollout),
            **body.metrics,
        }
        evaluation = evaluate_rollout_gates(gates, signals)
        current_stage = int(rollout["current_stage"])
        now = utc_now_iso()
        if evaluation.decision == "blocked":
            metrics = {
                **evaluation.metrics,
                "blocked_reasons": evaluation.blocked_reasons,
            }
            self.connection.execute(
                """
                UPDATE rollouts
                SET status = ?,
                    updated_at = ?
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                ("blocked", now, rollout_id, self.organization_id, self.environment_id),
            )
            self._record_rollout_event(
                rollout_id,
                stage=current_stage,
                decision="blocked",
                metrics=metrics,
                created_at=now,
            )
            row = self.get_rollout(rollout_id)
            if row is None:
                raise RolloutNotFoundError("Rollout not found.")
            return row

        stages = _rollout_stages(config, strategy=rollout["strategy"])
        next_stage = _next_rollout_stage(stages, current_stage)
        status = "completed" if next_stage >= stages[-1] else "running"
        self.connection.execute(
            """
            UPDATE rollouts
            SET status = ?,
                current_stage = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (status, next_stage, now, rollout_id, self.organization_id, self.environment_id),
        )
        self._record_rollout_event(
            rollout_id,
            stage=next_stage,
            decision="advanced",
            metrics={
                **evaluation.metrics,
                "from_stage": current_stage,
                "to_stage": next_stage,
            },
            created_at=now,
        )
        row = self.get_rollout(rollout_id)
        if row is None:
            raise RolloutNotFoundError("Rollout not found.")
        return row

    def rollback_rollout(self, rollout_id: str, body: RolloutRollbackRequest) -> Row:
        """Rollback a rollout to stage zero."""

        rollout = self.get_rollout(rollout_id)
        if rollout is None:
            raise RolloutNotFoundError("Rollout not found.")
        from_stage = int(rollout["current_stage"])
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE rollouts
            SET status = ?,
                current_stage = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            ("rolled_back", 0, now, rollout_id, self.organization_id, self.environment_id),
        )
        self._record_rollout_event(
            rollout_id,
            stage=0,
            decision="rolled_back",
            metrics={"reason": body.reason, "from_stage": from_stage},
            created_at=now,
        )
        row = self.get_rollout(rollout_id)
        if row is None:
            raise RolloutNotFoundError("Rollout not found.")
        return row

    def evaluate_rollout_for_current_signals(self, rollout: Row) -> tuple[str, dict[str, object]]:
        """Evaluate a rollout's gates against current persisted signals."""

        config = json.loads(rollout["config_json"])
        gates = dict(config.get("gates") or {})
        signals = self._rollout_signals(rollout)
        evaluation = evaluate_rollout_gates(gates, signals)
        return evaluation.decision, {
            **evaluation.metrics,
            "blocked_reasons": evaluation.blocked_reasons,
        }

    def _rollout_signals(self, rollout: Row) -> dict[str, object]:
        slo_rows = [
            row
            for row in self.list_slos(target_type=rollout["target_type"])
            if row["target_id"] == rollout["target_id"]
        ]
        incidents = [
            row
            for row in self.list_incidents(status=None)
            if row["status"] != "resolved"
        ]
        return {
            "slo_status": slo_rows[0]["status"] if slo_rows else "unknown",
            "policy_deny_rate": 0.0,
            "trust_score": 1000,
            "open_incidents": len(incidents),
        }

    def _record_rollout_event(
        self,
        rollout_id: str,
        *,
        stage: int,
        decision: str,
        metrics: dict[str, object],
        created_at: str | None = None,
    ) -> Row:
        event_id = generate_id("rollevent")
        now = created_at or utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO rollout_events (
                id, rollout_id, stage, decision, metrics_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                rollout_id,
                stage,
                decision,
                json.dumps(metrics, sort_keys=True, separators=(",", ":")),
                now,
            ),
        )
        row = self.connection.execute("SELECT * FROM rollout_events WHERE id = ?", (event_id,)).fetchone()
        if row is None:
            raise RolloutNotFoundError("Rollout event could not be loaded.")
        return row


def slo_objective_response(repository: ObservabilityRepository, row: Row) -> SloObjectiveResponse:
    """Build an SLO objective API response."""

    return SloObjectiveResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        name=row["name"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        sli=row["sli"],
        target_value=float(row["target_value"]),
        window=row["window"],
        status=row["status"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        measurements=[
            slo_measurement_response(measurement)
            for measurement in repository.list_slo_measurements(row["id"])
        ],
    )


def slo_measurement_response(row: Row) -> SloMeasurementResponse:
    """Build an SLO measurement API response."""

    return SloMeasurementResponse(
        id=row["id"],
        slo_id=row["slo_id"],
        value=float(row["value"]),
        good_events=int(row["good_events"]),
        total_events=int(row["total_events"]),
        error_budget_remaining=float(row["error_budget_remaining"]),
        burn_rate=float(row["burn_rate"]),
        status=row["status"],
        metadata=json.loads(row["metadata_json"]),
        measured_at=row["measured_at"],
    )


def cost_budget_response(row: Row) -> CostBudgetResponse:
    """Build a cost budget API response."""

    return CostBudgetResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        period=row["period"],
        amount_limit=float(row["amount_limit"]),
        used_amount=float(row["used_amount"]),
        action_on_breach=row["action_on_breach"],
        breach_action=row["breach_action"],
        status=row["status"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def cost_event_response(row: Row) -> CostEventResponse:
    """Build a cost event API response."""

    return CostEventResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        provider=row["provider"],
        model=row["model"],
        amount=float(row["amount"]),
        units=float(row["units"]),
        correlation_id=row["correlation_id"],
        created_at=row["created_at"],
    )


def cost_dashboard_response(repository: ObservabilityRepository) -> CostDashboardResponse:
    """Build the cost dashboard payload."""

    budgets = [cost_budget_response(row) for row in repository.list_cost_budgets()]
    events = [cost_event_response(row) for row in repository.list_cost_events()]
    by_target: dict[str, float] = {}
    by_provider: dict[str, float] = {}
    by_model: dict[str, float] = {}
    total_amount = 0.0
    for event in events:
        total_amount += event.amount
        target_key = f"{event.target_type}:{event.target_id}"
        by_target[target_key] = round(by_target.get(target_key, 0.0) + event.amount, 6)
        by_provider[event.provider] = round(by_provider.get(event.provider, 0.0) + event.amount, 6)
        by_model[event.model] = round(by_model.get(event.model, 0.0) + event.amount, 6)
    return CostDashboardResponse(
        budgets=budgets,
        events=events,
        total_amount=round(total_amount, 6),
        by_target=by_target,
        by_provider=by_provider,
        by_model=by_model,
    )


def incident_response(repository: ObservabilityRepository, row: Row) -> IncidentResponse:
    """Build an incident API response."""

    return IncidentResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        severity=row["severity"],
        status=row["status"],
        title=row["title"],
        summary=row["summary"],
        owner_user_id=row["owner_user_id"],
        correlation_id=row["correlation_id"],
        source_event_id=row["source_event_id"],
        resolution_note=row["resolution_note"],
        started_at=row["started_at"],
        acknowledged_at=row["acknowledged_at"],
        resolved_at=row["resolved_at"],
        updated_at=row["updated_at"],
        related_event_ids=repository.related_audit_event_ids(row),
    )


def chaos_experiment_response(row: Row) -> ChaosExperimentResponse:
    """Build a chaos experiment API response."""

    return ChaosExperimentResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        name=row["name"],
        fault_type=row["fault_type"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        blast_radius=json.loads(row["blast_radius_json"]),
        guardrails=json.loads(row["guardrails_json"]),
        status=row["status"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def chaos_run_response(row: Row) -> ChaosRunResponse:
    """Build a chaos run API response."""

    return ChaosRunResponse(
        id=row["id"],
        experiment_id=row["experiment_id"],
        status=row["status"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        result=json.loads(row["result_json"]),
    )


def rollout_event_response(row: Row) -> RolloutEventResponse:
    """Build a rollout event API response."""

    return RolloutEventResponse(
        id=row["id"],
        rollout_id=row["rollout_id"],
        stage=int(row["stage"]),
        decision=row["decision"],
        metrics=json.loads(row["metrics_json"]),
        created_at=row["created_at"],
    )


def rollout_response(repository: ObservabilityRepository, row: Row) -> RolloutResponse:
    """Build a rollout API response."""

    return RolloutResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        name=row["name"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        strategy=row["strategy"],
        status=row["status"],
        current_stage=int(row["current_stage"]),
        config=json.loads(row["config_json"]),
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        events=[rollout_event_response(event) for event in repository.list_rollout_events(row["id"])],
    )


def _is_production_chaos_target(body: ChaosExperimentCreateRequest) -> bool:
    production_markers = {
        str(body.target_type).lower(),
        str(body.target_id).lower(),
        str(body.blast_radius.get("environment", "")).lower(),
        str(body.blast_radius.get("target_environment", "")).lower(),
    }
    return "production" in production_markers or "prod" in production_markers


def _rollout_stages(config: dict[str, object], *, strategy: str) -> list[int]:
    raw_stages = config.get("stages")
    if isinstance(raw_stages, list):
        stages = sorted(
            {
                max(1, min(100, int(stage)))
                for stage in raw_stages
                if isinstance(stage, (int, float, str)) and str(stage).strip()
            }
        )
        if stages:
            return stages
    if strategy == "percentage":
        percentage = config.get("percentage", 100)
        try:
            return [max(1, min(100, int(percentage)))]
        except (TypeError, ValueError):
            return [100]
    return [5, 25, 50, 100]


def _next_rollout_stage(stages: list[int], current_stage: int) -> int:
    for stage in stages:
        if stage > current_stage:
            return stage
    return stages[-1]
