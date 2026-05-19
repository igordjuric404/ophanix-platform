"""Observability persistence repositories."""

from __future__ import annotations

import json
import re
from typing import Any
from product_platform.db.postgres import Connection, Row

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
    ObservabilityEvalResultCreateRequest,
    ObservabilityEvalResultResponse,
    ObservabilitySpanCreateRequest,
    ObservabilitySpanResponse,
    ObservabilityTraceAnnotationCreateRequest,
    ObservabilityTraceAnnotationResponse,
    ObservabilityTraceCreateRequest,
    ObservabilityTraceDetailResponse,
    ObservabilityTraceFeedbackCreateRequest,
    ObservabilityTraceFeedbackResponse,
    ObservabilityTraceResponse,
    RolloutAdvanceRequest,
    RolloutCreateRequest,
    RolloutEventResponse,
    RolloutRollbackRequest,
    RolloutResponse,
    SloMeasurementCreateRequest,
    SloMeasurementResponse,
    SloObjectiveCreateRequest,
    SloObjectiveResponse,
    TelemetryDerivationRequest,
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


class ObservabilityTraceNotFoundError(ValueError):
    """Raised when a trace is not visible in tenant scope."""


class ObservabilityRepository:
    """Tenant-scoped observability repository."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create_trace(
        self,
        body: ObservabilityTraceCreateRequest,
        *,
        created_by: str,
        correlation_id: str | None = None,
    ) -> Row:
        """Create or update a first-class trace record."""

        now = utc_now_iso()
        trace_record_id = generate_id("trace")
        started_at = body.started_at or now
        effective_correlation_id = body.correlation_id or correlation_id
        self.connection.execute(
            """
            INSERT INTO observability_traces (
                id, organization_id, environment_id, trace_id, name, status,
                agent_id, runtime_session_id, correlation_id, metadata_json,
                started_at, ended_at, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (organization_id, environment_id, trace_id)
            DO UPDATE SET
                name = EXCLUDED.name,
                status = EXCLUDED.status,
                agent_id = EXCLUDED.agent_id,
                runtime_session_id = EXCLUDED.runtime_session_id,
                correlation_id = COALESCE(EXCLUDED.correlation_id, observability_traces.correlation_id),
                metadata_json = EXCLUDED.metadata_json,
                started_at = EXCLUDED.started_at,
                ended_at = EXCLUDED.ended_at,
                updated_at = EXCLUDED.updated_at
            """,
            (
                trace_record_id,
                self.organization_id,
                self.environment_id,
                body.trace_id,
                body.name,
                body.status,
                body.agent_id,
                body.runtime_session_id,
                effective_correlation_id,
                _dump_json(body.metadata),
                started_at,
                body.ended_at,
                created_by,
                now,
                now,
            ),
        )
        row = self.get_trace(body.trace_id)
        if row is None:
            raise ObservabilityTraceNotFoundError("Created trace could not be loaded.")
        return row

    def list_traces(
        self,
        *,
        status: str | None = None,
        agent_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List first-class trace records in tenant scope."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if status:
            clauses.append("status = ?")
            values.append(status)
        if agent_id:
            clauses.append("agent_id = ?")
            values.append(agent_id)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT *
            FROM observability_traces
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC, started_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def get_trace(self, trace_id: str) -> Row | None:
        """Get one first-class trace record by W3C trace id."""

        return self.connection.execute(
            """
            SELECT *
            FROM observability_traces
            WHERE organization_id = ?
              AND environment_id = ?
              AND trace_id = ?
            """,
            (self.organization_id, self.environment_id, trace_id),
        ).fetchone()

    def create_span(self, trace_id: str, body: ObservabilitySpanCreateRequest) -> Row:
        """Create or update a span inside a first-class trace."""

        trace = self.get_trace(trace_id)
        if trace is None:
            raise ObservabilityTraceNotFoundError("Trace not found.")
        now = utc_now_iso()
        span_id = generate_id("span")
        start_time = body.start_time or now
        self.connection.execute(
            """
            INSERT INTO observability_spans (
                id, trace_record_id, organization_id, environment_id, trace_id,
                span_id, parent_span_id, span_kind, name, status, start_time,
                end_time, latency_ms, resource_type, resource_id, attributes_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (organization_id, environment_id, trace_id, span_id)
            DO UPDATE SET
                parent_span_id = EXCLUDED.parent_span_id,
                span_kind = EXCLUDED.span_kind,
                name = EXCLUDED.name,
                status = EXCLUDED.status,
                start_time = EXCLUDED.start_time,
                end_time = EXCLUDED.end_time,
                latency_ms = EXCLUDED.latency_ms,
                resource_type = EXCLUDED.resource_type,
                resource_id = EXCLUDED.resource_id,
                attributes_json = EXCLUDED.attributes_json
            """,
            (
                span_id,
                trace["id"],
                self.organization_id,
                self.environment_id,
                trace_id,
                body.span_id,
                body.parent_span_id,
                body.span_kind,
                body.name,
                body.status,
                start_time,
                body.end_time,
                body.latency_ms,
                body.resource_type,
                body.resource_id,
                _dump_json(body.attributes),
                now,
            ),
        )
        row = self.get_span(trace_id, body.span_id)
        if row is None:
            raise ObservabilityTraceNotFoundError("Created span could not be loaded.")
        return row

    def get_span(self, trace_id: str, span_id: str) -> Row | None:
        """Get one span in tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM observability_spans
            WHERE organization_id = ?
              AND environment_id = ?
              AND trace_id = ?
              AND span_id = ?
            """,
            (self.organization_id, self.environment_id, trace_id, span_id),
        ).fetchone()

    def list_spans_for_trace(self, trace_id: str) -> list[Row]:
        """List explicit spans for a trace."""

        return self.connection.execute(
            """
            SELECT *
            FROM observability_spans
            WHERE organization_id = ?
              AND environment_id = ?
              AND trace_id = ?
            ORDER BY start_time ASC, id ASC
            """,
            (self.organization_id, self.environment_id, trace_id),
        ).fetchall()

    def create_eval_result(
        self,
        body: ObservabilityEvalResultCreateRequest,
        *,
        created_by: str,
    ) -> Row:
        """Create an eval result linked to a trace and optional span."""

        trace = self.get_trace(body.trace_id)
        now = utc_now_iso()
        eval_id = generate_id("eval")
        self.connection.execute(
            """
            INSERT INTO observability_eval_results (
                id, trace_record_id, organization_id, environment_id, trace_id,
                span_id, dataset_id, dataset_name, evaluator_name, score,
                label, passed, feedback_json, metadata_json, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                eval_id,
                trace["id"] if trace is not None else None,
                self.organization_id,
                self.environment_id,
                body.trace_id,
                body.span_id,
                body.dataset_id,
                body.dataset_name,
                body.evaluator_name,
                body.score,
                body.label,
                None if body.passed is None else int(body.passed),
                _dump_json(body.feedback),
                _dump_json(body.metadata),
                created_by,
                now,
            ),
        )
        row = self.get_eval_result(eval_id)
        if row is None:
            raise ObservabilityTraceNotFoundError("Created eval result could not be loaded.")
        return row

    def get_eval_result(self, eval_result_id: str) -> Row | None:
        """Get one eval result in tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM observability_eval_results
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (eval_result_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_eval_results(
        self,
        *,
        trace_id: str | None = None,
        dataset_id: str | None = None,
        limit: int = 100,
    ) -> list[Row]:
        """List eval results by trace or dataset."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if trace_id:
            clauses.append("trace_id = ?")
            values.append(trace_id)
        if dataset_id:
            clauses.append("dataset_id = ?")
            values.append(dataset_id)
        values.append(limit)
        return self.connection.execute(
            f"""
            SELECT *
            FROM observability_eval_results
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            values,
        ).fetchall()

    def create_trace_annotation(
        self,
        trace_id: str,
        body: ObservabilityTraceAnnotationCreateRequest,
        *,
        created_by: str,
    ) -> Row:
        """Attach an annotation to a trace."""

        trace = self.get_trace(trace_id)
        now = utc_now_iso()
        annotation_id = generate_id("traceann")
        self.connection.execute(
            """
            INSERT INTO observability_trace_annotations (
                id, trace_record_id, organization_id, environment_id, trace_id,
                span_id, annotation_type, body_json, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                annotation_id,
                trace["id"] if trace is not None else None,
                self.organization_id,
                self.environment_id,
                trace_id,
                body.span_id,
                body.annotation_type,
                _dump_json(body.body),
                created_by,
                now,
            ),
        )
        row = self.connection.execute(
            """
            SELECT *
            FROM observability_trace_annotations
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (annotation_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise ObservabilityTraceNotFoundError("Created trace annotation could not be loaded.")
        return row

    def create_trace_feedback(
        self,
        trace_id: str,
        body: ObservabilityTraceFeedbackCreateRequest,
        *,
        created_by: str,
    ) -> Row:
        """Attach feedback to a trace."""

        trace = self.get_trace(trace_id)
        now = utc_now_iso()
        feedback_id = generate_id("tracefb")
        self.connection.execute(
            """
            INSERT INTO observability_trace_feedback (
                id, trace_record_id, organization_id, environment_id, trace_id,
                span_id, rating, body_json, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feedback_id,
                trace["id"] if trace is not None else None,
                self.organization_id,
                self.environment_id,
                trace_id,
                body.span_id,
                body.rating,
                _dump_json(body.body),
                created_by,
                now,
            ),
        )
        row = self.connection.execute(
            """
            SELECT *
            FROM observability_trace_feedback
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (feedback_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise ObservabilityTraceNotFoundError("Created trace feedback could not be loaded.")
        return row

    def list_trace_annotations(self, trace_id: str) -> list[Row]:
        """List annotations for a trace."""

        return self.connection.execute(
            """
            SELECT *
            FROM observability_trace_annotations
            WHERE organization_id = ?
              AND environment_id = ?
              AND trace_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (self.organization_id, self.environment_id, trace_id),
        ).fetchall()

    def list_trace_feedback(self, trace_id: str) -> list[Row]:
        """List feedback entries for a trace."""

        return self.connection.execute(
            """
            SELECT *
            FROM observability_trace_feedback
            WHERE organization_id = ?
              AND environment_id = ?
              AND trace_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (self.organization_id, self.environment_id, trace_id),
        ).fetchall()

    def get_trace_detail(self, trace_id: str) -> ObservabilityTraceDetailResponse | None:
        """Build a trace detail by combining first-class and linked runtime evidence."""

        trace_id = trace_id.strip().lower()
        trace_row = self.get_trace(trace_id)
        span_rows = self.list_spans_for_trace(trace_id)
        runtime_sessions = [_runtime_session_link_response(row) for row in self._linked_runtime_sessions(trace_id)]
        runtime_actions = [_runtime_action_link_response(row) for row in self._linked_runtime_actions(trace_id)]
        tool_actions = [_tool_runtime_action_link_response(row) for row in self._linked_tool_runtime_actions(trace_id)]
        mcp_calls = [_mcp_tool_call_link_response(row) for row in self._linked_mcp_tool_calls(trace_id)]
        eval_rows = self.list_eval_results(trace_id=trace_id)
        annotation_rows = self.list_trace_annotations(trace_id)
        feedback_rows = self.list_trace_feedback(trace_id)
        if (
            trace_row is None
            and not span_rows
            and not runtime_sessions
            and not runtime_actions
            and not tool_actions
            and not mcp_calls
            and not eval_rows
            and not annotation_rows
            and not feedback_rows
        ):
            return None

        spans = [observability_span_response(row) for row in span_rows]
        spans.extend(
            _synthetic_spans(
                trace_id=trace_id,
                existing_span_ids={span.span_id for span in spans},
                runtime_sessions=runtime_sessions,
                runtime_actions=runtime_actions,
                tool_actions=tool_actions,
                mcp_calls=mcp_calls,
            )
        )
        linked_artifacts = self._linked_artifacts_for_trace(
            trace_id=trace_id,
            trace_row=trace_row,
            spans=spans,
            runtime_sessions=runtime_sessions,
            runtime_actions=runtime_actions,
            tool_actions=tool_actions,
            mcp_calls=mcp_calls,
            eval_rows=eval_rows,
        )
        trace = (
            observability_trace_response(trace_row)
            if trace_row is not None
            else _synthetic_trace_response(
                organization_id=self.organization_id,
                environment_id=self.environment_id,
                trace_id=trace_id,
                runtime_sessions=runtime_sessions,
                runtime_actions=runtime_actions,
                tool_actions=tool_actions,
                mcp_calls=mcp_calls,
                spans=spans,
                eval_rows=eval_rows,
            )
        )
        correlation_ids = _correlation_ids(trace, runtime_sessions, runtime_actions, tool_actions, mcp_calls)
        policy_evaluations = [
            _policy_evaluation_link_response(row)
            for row in self._linked_policy_evaluations_by_correlation_ids(correlation_ids)
        ]
        timeline = _trace_timeline(
            spans=spans,
            runtime_sessions=runtime_sessions,
            runtime_actions=runtime_actions,
            tool_actions=tool_actions,
            mcp_calls=mcp_calls,
            eval_results=[observability_eval_result_response(row) for row in eval_rows],
        )
        return ObservabilityTraceDetailResponse(
            trace=trace,
            spans=spans,
            runtime_sessions=runtime_sessions,
            runs=runtime_sessions,
            runtime_actions=runtime_actions,
            tool_runtime_actions=tool_actions,
            mcp_tool_calls=mcp_calls,
            policy_evaluations=policy_evaluations,
            eval_results=[observability_eval_result_response(row) for row in eval_rows],
            annotations=[observability_trace_annotation_response(row) for row in annotation_rows],
            feedback=[observability_trace_feedback_response(row) for row in feedback_rows],
            artifacts=linked_artifacts,
            timeline=timeline,
        )

    def _linked_runtime_sessions(self, trace_id: str) -> list[Row]:
        return self.connection.execute(
            """
            SELECT s.*, a.name AS agent_name
            FROM runtime_sessions s
            LEFT JOIN agents a ON a.id = s.agent_id
            WHERE s.organization_id = ?
              AND s.environment_id = ?
              AND s.trace_id = ?
            ORDER BY s.started_at ASC, s.id ASC
            """,
            (self.organization_id, self.environment_id, trace_id),
        ).fetchall()

    def _linked_runtime_actions(self, trace_id: str) -> list[Row]:
        return self.connection.execute(
            """
            SELECT a.*
            FROM runtime_actions a
            JOIN runtime_sessions s ON s.id = a.session_id
            WHERE s.organization_id = ?
              AND s.environment_id = ?
              AND (a.trace_id = ? OR s.trace_id = ?)
            ORDER BY a.created_at ASC, a.id ASC
            """,
            (self.organization_id, self.environment_id, trace_id, trace_id),
        ).fetchall()

    def _linked_tool_runtime_actions(self, trace_id: str) -> list[Row]:
        return self.connection.execute(
            """
            SELECT *
            FROM tool_runtime_actions
            WHERE organization_id = ?
              AND environment_id = ?
              AND trace_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (self.organization_id, self.environment_id, trace_id),
        ).fetchall()

    def _linked_mcp_tool_calls(self, trace_id: str) -> list[Row]:
        return self.connection.execute(
            """
            SELECT *
            FROM mcp_tool_calls
            WHERE organization_id = ?
              AND environment_id = ?
              AND trace_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (self.organization_id, self.environment_id, trace_id),
        ).fetchall()

    def _linked_policy_evaluations_by_correlation_ids(self, correlation_ids: list[str]) -> list[Row]:
        if not correlation_ids:
            return []
        placeholders = ", ".join("?" for _ in correlation_ids)
        values: list[object] = [self.organization_id, self.environment_id, *correlation_ids]
        return self.connection.execute(
            f"""
            SELECT *
            FROM policy_evaluations
            WHERE organization_id = ?
              AND environment_id = ?
              AND correlation_id IN ({placeholders})
            ORDER BY created_at ASC, id ASC
            """,
            values,
        ).fetchall()

    def _linked_artifacts_for_trace(
        self,
        *,
        trace_id: str,
        trace_row: Row | None,
        spans: list[ObservabilitySpanResponse],
        runtime_sessions: list[dict[str, Any]],
        runtime_actions: list[dict[str, Any]],
        tool_actions: list[dict[str, Any]],
        mcp_calls: list[dict[str, Any]],
        eval_rows: list[Row],
    ) -> list[dict[str, Any]]:
        targets: dict[str, set[str]] = {
            "runtime_session": {str(row["id"]) for row in runtime_sessions},
            "runtime_action": {str(row["id"]) for row in runtime_actions},
            "tool_runtime_action": {str(row["id"]) for row in tool_actions},
            "mcp_tool_call": {str(row["id"]) for row in mcp_calls},
            "observability_trace": {trace_id},
            "observability_span": {span.id for span in spans} | {span.span_id for span in spans},
            "observability_eval_result": {str(row["id"]) for row in eval_rows},
        }
        if trace_row is not None:
            targets["observability_trace"].add(str(trace_row["id"]))
        return _linked_artifacts_by_targets(
            self.connection,
            organization_id=self.organization_id,
            environment_id=self.environment_id,
            targets=targets,
        )

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
                measured_at, source, source_resource_type, source_resource_id,
                trace_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                body.source,
                body.source_resource_type,
                body.source_resource_id,
                body.trace_id,
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
                provider, model, amount, units, correlation_id, source,
                source_resource_type, source_resource_id, trace_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                body.source,
                body.source_resource_type,
                body.source_resource_id,
                body.trace_id,
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
                source, source_resource_type, source_resource_id, trace_id,
                resolution_note, started_at, acknowledged_at, resolved_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                body.source,
                body.source_resource_type,
                body.source_resource_id,
                body.trace_id,
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
                source="audit_event",
                source_resource_type="audit_event",
                source_resource_id=event["id"],
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

    def derive_telemetry_signals(self, body: TelemetryDerivationRequest) -> dict[str, Any]:
        """Derive SLO, cost, and incident records from persisted runtime telemetry."""

        tool_actions = self._telemetry_tool_runtime_actions(body)
        runtime_actions = self._telemetry_runtime_actions(body)
        measurements: list[Row] = []
        cost_events: list[Row] = []
        incidents: list[Row] = []
        skipped_duplicate_cost_events = 0

        for slo in self.list_slos(
            target_type=body.target_type if body.target_type not in {"tool_runtime_action", "runtime_action"} else None,
            limit=1000,
        ):
            if body.target_id and slo["target_id"] != body.target_id:
                continue
            measurement_body = _slo_measurement_from_runtime_telemetry(slo, tool_actions, runtime_actions)
            if measurement_body is None:
                continue
            measurement = self.create_slo_measurement(slo["id"], measurement_body)
            measurements.append(measurement)
            if body.create_incidents and measurement["status"] in {"critical", "exhausted"}:
                incident = self._create_telemetry_incident_once(
                    severity="critical" if measurement["status"] == "exhausted" else "warning",
                    title=f"SLO threshold breached: {slo['name']}",
                    summary=(
                        f"Runtime telemetry derived {slo['sli']} value {float(measurement['value']):.4f} "
                        f"against target {float(slo['target_value']):.4f}."
                    ),
                    correlation_id=None,
                    source_resource_type="slo_objective",
                    source_resource_id=slo["id"],
                    trace_id=measurement["trace_id"],
                )
                if incident is not None:
                    incidents.append(incident)

        for action in tool_actions:
            cost_body = _cost_event_from_tool_runtime_action(action)
            if cost_body is None:
                continue
            if self._cost_event_source_exists(
                source_resource_type=str(cost_body.source_resource_type),
                source_resource_id=str(cost_body.source_resource_id),
            ):
                skipped_duplicate_cost_events += 1
                continue
            cost_event = self.create_cost_event(cost_body)
            cost_events.append(cost_event)

        if body.create_incidents:
            seen_budget_incidents: set[str] = set()
            for event in cost_events:
                for budget in self._matching_budgets(event["target_type"], event["target_id"]):
                    if budget["status"] != "breached" or budget["id"] in seen_budget_incidents:
                        continue
                    seen_budget_incidents.add(budget["id"])
                    incident = self._create_telemetry_incident_once(
                        severity="critical",
                        title=f"Cost budget breached for {budget['target_type']} {budget['target_id']}",
                        summary=(
                            f"Runtime telemetry cost reached {float(budget['used_amount']):.4f} "
                            f"of {float(budget['amount_limit']):.4f}."
                        ),
                        correlation_id=event["correlation_id"],
                        source_resource_type="cost_budget",
                        source_resource_id=budget["id"],
                        trace_id=event["trace_id"],
                    )
                    if incident is not None:
                        incidents.append(incident)

        return {
            "slo_measurements": measurements,
            "cost_events": cost_events,
            "incidents": incidents,
            "examined_tool_runtime_actions": len(tool_actions),
            "examined_runtime_actions": len(runtime_actions),
            "skipped_duplicate_cost_events": skipped_duplicate_cost_events,
        }

    def _telemetry_tool_runtime_actions(self, body: TelemetryDerivationRequest) -> list[Row]:
        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if body.target_type == "agent" and body.target_id:
            clauses.append("agent_id = ?")
            values.append(body.target_id)
        elif body.target_type in {"tool", "tool_definition"} and body.target_id:
            clauses.append("tool_id = ?")
            values.append(body.target_id)
        elif body.target_type == "tool_runtime_action" and body.target_id:
            clauses.append("id = ?")
            values.append(body.target_id)
        elif body.target_type and body.target_id:
            return []
        if body.created_from:
            clauses.append("created_at >= ?")
            values.append(body.created_from)
        if body.created_to:
            clauses.append("created_at <= ?")
            values.append(body.created_to)
        values.append(body.limit)
        return self.connection.execute(
            f"""
            SELECT *
            FROM tool_runtime_actions
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            values,
        ).fetchall()

    def _telemetry_runtime_actions(self, body: TelemetryDerivationRequest) -> list[Row]:
        clauses = ["s.organization_id = ?", "s.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if body.target_type == "agent" and body.target_id:
            clauses.append("s.agent_id = ?")
            values.append(body.target_id)
        elif body.target_type == "runtime_session" and body.target_id:
            clauses.append("a.session_id = ?")
            values.append(body.target_id)
        elif body.target_type == "runtime_action" and body.target_id:
            clauses.append("a.id = ?")
            values.append(body.target_id)
        elif body.target_type and body.target_id:
            return []
        if body.created_from:
            clauses.append("a.created_at >= ?")
            values.append(body.created_from)
        if body.created_to:
            clauses.append("a.created_at <= ?")
            values.append(body.created_to)
        values.append(body.limit)
        return self.connection.execute(
            f"""
            SELECT
                a.*,
                s.agent_id AS agent_id,
                s.trace_id AS session_trace_id,
                s.span_id AS session_span_id
            FROM runtime_actions a
            JOIN runtime_sessions s ON s.id = a.session_id
            WHERE {' AND '.join(clauses)}
            ORDER BY a.created_at ASC, a.id ASC
            LIMIT ?
            """,
            values,
        ).fetchall()

    def _cost_event_source_exists(self, *, source_resource_type: str, source_resource_id: str) -> bool:
        return self.connection.execute(
            """
            SELECT id
            FROM cost_events
            WHERE organization_id = ?
              AND environment_id = ?
              AND source = 'runtime_telemetry'
              AND source_resource_type = ?
              AND source_resource_id = ?
            LIMIT 1
            """,
            (self.organization_id, self.environment_id, source_resource_type, source_resource_id),
        ).fetchone() is not None

    def _create_telemetry_incident_once(
        self,
        *,
        severity: str,
        title: str,
        summary: str,
        correlation_id: str | None,
        source_resource_type: str,
        source_resource_id: str,
        trace_id: str | None,
    ) -> Row | None:
        existing = self.connection.execute(
            """
            SELECT *
            FROM incidents
            WHERE organization_id = ?
              AND environment_id = ?
              AND source = 'runtime_telemetry'
              AND source_resource_type = ?
              AND source_resource_id = ?
              AND status <> 'resolved'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
            """,
            (self.organization_id, self.environment_id, source_resource_type, source_resource_id),
        ).fetchone()
        if existing is not None:
            return None
        return self.create_incident(
            IncidentCreateRequest(
                severity=severity,
                title=title,
                summary=summary,
                correlation_id=correlation_id,
                source="runtime_telemetry",
                source_resource_type=source_resource_type,
                source_resource_id=source_resource_id,
                trace_id=trace_id,
            )
        )

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


def observability_trace_response(row: Row) -> ObservabilityTraceResponse:
    """Build a trace API response."""

    return ObservabilityTraceResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        trace_id=row["trace_id"],
        name=row["name"],
        status=row["status"],
        agent_id=row["agent_id"],
        runtime_session_id=row["runtime_session_id"],
        correlation_id=row["correlation_id"],
        metadata=_load_json(row["metadata_json"]),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def observability_span_response(row: Row) -> ObservabilitySpanResponse:
    """Build a trace span API response."""

    return ObservabilitySpanResponse(
        id=row["id"],
        trace_id=row["trace_id"],
        span_id=row["span_id"],
        parent_span_id=row["parent_span_id"],
        span_kind=row["span_kind"],
        name=row["name"],
        status=row["status"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        latency_ms=row["latency_ms"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        attributes=_load_json(row["attributes_json"]),
        created_at=row["created_at"],
    )


def observability_eval_result_response(row: Row) -> ObservabilityEvalResultResponse:
    """Build an eval result API response."""

    return ObservabilityEvalResultResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        trace_id=row["trace_id"],
        span_id=row["span_id"],
        dataset_id=row["dataset_id"],
        dataset_name=row["dataset_name"],
        evaluator_name=row["evaluator_name"],
        score=float(row["score"]) if row["score"] is not None else None,
        label=row["label"],
        passed=bool(row["passed"]) if row["passed"] is not None else None,
        feedback=_load_json(row["feedback_json"]),
        metadata=_load_json(row["metadata_json"]),
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def observability_trace_annotation_response(row: Row) -> ObservabilityTraceAnnotationResponse:
    """Build a trace annotation API response."""

    return ObservabilityTraceAnnotationResponse(
        id=row["id"],
        trace_id=row["trace_id"],
        span_id=row["span_id"],
        annotation_type=row["annotation_type"],
        body=_load_json(row["body_json"]),
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def observability_trace_feedback_response(row: Row) -> ObservabilityTraceFeedbackResponse:
    """Build a trace feedback API response."""

    return ObservabilityTraceFeedbackResponse(
        id=row["id"],
        trace_id=row["trace_id"],
        span_id=row["span_id"],
        rating=row["rating"],
        body=_load_json(row["body_json"]),
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def _runtime_session_link_response(row: Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "organization_id": row["organization_id"],
        "environment_id": row["environment_id"],
        "agent_id": row["agent_id"],
        "agent_name": row["agent_name"],
        "state": row["state"],
        "ring": row["ring"],
        "sponsor_user_id": row["sponsor_user_id"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "metadata": _load_json(row["metadata_json"]),
        "trace_id": row["trace_id"],
        "span_id": row["span_id"],
        "parent_span_id": row["parent_span_id"],
        "traceparent": row["traceparent"],
        "tracestate": row["tracestate"],
        "baggage": row["baggage"],
    }


def _runtime_action_link_response(row: Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "action_name": row["action_name"],
        "resource_type": row["resource_type"],
        "required_ring": row["required_ring"],
        "decision": row["decision"],
        "reason": row["reason"],
        "latency_ms": row["latency_ms"],
        "correlation_id": row["correlation_id"],
        "trace_id": row["trace_id"],
        "span_id": row["span_id"],
        "parent_span_id": row["parent_span_id"],
        "traceparent": row["traceparent"],
        "tracestate": row["tracestate"],
        "baggage": row["baggage"],
        "created_at": row["created_at"],
    }


def _tool_runtime_action_link_response(row: Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "organization_id": row["organization_id"],
        "environment_id": row["environment_id"],
        "request_id": row["request_id"],
        "correlation_id": row["correlation_id"],
        "trace_id": row["trace_id"],
        "span_id": row["span_id"],
        "parent_span_id": row["parent_span_id"],
        "traceparent": row["traceparent"],
        "tracestate": row["tracestate"],
        "baggage": row["baggage"],
        "agent_id": row["agent_id"],
        "credential_id": row["credential_id"],
        "tool_id": row["tool_id"],
        "permission_id": row["permission_id"],
        "decision_id": row["decision_id"],
        "action_status": row["action_status"],
        "reason_code": row["reason_code"],
        "upstream_status_code": row["upstream_status_code"],
        "latency_ms": float(row["latency_ms"]) if row["latency_ms"] is not None else None,
        "payload_summary": _load_json(row["payload_summary_json"]),
        "response_summary": _load_json(row["response_summary_json"], default=None),
        "redaction_applied": bool(row["redaction_applied"]),
        "error_code": row["error_code"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _mcp_tool_call_link_response(row: Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "organization_id": row["organization_id"],
        "environment_id": row["environment_id"],
        "server_id": row["server_id"],
        "tool_id": row["tool_id"],
        "source_agent_id": row["source_agent_id"],
        "params_summary": _load_json(row["params_summary_json"]),
        "decision": row["decision"],
        "reason": row["reason"],
        "matched_policy_id": row["matched_policy_id"],
        "matched_policy_version_id": row["matched_policy_version_id"],
        "policy_binding_id": row["policy_binding_id"] if "policy_binding_id" in row.keys() else None,
        "policy_action": row["policy_action"] if "policy_action" in row.keys() else None,
        "policy_reason": row["policy_reason"] if "policy_reason" in row.keys() else None,
        "policy_matched_rule": row["policy_matched_rule"] if "policy_matched_rule" in row.keys() else None,
        "trust_threshold_id": row["trust_threshold_id"],
        "trust_score": row["trust_score"],
        "gateway_stage": row["gateway_stage"],
        "response": _load_json(row["response_json"], default=None),
        "sanitizer_action": row["sanitizer_action"],
        "latency_ms": row["latency_ms"],
        "correlation_id": row["correlation_id"],
        "trace_id": row["trace_id"],
        "span_id": row["span_id"],
        "parent_span_id": row["parent_span_id"],
        "traceparent": row["traceparent"],
        "tracestate": row["tracestate"],
        "baggage": row["baggage"],
        "created_at": row["created_at"],
    }


def _policy_evaluation_link_response(row: Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "organization_id": row["organization_id"],
        "environment_id": row["environment_id"],
        "policy_id": row["policy_id"],
        "policy_version_id": row["policy_version_id"],
        "binding_id": row["binding_id"],
        "binding_mode": row["binding_mode"],
        "agent_id": row["agent_id"],
        "target_type": row["target_type"],
        "target_id": row["target_id"],
        "action": row["action"],
        "resource_type": row["resource_type"],
        "resource_id": row["resource_id"],
        "context": _load_json(row["context_json"]),
        "decision": row["decision"],
        "policy_action": row["policy_action"],
        "matched_rule": row["matched_rule"],
        "reason": row["reason"],
        "latency_ms": float(row["latency_ms"]),
        "mode": row["mode"],
        "correlation_id": row["correlation_id"],
        "backend": row["backend"],
        "error": bool(row["error"]),
        "audit_preview": _load_json(row["audit_preview_json"]),
        "created_at": row["created_at"],
    }


def _linked_artifacts_by_targets(
    connection: Connection,
    *,
    organization_id: str,
    environment_id: str,
    targets: dict[str, set[str]],
) -> list[dict[str, Any]]:
    artifacts: dict[str, dict[str, Any]] = {}
    for target_type, target_ids in targets.items():
        clean_ids = sorted(target_id for target_id in target_ids if target_id)
        if not clean_ids:
            continue
        placeholders = ", ".join("?" for _ in clean_ids)
        rows = connection.execute(
            f"""
            SELECT
                a.id, a.organization_id, a.environment_id, a.artifact_type, a.name,
                a.content_type, a.storage_uri, a.checksum, a.digest_algorithm,
                a.size_bytes, a.retention_policy, a.redaction_classification,
                a.provenance_json, a.created_by, a.created_at,
                l.id AS link_id, l.target_type, l.target_id, l.link_type,
                l.created_at AS link_created_at
            FROM artifact_links l
            JOIN artifacts a ON a.id = l.artifact_id
            WHERE a.organization_id = ?
              AND a.environment_id = ?
              AND l.target_type = ?
              AND l.target_id IN ({placeholders})
            ORDER BY a.created_at DESC, l.created_at ASC, l.id ASC
            """,
            [organization_id, environment_id, target_type, *clean_ids],
        ).fetchall()
        for row in rows:
            artifact = artifacts.setdefault(
                row["id"],
                {
                    "id": row["id"],
                    "organization_id": row["organization_id"],
                    "environment_id": row["environment_id"],
                    "artifact_type": row["artifact_type"],
                    "name": row["name"],
                    "content_type": row["content_type"],
                    "storage_uri": row["storage_uri"],
                    "checksum": row["checksum"],
                    "digest_algorithm": row["digest_algorithm"],
                    "size_bytes": row["size_bytes"],
                    "retention_policy": row["retention_policy"],
                    "redaction_classification": row["redaction_classification"],
                    "provenance": _load_json(row["provenance_json"]),
                    "created_by": row["created_by"],
                    "created_at": row["created_at"],
                    "links": [],
                },
            )
            artifact["links"].append(
                {
                    "id": row["link_id"],
                    "artifact_id": row["id"],
                    "target_type": row["target_type"],
                    "target_id": row["target_id"],
                    "link_type": row["link_type"],
                    "created_at": row["link_created_at"],
                }
            )
    priority = {
        "tool_runtime_action": 0,
        "runtime_action": 1,
        "runtime_session": 2,
        "mcp_tool_call": 3,
        "observability_trace": 4,
        "observability_span": 5,
        "observability_eval_result": 6,
    }
    for artifact in artifacts.values():
        artifact["links"].sort(key=lambda link: (priority.get(str(link["target_type"]), 100), str(link["created_at"])))
    return sorted(artifacts.values(), key=lambda artifact: (str(artifact["created_at"]), str(artifact["id"])), reverse=True)


def _synthetic_trace_response(
    *,
    organization_id: str,
    environment_id: str,
    trace_id: str,
    runtime_sessions: list[dict[str, Any]],
    runtime_actions: list[dict[str, Any]],
    tool_actions: list[dict[str, Any]],
    mcp_calls: list[dict[str, Any]],
    spans: list[ObservabilitySpanResponse],
    eval_rows: list[Row],
) -> ObservabilityTraceResponse:
    timestamps = [
        *(str(row.get("started_at")) for row in runtime_sessions if row.get("started_at")),
        *(str(row.get("created_at")) for row in runtime_actions if row.get("created_at")),
        *(str(row.get("created_at")) for row in tool_actions if row.get("created_at")),
        *(str(row.get("created_at")) for row in mcp_calls if row.get("created_at")),
        *(span.start_time for span in spans if span.start_time),
        *(row["created_at"] for row in eval_rows),
    ]
    started_at = min(timestamps) if timestamps else utc_now_iso()
    updated_at = max(timestamps) if timestamps else started_at
    agent_id = _first_present(
        *(row.get("agent_id") for row in runtime_sessions),
        *(row.get("agent_id") for row in tool_actions),
        *(row.get("source_agent_id") for row in mcp_calls),
    )
    status = "error" if _has_error(runtime_actions, tool_actions, mcp_calls) else "ok"
    return ObservabilityTraceResponse(
        id=f"trace:{trace_id}",
        organization_id=organization_id,
        environment_id=environment_id,
        trace_id=trace_id,
        name=f"Runtime trace {trace_id[:8]}",
        status=status,
        agent_id=agent_id,
        runtime_session_id=runtime_sessions[0]["id"] if runtime_sessions else None,
        correlation_id=_first_present(
            *(row.get("correlation_id") for row in runtime_actions),
            *(row.get("correlation_id") for row in tool_actions),
            *(row.get("correlation_id") for row in mcp_calls),
        ),
        metadata={"source": "linked_runtime_evidence"},
        started_at=started_at,
        ended_at=None,
        created_by=None,
        created_at=started_at,
        updated_at=updated_at,
    )


def _synthetic_spans(
    *,
    trace_id: str,
    existing_span_ids: set[str],
    runtime_sessions: list[dict[str, Any]],
    runtime_actions: list[dict[str, Any]],
    tool_actions: list[dict[str, Any]],
    mcp_calls: list[dict[str, Any]],
) -> list[ObservabilitySpanResponse]:
    spans: list[ObservabilitySpanResponse] = []

    def append(record: dict[str, Any], *, kind: str, name: str, status: str, timestamp_key: str) -> None:
        span_id = record.get("span_id")
        if not span_id or span_id in existing_span_ids:
            return
        existing_span_ids.add(span_id)
        timestamp = str(record.get(timestamp_key) or record.get("created_at") or utc_now_iso())
        spans.append(
            ObservabilitySpanResponse(
                id=f"linked:{kind}:{record['id']}",
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=record.get("parent_span_id"),
                span_kind=kind,
                name=name,
                status=status,
                start_time=timestamp,
                end_time=record.get("ended_at"),
                latency_ms=_int_or_none(record.get("latency_ms")),
                resource_type=record.get("resource_type") or kind,
                resource_id=record.get("resource_id") or record["id"],
                attributes={"linked_record_type": kind, "linked_record_id": record["id"]},
                created_at=timestamp,
            )
        )

    for session in runtime_sessions:
        append(session, kind="runtime", name="runtime.session", status=session["state"], timestamp_key="started_at")
    for action in runtime_actions:
        append(action, kind="runtime", name=action["action_name"], status=action["decision"], timestamp_key="created_at")
    for action in tool_actions:
        append(
            action,
            kind="tool",
            name=str(action.get("payload_summary", {}).get("tool") or action.get("tool_id") or "tool.call"),
            status=action["action_status"],
            timestamp_key="created_at",
        )
    for call in mcp_calls:
        append(call, kind="tool", name=str(call.get("tool_id") or "mcp.tool_call"), status=call["decision"], timestamp_key="created_at")
    return spans


def _trace_timeline(
    *,
    spans: list[ObservabilitySpanResponse],
    runtime_sessions: list[dict[str, Any]],
    runtime_actions: list[dict[str, Any]],
    tool_actions: list[dict[str, Any]],
    mcp_calls: list[dict[str, Any]],
    eval_results: list[ObservabilityEvalResultResponse],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for span in spans:
        entries.append(
            {
                "kind": "span",
                "id": span.id,
                "name": span.name,
                "status": span.status,
                "timestamp": span.start_time,
                "span_id": span.span_id,
                "parent_span_id": span.parent_span_id,
            }
        )
    for session in runtime_sessions:
        entries.append(
            {
                "kind": "runtime_session",
                "id": session["id"],
                "name": session.get("agent_name") or session["agent_id"],
                "status": session["state"],
                "timestamp": session["started_at"],
                "span_id": session.get("span_id"),
            }
        )
    for action in runtime_actions:
        entries.append(
            {
                "kind": "runtime_action",
                "id": action["id"],
                "name": action["action_name"],
                "status": action["decision"],
                "timestamp": action["created_at"],
                "span_id": action.get("span_id"),
            }
        )
    for action in tool_actions:
        entries.append(
            {
                "kind": "tool_runtime_action",
                "id": action["id"],
                "name": action.get("tool_id") or action["request_id"],
                "status": action["action_status"],
                "timestamp": action["created_at"],
                "span_id": action.get("span_id"),
            }
        )
    for call in mcp_calls:
        entries.append(
            {
                "kind": "mcp_tool_call",
                "id": call["id"],
                "name": call["tool_id"],
                "status": call["decision"],
                "timestamp": call["created_at"],
                "span_id": call.get("span_id"),
            }
        )
    for result in eval_results:
        entries.append(
            {
                "kind": "eval_result",
                "id": result.id,
                "name": result.evaluator_name,
                "status": "passed" if result.passed else "failed" if result.passed is False else "unknown",
                "timestamp": result.created_at,
                "span_id": result.span_id,
            }
        )
    return sorted(entries, key=lambda entry: (str(entry.get("timestamp") or ""), entry["kind"], entry["id"]))


def _correlation_ids(
    trace: ObservabilityTraceResponse,
    runtime_sessions: list[dict[str, Any]],
    runtime_actions: list[dict[str, Any]],
    tool_actions: list[dict[str, Any]],
    mcp_calls: list[dict[str, Any]],
) -> list[str]:
    values = [
        trace.correlation_id,
        *(row.get("correlation_id") for row in runtime_sessions),
        *(row.get("correlation_id") for row in runtime_actions),
        *(row.get("correlation_id") for row in tool_actions),
        *(row.get("correlation_id") for row in mcp_calls),
    ]
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(str(value))
    return result


def _dump_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _load_json(value: str | None, *, default: Any = None) -> Any:
    if value is None:
        return {} if default is None else default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {} if default is None else default


def _first_present(*values: object) -> str | None:
    for value in values:
        if value is not None and str(value).strip():
            return str(value)
    return None


def _has_error(
    runtime_actions: list[dict[str, Any]],
    tool_actions: list[dict[str, Any]],
    mcp_calls: list[dict[str, Any]],
) -> bool:
    runtime_error = any(row.get("decision") in {"deny", "denied", "blocked"} for row in runtime_actions)
    tool_error = any(
        row.get("action_status") in {"denied", "validation_failed", "upstream_failed", "response_blocked"}
        for row in tool_actions
    )
    mcp_error = any(row.get("decision") in {"deny", "denied", "blocked", "failed"} for row in mcp_calls)
    return runtime_error or tool_error or mcp_error


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _slo_measurement_from_runtime_telemetry(
    slo: Row,
    tool_actions: list[Row],
    runtime_actions: list[Row],
) -> SloMeasurementCreateRequest | None:
    target_type = str(slo["target_type"])
    target_id = str(slo["target_id"])
    matching_tool_actions = [
        row for row in tool_actions if _telemetry_row_matches_target(row, target_type=target_type, target_id=target_id)
    ]
    matching_runtime_actions = [
        row for row in runtime_actions if _telemetry_row_matches_target(row, target_type=target_type, target_id=target_id)
    ]
    sli = str(slo["sli"]).lower()
    record_ids = [
        *(f"tool_runtime_action:{row['id']}" for row in matching_tool_actions),
        *(f"runtime_action:{row['id']}" for row in matching_runtime_actions),
    ]
    if not record_ids:
        return None
    trace_id = _first_present(
        *(_row_value(row, "trace_id") for row in matching_tool_actions),
        *(_row_value(row, "trace_id") for row in matching_runtime_actions),
        *(_row_value(row, "session_trace_id") for row in matching_runtime_actions),
    )
    source_resource_id = f"{slo['id']}:{record_ids[0]}:{record_ids[-1]}:{len(record_ids)}"
    measured_at = max(
        str(_row_value(row, "created_at") or "")
        for row in [*matching_tool_actions, *matching_runtime_actions]
    )
    if "latency" in sli:
        latency_records = [
            row for row in [*matching_tool_actions, *matching_runtime_actions] if _float_or_none(_row_value(row, "latency_ms")) is not None
        ]
        if not latency_records:
            return None
        threshold_ms = _latency_threshold_ms(sli, target_value=float(slo["target_value"]))
        latencies = [float(_row_value(row, "latency_ms")) for row in latency_records]
        good_events = sum(1 for latency in latencies if latency <= threshold_ms)
        total_events = len(latencies)
        metadata = {
            "source": "runtime_telemetry",
            "sli": sli,
            "latency_threshold_ms": threshold_ms,
            "average_latency_ms": round(sum(latencies) / total_events, 3),
            "tool_runtime_action_ids": [row["id"] for row in matching_tool_actions],
            "runtime_action_ids": [row["id"] for row in matching_runtime_actions],
            "data_freshness_at": measured_at,
        }
    else:
        good_events = sum(
            1
            for row in matching_tool_actions
            if str(_row_value(row, "action_status") or "").lower() in {"completed", "allowed", "forwarded"}
        )
        good_events += sum(
            1
            for row in matching_runtime_actions
            if str(_row_value(row, "decision") or "").lower() in {"allow", "allowed", "approved"}
        )
        total_events = len(matching_tool_actions) + len(matching_runtime_actions)
        metadata = {
            "source": "runtime_telemetry",
            "sli": sli,
            "tool_runtime_action_ids": [row["id"] for row in matching_tool_actions],
            "runtime_action_ids": [row["id"] for row in matching_runtime_actions],
            "data_freshness_at": measured_at,
        }
    if total_events <= 0:
        return None
    return SloMeasurementCreateRequest(
        value=round(good_events / total_events, 6),
        good_events=good_events,
        total_events=total_events,
        metadata=metadata,
        measured_at=measured_at or None,
        source="runtime_telemetry",
        source_resource_type="telemetry_window",
        source_resource_id=source_resource_id,
        trace_id=trace_id,
    )


def _cost_event_from_tool_runtime_action(row: Row) -> CostEventCreateRequest | None:
    usage = _extract_model_usage(
        _load_json(_row_value(row, "response_summary_json"), default={}),
        _load_json(_row_value(row, "payload_summary_json"), default={}),
    )
    if usage is None:
        return None
    target_id = _first_present(_row_value(row, "agent_id"), _row_value(row, "tool_id"))
    if target_id is None:
        return None
    amount = _float_or_none(usage.get("amount")) or 0.0
    units = _float_or_none(usage.get("units")) or 0.0
    return CostEventCreateRequest(
        target_type="agent" if _row_value(row, "agent_id") else "tool",
        target_id=target_id,
        provider=str(usage["provider"]),
        model=str(usage["model"]),
        amount=amount,
        units=units,
        correlation_id=_row_value(row, "correlation_id"),
        created_at=_row_value(row, "updated_at") or _row_value(row, "created_at"),
        source="runtime_telemetry",
        source_resource_type="tool_runtime_action",
        source_resource_id=row["id"],
        trace_id=_row_value(row, "trace_id"),
    )


def _extract_model_usage(response_summary: Any, payload_summary: Any) -> dict[str, object] | None:
    candidates = _usage_candidates(response_summary) + _usage_candidates(payload_summary)
    for candidate in candidates:
        provider = _string_value(candidate, "provider", "model_provider", "vendor") or "unknown"
        model = _string_value(candidate, "model", "model_name", "deployment") or "unknown"
        amount = _number_value(
            candidate,
            "cost_usd",
            "amount",
            "total_cost_usd",
            "estimated_cost_usd",
            "cost",
        )
        units = _number_value(candidate, "units", "total_tokens", "tokens")
        if units is None:
            units = sum(
                value
                for value in [
                    _number_value(candidate, "input_tokens", "prompt_tokens"),
                    _number_value(candidate, "output_tokens", "completion_tokens"),
                ]
                if value is not None
            )
        if amount is None and not units:
            continue
        return {
            "provider": provider,
            "model": model,
            "amount": amount or 0.0,
            "units": units or 0.0,
        }
    return None


def _usage_candidates(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    candidates: list[dict[str, Any]] = []
    for key in ("model_usage", "usage", "cost", "token_usage"):
        nested = value.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)
    candidates.append(value)
    return candidates


def _telemetry_row_matches_target(row: Row, *, target_type: str, target_id: str) -> bool:
    normalized_type = target_type.lower()
    if normalized_type == "agent":
        return _row_value(row, "agent_id") == target_id
    if normalized_type in {"tool", "tool_definition"}:
        return _row_value(row, "tool_id") == target_id or _row_value(row, "resource_id") == target_id
    if normalized_type == "runtime_session":
        return _row_value(row, "session_id") == target_id
    if normalized_type in {"tool_runtime_action", "runtime_action"}:
        return _row_value(row, "id") == target_id
    return False


def _latency_threshold_ms(sli: str, *, target_value: float) -> int:
    match = re.search(r"(?:under|lt|lte|below)[_-]?(\d+)(?:ms)?", sli)
    if match:
        return int(match.group(1))
    if target_value > 1:
        return int(target_value)
    return 1000


def _string_value(value: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        raw = value.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return None


def _number_value(value: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        number = _float_or_none(value.get(key))
        if number is not None:
            return number
    return None


def _float_or_none(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _row_value(row: Row, key: str) -> Any:
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        if hasattr(row, "get"):
            return row.get(key)
        return None


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
        source=row["source"],
        source_resource_type=row["source_resource_type"],
        source_resource_id=row["source_resource_id"],
        trace_id=row["trace_id"],
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
        source=row["source"],
        source_resource_type=row["source_resource_type"],
        source_resource_id=row["source_resource_id"],
        trace_id=row["trace_id"],
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
        source=row["source"],
        source_resource_type=row["source_resource_type"],
        source_resource_id=row["source_resource_id"],
        trace_id=row["trace_id"],
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
        if not isinstance(percentage, (int, float, str)):
            return [100]
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
