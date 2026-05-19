"""Repositories for compliance audit exports."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from product_platform.db.postgres import Connection, IntegrityError, Row
from typing import Any

from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.compliance.models import (
    AuditExportRequest,
    AuditExportResponse,
    ComplianceControlResponse,
    ComplianceFrameworkCreateRequest,
    ComplianceFrameworkResponse,
    ComplianceReportAttestationRequest,
    ComplianceReportAttestationResponse,
    ComplianceReportCreateRequest,
    ComplianceReportResponse,
    ComplianceViolationPatchRequest,
    ComplianceViolationResponse,
    ControlMappingCreateRequest,
    ControlMappingResponse,
    EvidenceItemResponse,
    EvidenceRecomputeResponse,
)
from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso


class ComplianceResourceNotFoundError(ValueError):
    """Raised when a compliance resource is outside the tenant scope."""


class DuplicateComplianceResourceError(ValueError):
    """Raised when a compliance resource already exists in the tenant scope."""


class ComplianceViolationNotFoundError(ValueError):
    """Raised when a compliance violation is outside the tenant scope."""


class ComplianceViolationStateError(ValueError):
    """Raised when a violation status transition is invalid."""


class ComplianceReportNotFoundError(ValueError):
    """Raised when a compliance report is outside the tenant scope."""


class ComplianceReportValidationError(ValueError):
    """Raised when a compliance report request is invalid."""


class AuditExportRepository:
    """Repository for audit export metadata."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create(
        self,
        body: AuditExportRequest,
        *,
        actor_id: str,
        event_count: int = 0,
        complete: bool = True,
        completeness_reason: str | None = None,
        chain_proof: dict[str, Any] | None = None,
    ) -> Row:
        export_id = generate_id("audexp")
        artifact_uri = f"audit-export://{export_id}.{body.format}"
        now = utc_now_iso()
        status = "ready" if complete else "partial"
        self.connection.execute(
            """
            INSERT INTO audit_exports (
                id, organization_id, environment_id, filters_json, format, status,
                artifact_uri, event_count, complete, completeness_reason, chain_proof_json,
                created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                export_id,
                self.organization_id,
                self.environment_id,
                json.dumps(_clean_filters(body.filters), sort_keys=True),
                body.format,
                status,
                artifact_uri,
                event_count,
                1 if complete else 0,
                completeness_reason,
                json.dumps(chain_proof or {}, sort_keys=True),
                actor_id,
                now,
            ),
        )
        row = self.connection.execute(
            """
            SELECT *
            FROM audit_exports
            WHERE id = ? AND organization_id = ? AND environment_id = ?
            """,
            (export_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise ValueError("Created audit export could not be loaded.")
        return row


AUDIT_EXPORT_FILTER_FIELDS = {
    "environment_id",
    "event_type",
    "source_component",
    "actor_type",
    "actor_id",
    "agent_id",
    "decision",
    "severity",
    "policy_id",
    "resource_type",
    "resource_id",
    "correlation_id",
    "created_from",
    "created_to",
    "limit",
    "offset",
}
AUDIT_EXPORT_PAGE_SIZE = 1000
AUDIT_EXPORT_MAX_SYNC_EVENTS = 50_000
COMPLIANCE_RECOMPUTE_PAGE_SIZE = 500


class AuditExportValidationError(ValueError):
    """Raised when audit export filters are invalid."""


@dataclass(frozen=True)
class AuditExportEventSet:
    """A fully materialized audit export event set plus completeness metadata."""

    events: list[AuditEventEnvelope]
    filters: dict[str, Any]
    complete: bool
    completeness_reason: str | None
    page_size: int
    max_events: int


def audit_export_query(
    *,
    organization_id: str,
    environment_id: str,
    filters: dict[str, Any],
) -> AuditEventQuery:
    """Build a bounded audit event query from export filters."""

    cleaned = _clean_filters(filters)
    unknown = sorted(set(cleaned) - AUDIT_EXPORT_FILTER_FIELDS)
    if unknown:
        raise AuditExportValidationError(
            "Unsupported audit export filter(s): " + ", ".join(unknown)
        )
    requested_environment_id = cleaned.get("environment_id")
    if requested_environment_id is not None and str(requested_environment_id) != environment_id:
        raise AuditExportValidationError(
            "Audit export environment filter must match the selected request environment."
        )
    return AuditEventQuery(
        organization_id=organization_id,
        environment_id=environment_id,
        event_type=_string_filter(cleaned, "event_type"),
        source_component=_string_filter(cleaned, "source_component"),
        actor_type=_string_filter(cleaned, "actor_type"),
        actor_id=_string_filter(cleaned, "actor_id"),
        agent_id=_string_filter(cleaned, "agent_id"),
        decision=_string_filter(cleaned, "decision"),
        severity=_string_filter(cleaned, "severity"),
        policy_id=_string_filter(cleaned, "policy_id"),
        resource_type=_string_filter(cleaned, "resource_type"),
        resource_id=_string_filter(cleaned, "resource_id"),
        correlation_id=_string_filter(cleaned, "correlation_id"),
        created_from=_string_filter(cleaned, "created_from"),
        created_to=_string_filter(cleaned, "created_to"),
        limit=_int_filter(
            cleaned,
            "limit",
            default=AUDIT_EXPORT_PAGE_SIZE,
            minimum=1,
            maximum=AUDIT_EXPORT_MAX_SYNC_EVENTS,
        ),
        offset=_int_filter(cleaned, "offset", default=0, minimum=0, maximum=1_000_000),
    )


def collect_audit_export_events(
    *,
    audit_repository: AuditEventRepository,
    organization_id: str,
    environment_id: str,
    filters: dict[str, Any],
    page_size: int = AUDIT_EXPORT_PAGE_SIZE,
    max_events: int = AUDIT_EXPORT_MAX_SYNC_EVENTS,
) -> AuditExportEventSet:
    """Page through matching audit events without silently truncating exports."""

    if page_size <= 0:
        raise AuditExportValidationError("page_size must be greater than zero.")
    if max_events <= 0:
        raise AuditExportValidationError("max_events must be greater than zero.")
    cleaned = _clean_filters(filters)
    base_query = audit_export_query(
        organization_id=organization_id,
        environment_id=environment_id,
        filters={**cleaned, "limit": 1},
    )
    requested_limit = (
        _int_filter(cleaned, "limit", default=max_events, minimum=1, maximum=max_events)
        if "limit" in cleaned
        else None
    )
    target_limit = requested_limit or max_events
    start_offset = base_query.offset
    events: list[AuditEventEnvelope] = []
    while len(events) < target_limit:
        remaining = target_limit - len(events)
        query = audit_export_query(
            organization_id=organization_id,
            environment_id=environment_id,
            filters={
                **cleaned,
                "limit": min(page_size, remaining),
                "offset": start_offset + len(events),
            },
        )
        page = audit_repository.query(query)
        events.extend(page)
        if len(page) < query.limit:
            return AuditExportEventSet(
                events=events,
                filters=cleaned,
                complete=True,
                completeness_reason=None,
                page_size=page_size,
                max_events=max_events,
            )
    probe = audit_repository.query(
        audit_export_query(
            organization_id=organization_id,
            environment_id=environment_id,
            filters={**cleaned, "limit": 1, "offset": start_offset + len(events)},
        )
    )
    complete = not probe
    reason = None
    if not complete:
        reason = "requested_limit_reached" if requested_limit is not None else "sync_export_limit_reached"
    return AuditExportEventSet(
        events=events,
        filters=cleaned,
        complete=complete,
        completeness_reason=reason,
        page_size=page_size,
        max_events=max_events,
    )


def audit_export_runtime_links(
    *,
    connection: Connection,
    organization_id: str,
    environment_id: str,
    events: list[AuditEventEnvelope],
) -> list[dict[str, Any]]:
    """Return runtime action links related to exported audit events."""

    correlation_ids = sorted({event.correlation_id for event in events if event.correlation_id})
    if not correlation_ids:
        return []
    placeholders = ", ".join("?" for _ in correlation_ids)
    rows = connection.execute(
        f"""
        SELECT id, request_id, correlation_id, agent_id, tool_id, decision_id,
               action_status, reason_code, error_code, created_at
        FROM tool_runtime_actions
        WHERE organization_id = ?
          AND environment_id = ?
          AND correlation_id IN ({placeholders})
        ORDER BY created_at DESC, id DESC
        """,
        [organization_id, environment_id, *correlation_ids],
    ).fetchall()
    return [_row_dict(row) for row in rows]


def audit_export_content(
    *,
    response: AuditExportResponse,
    events: list[AuditEventEnvelope],
) -> tuple[str, bytes]:
    """Render audit events for an export artifact."""

    hash_metadata = {
        item["event_id"]: item
        for item in response.chain_proof.get("selected_events", [])
        if isinstance(item, dict) and item.get("event_id")
    }
    event_rows = []
    for event in events:
        row = event.model_dump(mode="json")
        if event.id in hash_metadata:
            row["hash_chain"] = hash_metadata[event.id]
        event_rows.append(row)
    if response.format == "json":
        payload = {
            "export": response.model_dump(mode="json"),
            "event_count": len(event_rows),
            "complete": response.complete,
            "completeness_reason": response.completeness_reason,
            "integrity": {
                "chain_proof": response.chain_proof,
            },
            "events": event_rows,
        }
        return "application/json", json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")
    if response.format == "csv":
        return "text/csv", _audit_events_csv(event_rows).encode("utf-8")
    if response.format == "markdown":
        return "text/markdown", _audit_events_markdown(response, event_rows).encode("utf-8")
    raise AuditExportValidationError(f"Unsupported audit export format: {response.format}.")


def audit_export_response(row: Row) -> AuditExportResponse:
    """Serialize an audit export row."""

    return AuditExportResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        filters=json.loads(row["filters_json"] or "{}"),
        format=row["format"],
        status=row["status"],
        artifact_uri=row["artifact_uri"],
        event_count=int(row["event_count"]) if "event_count" in row.keys() else 0,
        complete=bool(row["complete"]) if "complete" in row.keys() else True,
        completeness_reason=row["completeness_reason"]
        if "completeness_reason" in row.keys()
        else None,
        chain_proof=json.loads(row["chain_proof_json"] or "{}")
        if "chain_proof_json" in row.keys()
        else {},
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def _clean_filters(filters: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in filters.items()
        if value is not None and value != ""
    }


def _string_filter(filters: dict[str, Any], key: str) -> str | None:
    value = filters.get(key)
    if value is None:
        return None
    return str(value).strip() or None


def _int_filter(
    filters: dict[str, Any],
    key: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = filters.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise AuditExportValidationError(f"{key} must be an integer.") from exc
    if parsed < minimum or parsed > maximum:
        raise AuditExportValidationError(f"{key} must be between {minimum} and {maximum}.")
    return parsed


def _audit_events_csv(event_rows: list[dict[str, Any]]) -> str:
    fields = [
        "id",
        "organization_id",
        "environment_id",
        "event_type",
        "source_component",
        "actor_type",
        "actor_id",
        "agent_id",
        "resource_type",
        "resource_id",
        "decision",
        "severity",
        "correlation_id",
        "trace_id",
        "policy_id",
        "policy_version_id",
        "trust_delta",
        "payload_json",
        "audit_previous_hash",
        "audit_current_hash",
        "audit_hash_algorithm",
        "created_at",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for event in event_rows:
        row = {field: _csv_safe_cell(event.get(field)) for field in fields}
        row["payload_json"] = _csv_safe_cell(
            json.dumps(event.get("payload_json") or {}, sort_keys=True)
        )
        hash_chain = event.get("hash_chain") if isinstance(event.get("hash_chain"), dict) else {}
        row["audit_previous_hash"] = _csv_safe_cell(hash_chain.get("previous_hash"))
        row["audit_current_hash"] = _csv_safe_cell(hash_chain.get("current_hash"))
        row["audit_hash_algorithm"] = _csv_safe_cell(hash_chain.get("algorithm"))
        writer.writerow(row)
    return output.getvalue()


def _csv_safe_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    stripped = text.lstrip(" \t\r\n")
    if stripped and stripped[0] in {"=", "+", "-", "@"}:
        return "'" + text
    return text


def _audit_events_markdown(
    response: AuditExportResponse,
    event_rows: list[dict[str, Any]],
) -> str:
    lines = [
        f"# Audit Export {response.id}",
        "",
        f"- Format: {response.format}",
        f"- Status: {response.status}",
        f"- Event count: {len(event_rows)}",
        f"- Complete: {'yes' if response.complete else 'no'}",
        f"- Completeness reason: {response.completeness_reason or 'n/a'}",
        f"- Created at: {response.created_at}",
        f"- Hash verification: {response.chain_proof.get('range_verification', {}).get('valid')}",
        f"- Checkpoint: {response.chain_proof.get('checkpoint', {}).get('id') if response.chain_proof.get('checkpoint') else 'n/a'}",
        "",
        "| Created at | Event type | Actor | Resource | Decision | Severity |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for event in event_rows:
        actor = event.get("actor_id") or event.get("actor_type") or ""
        resource = event.get("resource_id") or event.get("resource_type") or ""
        lines.append(
            "| {created_at} | {event_type} | {actor} | {resource} | {decision} | {severity} |".format(
                created_at=event.get("created_at") or "",
                event_type=event.get("event_type") or "",
                actor=actor,
                resource=resource,
                decision=event.get("decision") or "",
                severity=event.get("severity") or "",
            )
        )
    return "\n".join(lines) + "\n"


DEFAULT_FRAMEWORKS = [
    {
        "id": "cf_soc2",
        "name": "SOC 2",
        "version": "2026",
        "description": "Trust Services Criteria evidence mapped from product audit events.",
        "controls": [
            {
                "id": "ctrl_soc2_cc6_6",
                "code": "CC6.6",
                "title": "Policy Enforcement",
                "description": "Policy decisions are recorded and reviewable.",
                "evidence": ["policy_decision"],
                "mappings": [
                    {
                        "event_type": "policy.decision",
                        "source_component": "policy-engine",
                        "evidence_type": "policy_decision",
                    }
                ],
            },
            {
                "id": "ctrl_soc2_cc6_1",
                "code": "CC6.1",
                "title": "Credential Lifecycle",
                "description": "Agent credential issuance and rotation are auditable.",
                "evidence": ["credential_lifecycle"],
                "mappings": [
                    {
                        "event_type": "agent.credential.rotated",
                        "source_component": "agent-registry",
                        "evidence_type": "credential_lifecycle",
                    }
                ],
            },
        ],
    },
    {
        "id": "cf_gdpr",
        "name": "GDPR",
        "version": "Article 32",
        "description": "Security of processing controls for governed AI operations.",
        "controls": [
            {
                "id": "ctrl_gdpr_art32",
                "code": "Art.32",
                "title": "Access Control Evidence",
                "description": "Denied or approved access decisions are traceable.",
                "evidence": ["policy_decision"],
                "mappings": [
                    {
                        "event_type": "policy.decision",
                        "source_component": "policy-engine",
                        "evidence_type": "policy_decision",
                    }
                ],
            }
        ],
    },
    {
        "id": "cf_eu_ai_act",
        "name": "EU AI Act",
        "version": "2026",
        "description": "Operational logging controls for high-risk AI workflows.",
        "controls": [
            {
                "id": "ctrl_eu_ai_logging",
                "code": "LOG-1",
                "title": "Runtime Logging",
                "description": "Runtime and MCP decisions are logged for oversight.",
                "evidence": ["runtime_decision"],
                "mappings": [
                    {
                        "event_type": "runtime.action",
                        "source_component": "runtime-control",
                        "evidence_type": "runtime_decision",
                    },
                    {
                        "event_type": "mcp.proxy.call.denied",
                        "source_component": "mcp-proxy",
                        "evidence_type": "mcp_decision",
                    },
                ],
            }
        ],
    },
    {
        "id": "cf_internal",
        "name": "Internal Governance",
        "version": "demo",
        "description": "Internal demo controls for product governance workflows.",
        "controls": [
            {
                "id": "ctrl_internal_discovery",
                "code": "GOV-1",
                "title": "Discovery Reconciliation",
                "description": "Discovery findings are triaged through audit history.",
                "evidence": ["discovery_finding"],
                "mappings": [
                    {
                        "event_type": "discovery.finding.action",
                        "source_component": "discovery-reconciliation",
                        "evidence_type": "discovery_finding",
                    }
                ],
            }
        ],
    },
]


class ComplianceRepository:
    """Repository for compliance frameworks, controls, mappings, and evidence."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def seed_defaults(self) -> None:
        now = utc_now_iso()
        for framework in DEFAULT_FRAMEWORKS:
            framework_id = self._default_id(framework["id"])
            self.connection.execute(
                """
                INSERT INTO control_frameworks
                    (id, organization_id, name, version, description, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (
                    framework_id,
                    self.organization_id,
                    framework["name"],
                    framework["version"],
                    framework["description"],
                    "active",
                    now,
                ),
            )
            for control in framework["controls"]:
                control_id = self._default_id(control["id"])
                self.connection.execute(
                    """
                    INSERT INTO controls (
                        id, framework_id, control_code, title, description,
                        required_evidence_types_json, owner_user_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        control_id,
                        framework_id,
                        control["code"],
                        control["title"],
                        control["description"],
                        json.dumps(control["evidence"], sort_keys=True),
                        "user_admin",
                    ),
                )
                for mapping in control["mappings"]:
                    mapping_id = generate_id("cmap")
                    self.connection.execute(
                        """
                        INSERT INTO control_mappings (
                            id, control_id, event_type, source_component,
                            predicate_json, evidence_type
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            mapping_id,
                            control_id,
                            mapping["event_type"],
                            mapping.get("source_component"),
                            json.dumps(mapping.get("predicate", {}), sort_keys=True),
                            mapping["evidence_type"],
                        ),
                    )

    def create_framework(self, body: ComplianceFrameworkCreateRequest) -> Row:
        row_id = generate_id("cf")
        try:
            self.connection.execute(
                """
                INSERT INTO control_frameworks
                    (id, organization_id, name, version, description, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    self.organization_id,
                    body.name.strip(),
                    body.version.strip(),
                    body.description.strip(),
                    body.status.strip().lower(),
                    utc_now_iso(),
                ),
            )
        except IntegrityError as exc:
            raise DuplicateComplianceResourceError("Compliance framework already exists.") from exc
        row = self.connection.execute(
            "SELECT * FROM control_frameworks WHERE id = ? AND organization_id = ?",
            (row_id, self.organization_id),
        ).fetchone()
        if row is None:
            raise ComplianceResourceNotFoundError("Created compliance framework could not be loaded.")
        return row

    def list_frameworks(self) -> list[Row]:
        self.seed_defaults()
        return self.connection.execute(
            """
            SELECT *
            FROM control_frameworks
            WHERE organization_id = ?
            ORDER BY name ASC, version ASC
            """,
            (self.organization_id,),
        ).fetchall()

    def list_controls(self, *, framework_id: str | None = None) -> list[Row]:
        self.seed_defaults()
        clauses = ["f.organization_id = ?"]
        values: list[object] = [self.organization_id]
        if framework_id:
            clauses.append("c.framework_id = ?")
            values.append(framework_id)
        return self.connection.execute(
            f"""
            SELECT c.*, f.name AS framework_name
            FROM controls c
            JOIN control_frameworks f ON f.id = c.framework_id
            WHERE {' AND '.join(clauses)}
            ORDER BY f.name ASC, c.control_code ASC
            """,
            values,
        ).fetchall()

    def create_mapping(self, body: ControlMappingCreateRequest) -> Row:
        self.seed_defaults()
        if self._control_row(body.control_id) is None:
            raise ComplianceResourceNotFoundError("Control not found.")
        row_id = generate_id("cmap")
        try:
            self.connection.execute(
                """
                INSERT INTO control_mappings (
                    id, control_id, event_type, source_component, predicate_json, evidence_type
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    body.control_id,
                    body.event_type.strip(),
                    body.source_component.strip() if body.source_component else None,
                    json.dumps(body.predicate, sort_keys=True),
                    body.evidence_type.strip(),
                ),
            )
        except IntegrityError as exc:
            raise DuplicateComplianceResourceError("Control mapping already exists.") from exc
        row = self.connection.execute("SELECT * FROM control_mappings WHERE id = ?", (row_id,)).fetchone()
        if row is None:
            raise ComplianceResourceNotFoundError("Created control mapping could not be loaded.")
        return row

    def list_evidence(self, *, control_id: str | None = None, status: str | None = None) -> list[Row]:
        self.seed_defaults()
        clauses = ["e.organization_id = ?", "e.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if control_id:
            clauses.append("e.control_id = ?")
            values.append(control_id)
        if status:
            clauses.append("e.status = ?")
            values.append(status)
        return self.connection.execute(
            f"""
            SELECT e.*, c.control_code
            FROM evidence_items e
            JOIN controls c ON c.id = e.control_id
            WHERE {' AND '.join(clauses)}
            ORDER BY e.freshness_at DESC, e.id DESC
            """,
            values,
        ).fetchall()

    def recompute_evidence(self) -> EvidenceRecomputeResponse:
        self.seed_defaults()
        started_at = utc_now_iso()
        mappings = self._visible_mappings()
        audit_repository = AuditEventRepository(self.connection)
        scanned = 0
        evidence_count = 0
        refreshed = 0
        checkpoint = audit_repository.latest_checkpoint(
            self.organization_id,
            environment_id=self.environment_id,
        )
        checkpoint_summary = _checkpoint_summary(checkpoint)
        for mapping in mappings:
            for events in self._audit_event_pages(audit_repository, mapping):
                scanned += len(events)
                hash_metadata_by_event = audit_repository.hash_metadata_for_events(
                    [event.id for event in events]
                )
                for event in events:
                    if not _predicate_matches(event, json.loads(mapping["predicate_json"] or "{}")):
                        continue
                    existed = self._evidence_exists(mapping["control_id"], "audit_event", event.id)
                    self._upsert_evidence(
                        mapping,
                        event,
                        hash_metadata=hash_metadata_by_event.get(event.id),
                        checkpoint_summary=checkpoint_summary,
                    )
                    evidence_count += 1
                    if existed:
                        refreshed += 1
        runtime_action_count, runtime_evidence_count, runtime_refreshed = (
            self._recompute_runtime_action_evidence(checkpoint_summary=checkpoint_summary)
        )
        evidence_count += runtime_evidence_count
        refreshed += runtime_refreshed
        self.refresh_violations()
        completed_at = utc_now_iso()
        cursor = {
            "complete": True,
            "page_size": COMPLIANCE_RECOMPUTE_PAGE_SIZE,
            "mapping_count": len(mappings),
            "runtime_action_count": runtime_action_count,
        }
        source_range = {
            "audit_event_source": "audit_events",
            "runtime_action_source": "tool_runtime_actions",
            "created_from": None,
            "created_to": None,
        }
        run_id = self._record_recompute_run(
            status="completed",
            scanned_event_count=scanned,
            evidence_count=evidence_count,
            refreshed_count=refreshed,
            runtime_action_count=runtime_action_count,
            complete=True,
            cursor=cursor,
            source_range=source_range,
            started_at=started_at,
            completed_at=completed_at,
        )
        return EvidenceRecomputeResponse(
            run_id=run_id,
            scanned_event_count=scanned,
            evidence_count=evidence_count,
            refreshed_count=refreshed,
            runtime_action_count=runtime_action_count,
            complete=True,
            cursor=cursor,
            source_range=source_range,
        )

    def refresh_violations(self) -> int:
        """Create or refresh open compliance violations from current evidence and audit history."""

        self.seed_defaults()
        created = 0
        audit_repository = AuditEventRepository(self.connection)
        for mapping in self._visible_mappings():
            for events in self._audit_event_pages(audit_repository, mapping):
                for event in events:
                    if not _predicate_matches(event, json.loads(mapping["predicate_json"] or "{}")):
                        continue
                    if not _event_requires_violation(event):
                        continue
                    if self._upsert_violation(
                        control_id=mapping["control_id"],
                        agent_id=event.agent_id,
                        severity=_event_violation_severity(event),
                        reason=_event_violation_reason(event),
                        source_type="audit_event",
                        source_id=event.id,
                        source_event_id=event.id,
                    ):
                        created += 1

        runtime_control = self._control_by_code("LOG-1")
        if runtime_control is not None:
            for actions in self._runtime_action_pages():
                for action in actions:
                    if not _runtime_action_requires_violation(action):
                        continue
                    if self._upsert_violation(
                        control_id=runtime_control["id"],
                        agent_id=action["agent_id"],
                        severity=_runtime_action_violation_severity(action),
                        reason=_runtime_action_violation_reason(action),
                        source_type="tool_runtime_action",
                        source_id=action["id"],
                        source_event_id=None,
                    ):
                        created += 1

        for row in self._stale_evidence_rows():
            if self._upsert_violation(
                control_id=row["control_id"],
                agent_id=None,
                severity="warning",
                reason=f"Evidence for control {row['control_code']} is stale.",
                source_type="evidence_item",
                source_id=row["id"],
                source_event_id=row["source_id"] if row["source_type"] == "audit_event" else None,
            ):
                created += 1

        for row in self._controls_missing_fresh_evidence():
            if self._upsert_violation(
                control_id=row["id"],
                agent_id=None,
                severity="warning",
                reason=f"Control {row['control_code']} has no fresh evidence.",
                source_type="control",
                source_id=row["id"],
                source_event_id=None,
            ):
                created += 1
        return created

    def list_violations(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        control_id: str | None = None,
        agent_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        self.seed_defaults()
        clauses = ["v.organization_id = ?", "v.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if status:
            clauses.append("v.status = ?")
            values.append(status)
        if severity:
            clauses.append("v.severity = ?")
            values.append(severity)
        if control_id:
            clauses.append("v.control_id = ?")
            values.append(control_id)
        if agent_id:
            clauses.append("v.agent_id = ?")
            values.append(agent_id)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT v.*, c.control_code
            FROM compliance_violations v
            JOIN controls c ON c.id = v.control_id
            WHERE {' AND '.join(clauses)}
            ORDER BY v.created_at DESC, v.id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def get_violation(self, violation_id: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT v.*, c.control_code
            FROM compliance_violations v
            JOIN controls c ON c.id = v.control_id
            WHERE v.id = ?
              AND v.organization_id = ?
              AND v.environment_id = ?
            """,
            (violation_id, self.organization_id, self.environment_id),
        ).fetchone()

    def update_violation(
        self,
        violation_id: str,
        body: ComplianceViolationPatchRequest,
        *,
        actor_id: str,
    ) -> Row:
        violation = self.get_violation(violation_id)
        if violation is None:
            raise ComplianceViolationNotFoundError("Compliance violation not found.")
        if violation["status"] == "resolved":
            raise ComplianceViolationStateError("Resolved violations cannot be updated.")
        now = utc_now_iso()
        if body.status == "acknowledged":
            self.connection.execute(
                """
                UPDATE compliance_violations
                SET status = ?,
                    acknowledged_by = COALESCE(acknowledged_by, ?),
                    acknowledged_at = COALESCE(acknowledged_at, ?),
                    updated_at = ?
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                (
                    "acknowledged",
                    actor_id,
                    now,
                    now,
                    violation_id,
                    self.organization_id,
                    self.environment_id,
                ),
            )
        else:
            self.connection.execute(
                """
                UPDATE compliance_violations
                SET status = ?,
                    resolved_by = ?,
                    resolved_at = ?,
                    resolution_reason = ?,
                    updated_at = ?
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                (
                    "resolved",
                    actor_id,
                    now,
                    body.reason,
                    now,
                    violation_id,
                    self.organization_id,
                    self.environment_id,
                ),
            )
        row = self.get_violation(violation_id)
        if row is None:
            raise ComplianceViolationNotFoundError("Compliance violation not found.")
        return row

    def create_report(self, body: ComplianceReportCreateRequest, *, actor_id: str) -> Row:
        self.seed_defaults()
        if self._framework_row(body.framework_id) is None:
            raise ComplianceResourceNotFoundError("Compliance framework not found.")
        report_id = generate_id("crep")
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO compliance_reports (
                id, organization_id, environment_id, framework_id, name, status,
                date_from, date_to, generated_by, artifact_uri, summary_json,
                rendered_markdown, rendered_json, created_at, updated_at, generated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                self.organization_id,
                self.environment_id,
                body.framework_id,
                body.name,
                "draft",
                body.date_from.isoformat(),
                body.date_to.isoformat(),
                actor_id,
                None,
                json.dumps({}, sort_keys=True),
                None,
                None,
                now,
                now,
                None,
            ),
        )
        row = self.get_report(report_id)
        if row is None:
            raise ComplianceReportNotFoundError("Created compliance report could not be loaded.")
        return row

    def list_reports(self, *, status: str | None = None) -> list[Row]:
        self.seed_defaults()
        clauses = ["r.organization_id = ?", "r.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if status:
            clauses.append("r.status = ?")
            values.append(status)
        return self.connection.execute(
            f"""
            SELECT r.*, f.name AS framework_name
            FROM compliance_reports r
            JOIN control_frameworks f ON f.id = r.framework_id
            WHERE {' AND '.join(clauses)}
            ORDER BY r.created_at DESC, r.id DESC
            """,
            values,
        ).fetchall()

    def get_report(self, report_id: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT r.*, f.name AS framework_name
            FROM compliance_reports r
            JOIN control_frameworks f ON f.id = r.framework_id
            WHERE r.id = ?
              AND r.organization_id = ?
              AND r.environment_id = ?
            """,
            (report_id, self.organization_id, self.environment_id),
        ).fetchone()

    def generate_report(self, report_id: str, *, actor_id: str) -> Row:
        report = self.get_report(report_id)
        if report is None:
            raise ComplianceReportNotFoundError("Compliance report not found.")
        evidence_rows = self._report_evidence_rows(report)
        violation_rows = self._report_violation_rows(report)
        control_rows = self._report_control_rows(report["framework_id"])
        audit_repository = AuditEventRepository(self.connection)
        verification = audit_repository.verify_range(
            self.organization_id,
            environment_id=self.environment_id,
        )
        verification_manifest = _verification_manifest(
            verification=verification.model_dump(mode="json"),
            checkpoint=_checkpoint_summary(
                audit_repository.latest_checkpoint(
                    self.organization_id,
                    environment_id=self.environment_id,
                )
            ),
            evidence_rows=evidence_rows,
            report=report,
        )
        summary = {
            "framework_name": report["framework_name"],
            "control_count": len(control_rows),
            "evidence_count": len(evidence_rows),
            "open_violation_count": len(violation_rows),
            "audit_hash_valid": verification.valid,
            "audit_hash_checked_count": verification.checked_count,
            "audit_hash_reason": verification.reason,
            "complete": True,
            "completeness_reason": None,
            "verification_manifest": verification_manifest,
        }
        rendered_json = json.dumps(
            {
                "report": {
                    "id": report["id"],
                    "name": report["name"],
                    "framework_id": report["framework_id"],
                    "framework_name": report["framework_name"],
                    "date_from": report["date_from"],
                    "date_to": report["date_to"],
                },
                "summary": summary,
                "verification_manifest": verification_manifest,
                "evidence": [_evidence_export_row(row) for row in evidence_rows],
                "violations": [_row_dict(row) for row in violation_rows],
            },
            sort_keys=True,
        )
        rendered_markdown = _render_report_markdown(
            report=report,
            summary=summary,
            evidence_rows=evidence_rows,
            violation_rows=violation_rows,
        )
        now = utc_now_iso()
        artifact_uri = f"compliance-report://{report_id}.md"
        self.connection.execute("DELETE FROM report_evidence_items WHERE report_id = ?", (report_id,))
        for evidence in evidence_rows:
            self.connection.execute(
                """
                INSERT INTO report_evidence_items (report_id, evidence_item_id)
                VALUES (?, ?)
                ON CONFLICT DO NOTHING
                """,
                (report_id, evidence["id"]),
            )
        self.connection.execute(
            """
            UPDATE compliance_reports
            SET status = ?,
                generated_by = ?,
                artifact_uri = ?,
                summary_json = ?,
                rendered_markdown = ?,
                rendered_json = ?,
                generated_at = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (
                "generated",
                actor_id,
                artifact_uri,
                json.dumps(summary, sort_keys=True),
                rendered_markdown,
                rendered_json,
                now,
                now,
                report_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        row = self.get_report(report_id)
        if row is None:
            raise ComplianceReportNotFoundError("Compliance report not found.")
        return row

    def report_markdown(self, report_id: str) -> str:
        report = self.get_report(report_id)
        if report is None:
            raise ComplianceReportNotFoundError("Compliance report not found.")
        if not report["rendered_markdown"]:
            raise ComplianceReportValidationError("Compliance report has not been generated.")
        return str(report["rendered_markdown"])

    def attest_report(
        self,
        report_id: str,
        body: ComplianceReportAttestationRequest,
        *,
        actor_id: str,
    ) -> Row:
        report = self.get_report(report_id)
        if report is None:
            raise ComplianceReportNotFoundError("Compliance report not found.")
        if not report["artifact_uri"]:
            raise ComplianceReportValidationError("Compliance report must be generated before attestation.")
        attestation_id = generate_id("ratt")
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO report_attestations (
                id, report_id, attested_by, statement, signature_ref, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (attestation_id, report_id, actor_id, body.statement, body.signature_ref, now),
        )
        self.connection.execute(
            """
            UPDATE compliance_reports
            SET status = ?, updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            ("attested", now, report_id, self.organization_id, self.environment_id),
        )
        row = self.connection.execute(
            """
            SELECT a.*
            FROM report_attestations a
            JOIN compliance_reports r ON r.id = a.report_id
            WHERE a.id = ?
              AND r.organization_id = ?
              AND r.environment_id = ?
            """,
            (attestation_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise ComplianceReportNotFoundError("Created attestation could not be loaded.")
        return row

    def _audit_event_pages(
        self,
        audit_repository: AuditEventRepository,
        mapping: Row,
    ) -> list[list[AuditEventEnvelope]]:
        pages: list[list[AuditEventEnvelope]] = []
        offset = 0
        while True:
            events = audit_repository.query(
                AuditEventQuery(
                    organization_id=self.organization_id,
                    environment_id=self.environment_id,
                    event_type=mapping["event_type"],
                    source_component=mapping["source_component"],
                    limit=COMPLIANCE_RECOMPUTE_PAGE_SIZE,
                    offset=offset,
                )
            )
            if not events:
                return pages
            pages.append(events)
            if len(events) < COMPLIANCE_RECOMPUTE_PAGE_SIZE:
                return pages
            offset += len(events)

    def _recompute_runtime_action_evidence(
        self,
        *,
        checkpoint_summary: dict[str, Any] | None,
    ) -> tuple[int, int, int]:
        control = self._control_by_code("LOG-1")
        if control is None:
            return (0, 0, 0)
        scanned = 0
        evidence_count = 0
        refreshed = 0
        for actions in self._runtime_action_pages():
            scanned += len(actions)
            for action in actions:
                existed = self._upsert_runtime_action_evidence(
                    control_id=control["id"],
                    action=action,
                    checkpoint_summary=checkpoint_summary,
                )
                evidence_count += 1
                if existed:
                    refreshed += 1
        return (scanned, evidence_count, refreshed)

    def _runtime_action_pages(self) -> list[list[Row]]:
        pages: list[list[Row]] = []
        offset = 0
        while True:
            rows = self.connection.execute(
                """
                SELECT *
                FROM tool_runtime_actions
                WHERE organization_id = ?
                  AND environment_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (
                    self.organization_id,
                    self.environment_id,
                    COMPLIANCE_RECOMPUTE_PAGE_SIZE,
                    offset,
                ),
            ).fetchall()
            if not rows:
                return pages
            pages.append(rows)
            if len(rows) < COMPLIANCE_RECOMPUTE_PAGE_SIZE:
                return pages
            offset += len(rows)

    def _record_recompute_run(
        self,
        *,
        status: str,
        scanned_event_count: int,
        evidence_count: int,
        refreshed_count: int,
        runtime_action_count: int,
        complete: bool,
        cursor: dict[str, Any],
        source_range: dict[str, Any],
        started_at: str,
        completed_at: str,
    ) -> str:
        run_id = generate_id("crecomp")
        self.connection.execute(
            """
            INSERT INTO compliance_recompute_runs (
                id, organization_id, environment_id, status, scanned_event_count,
                evidence_count, refreshed_count, runtime_action_count, complete,
                cursor_json, source_range_json, started_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                self.organization_id,
                self.environment_id,
                status,
                scanned_event_count,
                evidence_count,
                refreshed_count,
                runtime_action_count,
                1 if complete else 0,
                json.dumps(cursor, sort_keys=True),
                json.dumps(source_range, sort_keys=True),
                started_at,
                completed_at,
            ),
        )
        return run_id

    def _upsert_evidence(
        self,
        mapping: Row,
        event: AuditEventEnvelope,
        *,
        hash_metadata: dict[str, Any] | None,
        checkpoint_summary: dict[str, Any] | None,
    ) -> None:
        evidence_id = generate_id("evid")
        decision = f" decision={event.decision}" if event.decision else ""
        title = f"{mapping['evidence_type']} evidence from {event.event_type}"
        summary = (
            f"{event.source_component} recorded {event.event_type}{decision}"
            f" for {event.resource_type or 'resource'} {event.resource_id or 'n/a'}"
        )
        predicate_snapshot = json.loads(mapping["predicate_json"] or "{}")
        source_manifest = _audit_event_source_manifest(
            mapping=mapping,
            event=event,
            hash_metadata=hash_metadata,
            checkpoint_summary=checkpoint_summary,
        )
        chain_proof = {
            "source_type": "audit_event",
            "source_id": event.id,
            "hash_chain": hash_metadata or {},
            "checkpoint": checkpoint_summary,
        }
        self.connection.execute(
            """
            INSERT INTO evidence_items (
                id, organization_id, environment_id, control_id, source_type, source_id,
                title, summary, source_event_hash, source_event_previous_hash,
                source_event_hash_algorithm, source_event_created_at, control_mapping_id,
                control_mapping_version, predicate_snapshot_json, source_manifest_json,
                trace_id, run_id, tool_id, policy_id, policy_version_id, artifact_checksum,
                chain_proof_json, freshness_at, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (organization_id, environment_id, control_id, source_type, source_id)
            DO UPDATE SET
                title = excluded.title,
                summary = excluded.summary,
                source_event_hash = excluded.source_event_hash,
                source_event_previous_hash = excluded.source_event_previous_hash,
                source_event_hash_algorithm = excluded.source_event_hash_algorithm,
                source_event_created_at = excluded.source_event_created_at,
                control_mapping_id = excluded.control_mapping_id,
                control_mapping_version = excluded.control_mapping_version,
                predicate_snapshot_json = excluded.predicate_snapshot_json,
                source_manifest_json = excluded.source_manifest_json,
                trace_id = excluded.trace_id,
                run_id = excluded.run_id,
                tool_id = excluded.tool_id,
                policy_id = excluded.policy_id,
                policy_version_id = excluded.policy_version_id,
                artifact_checksum = excluded.artifact_checksum,
                chain_proof_json = excluded.chain_proof_json,
                freshness_at = excluded.freshness_at,
                status = excluded.status
            """,
            (
                evidence_id,
                self.organization_id,
                self.environment_id,
                mapping["control_id"],
                "audit_event",
                event.id,
                title,
                summary,
                hash_metadata.get("current_hash") if hash_metadata else None,
                hash_metadata.get("previous_hash") if hash_metadata else None,
                hash_metadata.get("algorithm") if hash_metadata else None,
                event.created_at,
                mapping["id"],
                mapping["mapping_version"] if "mapping_version" in mapping.keys() else "v1",
                json.dumps(predicate_snapshot, sort_keys=True),
                json.dumps(source_manifest, sort_keys=True),
                event.trace_id,
                _event_run_id(event),
                _event_tool_id(event),
                event.policy_id,
                event.policy_version_id,
                _event_artifact_checksum(event),
                json.dumps(chain_proof, sort_keys=True),
                event.created_at,
                _evidence_status(event.created_at),
                utc_now_iso(),
            ),
        )

    def _upsert_runtime_action_evidence(
        self,
        *,
        control_id: str,
        action: Row,
        checkpoint_summary: dict[str, Any] | None,
    ) -> bool:
        evidence_id = generate_id("evid")
        title = "tool_runtime_action evidence from tool_runtime_actions"
        summary = (
            f"Tool Gateway recorded {action['action_status']} for tool "
            f"{action['tool_id'] or 'n/a'} request {action['request_id']}"
        )
        source_manifest = _runtime_action_source_manifest(
            action=action,
            checkpoint_summary=checkpoint_summary,
        )
        chain_proof = {
            "source_type": "tool_runtime_action",
            "source_id": action["id"],
            "checkpoint": checkpoint_summary,
        }
        existed = self._evidence_exists(control_id, "tool_runtime_action", action["id"])
        self.connection.execute(
            """
            INSERT INTO evidence_items (
                id, organization_id, environment_id, control_id, source_type, source_id,
                title, summary, source_event_hash, source_event_previous_hash,
                source_event_hash_algorithm, source_event_created_at, control_mapping_id,
                control_mapping_version, predicate_snapshot_json, source_manifest_json,
                trace_id, run_id, tool_id, policy_id, policy_version_id, artifact_checksum,
                chain_proof_json, freshness_at, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (organization_id, environment_id, control_id, source_type, source_id)
            DO UPDATE SET
                title = excluded.title,
                summary = excluded.summary,
                control_mapping_version = excluded.control_mapping_version,
                predicate_snapshot_json = excluded.predicate_snapshot_json,
                source_manifest_json = excluded.source_manifest_json,
                trace_id = excluded.trace_id,
                tool_id = excluded.tool_id,
                chain_proof_json = excluded.chain_proof_json,
                freshness_at = excluded.freshness_at,
                status = excluded.status
            """,
            (
                evidence_id,
                self.organization_id,
                self.environment_id,
                control_id,
                "tool_runtime_action",
                action["id"],
                title,
                summary,
                None,
                None,
                None,
                action["created_at"],
                None,
                "tool-runtime-action-v1",
                json.dumps({"source_type": "tool_runtime_action"}, sort_keys=True),
                json.dumps(source_manifest, sort_keys=True),
                action["correlation_id"],
                None,
                action["tool_id"],
                action["decision_id"],
                None,
                None,
                json.dumps(chain_proof, sort_keys=True),
                action["created_at"],
                _evidence_status(action["created_at"]),
                utc_now_iso(),
            ),
        )
        return existed

    def _upsert_violation(
        self,
        *,
        control_id: str,
        agent_id: str | None,
        severity: str,
        reason: str,
        source_type: str,
        source_id: str,
        source_event_id: str | None,
    ) -> bool:
        existed = self._violation_exists(control_id, source_type, source_id)
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO compliance_violations (
                id, organization_id, environment_id, control_id, agent_id,
                severity, status, reason, source_type, source_id, source_event_id,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (organization_id, environment_id, control_id, source_type, source_id)
            DO UPDATE SET
                severity = excluded.severity,
                reason = excluded.reason,
                updated_at = excluded.updated_at
            """,
            (
                generate_id("cviol"),
                self.organization_id,
                self.environment_id,
                control_id,
                agent_id,
                severity,
                "open",
                reason,
                source_type,
                source_id,
                source_event_id,
                now,
                now,
            ),
        )
        return not existed

    def _evidence_exists(self, control_id: str, source_type: str, source_id: str) -> bool:
        row = self.connection.execute(
            """
            SELECT 1
            FROM evidence_items
            WHERE organization_id = ?
              AND environment_id = ?
              AND control_id = ?
              AND source_type = ?
              AND source_id = ?
            """,
            (self.organization_id, self.environment_id, control_id, source_type, source_id),
        ).fetchone()
        return row is not None

    def _control_row(self, control_id: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT c.*
            FROM controls c
            JOIN control_frameworks f ON f.id = c.framework_id
            WHERE c.id = ? AND f.organization_id = ?
            """,
            (control_id, self.organization_id),
        ).fetchone()

    def _framework_row(self, framework_id: str) -> Row | None:
        self.seed_defaults()
        return self.connection.execute(
            """
            SELECT *
            FROM control_frameworks
            WHERE id = ? AND organization_id = ?
            """,
            (framework_id, self.organization_id),
        ).fetchone()

    def _default_id(self, base_id: str) -> str:
        return f"{base_id}_{self.organization_id}"

    def _control_by_code(self, control_code: str) -> Row | None:
        self.seed_defaults()
        return self.connection.execute(
            """
            SELECT c.*
            FROM controls c
            JOIN control_frameworks f ON f.id = c.framework_id
            WHERE f.organization_id = ?
              AND c.control_code = ?
            ORDER BY f.name ASC, c.id ASC
            LIMIT 1
            """,
            (self.organization_id, control_code),
        ).fetchone()

    def _visible_mappings(self) -> list[Row]:
        return self.connection.execute(
            """
            SELECT m.*
            FROM control_mappings m
            JOIN controls c ON c.id = m.control_id
            JOIN control_frameworks f ON f.id = c.framework_id
            WHERE f.organization_id = ?
            ORDER BY m.event_type ASC, m.id ASC
            """,
            (self.organization_id,),
        ).fetchall()

    def _violation_exists(self, control_id: str, source_type: str, source_id: str) -> bool:
        row = self.connection.execute(
            """
            SELECT 1
            FROM compliance_violations
            WHERE organization_id = ?
              AND environment_id = ?
              AND control_id = ?
              AND source_type = ?
              AND source_id = ?
            """,
            (self.organization_id, self.environment_id, control_id, source_type, source_id),
        ).fetchone()
        return row is not None

    def _stale_evidence_rows(self) -> list[Row]:
        cutoff = _freshness_cutoff()
        return self.connection.execute(
            """
            SELECT e.*, c.control_code
            FROM evidence_items e
            JOIN controls c ON c.id = e.control_id
            WHERE e.organization_id = ?
              AND e.environment_id = ?
              AND (e.status = ? OR e.freshness_at < ?)
            """,
            (self.organization_id, self.environment_id, "stale", cutoff),
        ).fetchall()

    def _controls_missing_fresh_evidence(self) -> list[Row]:
        return self.connection.execute(
            """
            SELECT c.*
            FROM controls c
            JOIN control_frameworks f ON f.id = c.framework_id
            WHERE f.organization_id = ?
              AND NOT EXISTS (
                SELECT 1
                FROM evidence_items e
                WHERE e.organization_id = ?
                  AND e.environment_id = ?
                  AND e.control_id = c.id
                  AND e.status = ?
              )
            """,
            (self.organization_id, self.organization_id, self.environment_id, "fresh"),
        ).fetchall()

    def _report_control_rows(self, framework_id: str) -> list[Row]:
        return self.connection.execute(
            """
            SELECT c.*
            FROM controls c
            JOIN control_frameworks f ON f.id = c.framework_id
            WHERE f.organization_id = ?
              AND c.framework_id = ?
            ORDER BY c.control_code ASC
            """,
            (self.organization_id, framework_id),
        ).fetchall()

    def _report_evidence_rows(self, report: Row) -> list[Row]:
        date_from, date_to = _report_datetime_bounds(report["date_from"], report["date_to"])
        return self.connection.execute(
            """
            SELECT e.*, c.control_code
            FROM evidence_items e
            JOIN controls c ON c.id = e.control_id
            JOIN control_frameworks f ON f.id = c.framework_id
            WHERE e.organization_id = ?
              AND e.environment_id = ?
              AND f.organization_id = ?
              AND c.framework_id = ?
              AND e.freshness_at >= ?
              AND e.freshness_at <= ?
            ORDER BY e.freshness_at DESC, e.id DESC
            """,
            (
                self.organization_id,
                self.environment_id,
                self.organization_id,
                report["framework_id"],
                date_from,
                date_to,
            ),
        ).fetchall()

    def _report_violation_rows(self, report: Row) -> list[Row]:
        date_from, date_to = _report_datetime_bounds(report["date_from"], report["date_to"])
        return self.connection.execute(
            """
            SELECT v.*, c.control_code
            FROM compliance_violations v
            JOIN controls c ON c.id = v.control_id
            JOIN control_frameworks f ON f.id = c.framework_id
            WHERE v.organization_id = ?
              AND v.environment_id = ?
              AND f.organization_id = ?
              AND c.framework_id = ?
              AND v.status != ?
              AND v.created_at >= ?
              AND v.created_at <= ?
            ORDER BY v.created_at DESC, v.id DESC
            """,
            (
                self.organization_id,
                self.environment_id,
                self.organization_id,
                report["framework_id"],
                "resolved",
                date_from,
                date_to,
            ),
        ).fetchall()

    def _report_evidence_ids(self, report_id: str) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT evidence_item_id
            FROM report_evidence_items
            WHERE report_id = ?
            ORDER BY evidence_item_id ASC
            """,
            (report_id,),
        ).fetchall()
        return [row["evidence_item_id"] for row in rows]

    def _attestation_count(self, report_id: str) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM report_attestations WHERE report_id = ?",
            (report_id,),
        ).fetchone()
        return int(row[0]) if row is not None else 0


def framework_response(row: Row) -> ComplianceFrameworkResponse:
    return ComplianceFrameworkResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        name=row["name"],
        version=row["version"],
        description=row["description"],
        status=row["status"],
        created_at=row["created_at"],
    )


def control_response(row: Row) -> ComplianceControlResponse:
    return ComplianceControlResponse(
        id=row["id"],
        framework_id=row["framework_id"],
        framework_name=row["framework_name"] if "framework_name" in row.keys() else None,
        control_code=row["control_code"],
        title=row["title"],
        description=row["description"],
        required_evidence_types=json.loads(row["required_evidence_types_json"] or "[]"),
        owner_user_id=row["owner_user_id"],
    )


def control_mapping_response(row: Row) -> ControlMappingResponse:
    return ControlMappingResponse(
        id=row["id"],
        control_id=row["control_id"],
        event_type=row["event_type"],
        source_component=row["source_component"],
        predicate=json.loads(row["predicate_json"] or "{}"),
        evidence_type=row["evidence_type"],
    )


def evidence_response(row: Row) -> EvidenceItemResponse:
    return EvidenceItemResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        control_id=row["control_id"],
        control_code=row["control_code"] if "control_code" in row.keys() else None,
        source_type=row["source_type"],
        source_id=row["source_id"],
        title=row["title"],
        summary=row["summary"],
        source_event_hash=row["source_event_hash"] if "source_event_hash" in row.keys() else None,
        source_event_previous_hash=row["source_event_previous_hash"]
        if "source_event_previous_hash" in row.keys()
        else None,
        source_event_hash_algorithm=row["source_event_hash_algorithm"]
        if "source_event_hash_algorithm" in row.keys()
        else None,
        source_event_created_at=row["source_event_created_at"]
        if "source_event_created_at" in row.keys()
        else None,
        control_mapping_id=row["control_mapping_id"] if "control_mapping_id" in row.keys() else None,
        control_mapping_version=row["control_mapping_version"]
        if "control_mapping_version" in row.keys()
        else None,
        predicate_snapshot=_json_dict(row, "predicate_snapshot_json"),
        source_manifest=_json_dict(row, "source_manifest_json"),
        trace_id=row["trace_id"] if "trace_id" in row.keys() else None,
        run_id=row["run_id"] if "run_id" in row.keys() else None,
        tool_id=row["tool_id"] if "tool_id" in row.keys() else None,
        policy_id=row["policy_id"] if "policy_id" in row.keys() else None,
        policy_version_id=row["policy_version_id"] if "policy_version_id" in row.keys() else None,
        artifact_checksum=row["artifact_checksum"] if "artifact_checksum" in row.keys() else None,
        chain_proof=_json_dict(row, "chain_proof_json"),
        freshness_at=row["freshness_at"],
        status=row["status"],
        created_at=row["created_at"],
    )


def violation_response(row: Row) -> ComplianceViolationResponse:
    return ComplianceViolationResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        control_id=row["control_id"],
        control_code=row["control_code"] if "control_code" in row.keys() else None,
        agent_id=row["agent_id"],
        severity=row["severity"],
        status=row["status"],
        reason=row["reason"],
        source_type=row["source_type"],
        source_id=row["source_id"],
        source_event_id=row["source_event_id"],
        acknowledged_by=row["acknowledged_by"],
        acknowledged_at=row["acknowledged_at"],
        resolved_by=row["resolved_by"],
        resolved_at=row["resolved_at"],
        resolution_reason=row["resolution_reason"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def report_response(repository: ComplianceRepository, row: Row) -> ComplianceReportResponse:
    return ComplianceReportResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        framework_id=row["framework_id"],
        framework_name=row["framework_name"] if "framework_name" in row.keys() else None,
        name=row["name"],
        status=row["status"],
        date_from=row["date_from"],
        date_to=row["date_to"],
        generated_by=row["generated_by"],
        artifact_uri=row["artifact_uri"],
        summary=json.loads(row["summary_json"] or "{}"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        generated_at=row["generated_at"],
        evidence_item_ids=repository._report_evidence_ids(row["id"]),
        attestation_count=repository._attestation_count(row["id"]),
        rendered_markdown=row["rendered_markdown"],
    )


def report_attestation_response(row: Row) -> ComplianceReportAttestationResponse:
    return ComplianceReportAttestationResponse(
        id=row["id"],
        report_id=row["report_id"],
        attested_by=row["attested_by"],
        statement=row["statement"],
        signature_ref=row["signature_ref"],
        created_at=row["created_at"],
    )


def _predicate_matches(event: AuditEventEnvelope, predicate: dict[str, Any]) -> bool:
    for key, expected in predicate.items():
        if key.startswith("payload."):
            value = event.payload_json.get(key.removeprefix("payload."))
        else:
            value = getattr(event, key, None)
        if value != expected:
            return False
    return True


def _event_requires_violation(event: AuditEventEnvelope) -> bool:
    decision = (event.decision or "").lower()
    severity = (event.severity or "").lower()
    payload_risk = str(event.payload_json.get("risk", "")).lower()
    return (
        decision in {"deny", "denied", "block", "blocked"}
        or severity in {"high", "critical", "error"}
        or payload_risk in {"high", "critical"}
    )


def _event_violation_severity(event: AuditEventEnvelope) -> str:
    severity = (event.severity or "").lower()
    if severity in {"critical", "high", "error"}:
        return severity
    if (event.decision or "").lower() in {"deny", "denied", "block", "blocked"}:
        return "warning"
    return severity or "warning"


def _event_violation_reason(event: AuditEventEnvelope) -> str:
    if reason := event.payload_json.get("reason"):
        return str(reason)
    if risk := event.payload_json.get("risk"):
        return f"High-risk audit event: {risk}"
    if matched_rule := event.payload_json.get("matched_rule"):
        return f"Audit event matched rule {matched_rule}."
    return f"{event.event_type} requires compliance review."


def _runtime_action_requires_violation(action: Row) -> bool:
    status = str(action["action_status"] or "").lower()
    error_code = str(action["error_code"] or "").lower()
    return status in {"denied", "response_blocked", "upstream_failed"} or error_code in {
        "tool_call_denied",
        "response_blocked",
        "upstream_error",
        "upstream_failed",
    }


def _runtime_action_violation_severity(action: Row) -> str:
    status = str(action["action_status"] or "").lower()
    if status == "response_blocked":
        return "high"
    if status == "upstream_failed":
        return "warning"
    return "warning"


def _runtime_action_violation_reason(action: Row) -> str:
    reason_code = action["reason_code"] or action["error_code"]
    if reason_code:
        return f"Tool Gateway runtime action {action['id']} requires review: {reason_code}."
    return f"Tool Gateway runtime action {action['id']} requires compliance review."


def _evidence_status(freshness_at: str) -> str:
    parsed = _parse_iso_datetime(freshness_at)
    if parsed is None:
        return "fresh"
    return "stale" if parsed < datetime.now(timezone.utc) - timedelta(days=90) else "fresh"


def _freshness_cutoff() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _report_datetime_bounds(date_from: str, date_to: str) -> tuple[str, str]:
    lower = f"{date_from}T00:00:00+00:00" if len(date_from) == 10 else date_from
    upper = f"{date_to}T23:59:59+00:00" if len(date_to) == 10 else date_to
    return lower, upper


def _row_dict(row: Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _json_dict(row: Row, column: str) -> dict[str, Any]:
    if column not in row.keys():
        return {}
    value = row[column]
    if not value:
        return {}
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}


def _checkpoint_summary(checkpoint: Row | None) -> dict[str, Any] | None:
    if checkpoint is None:
        return None
    return {
        "id": checkpoint["id"],
        "event_count": checkpoint["event_count"],
        "start_event_id": checkpoint["start_event_id"],
        "end_event_id": checkpoint["end_event_id"],
        "first_hash": checkpoint["first_hash"],
        "last_hash": checkpoint["last_hash"],
        "algorithm": checkpoint["algorithm"],
        "signature": checkpoint["signature"],
        "created_at": checkpoint["created_at"],
    }


def _audit_event_source_manifest(
    *,
    mapping: Row,
    event: AuditEventEnvelope,
    hash_metadata: dict[str, Any] | None,
    checkpoint_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "source_type": "audit_event",
        "source_id": event.id,
        "event_type": event.event_type,
        "source_component": event.source_component,
        "actor_type": event.actor_type,
        "actor_id": event.actor_id,
        "agent_id": event.agent_id,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "decision": event.decision,
        "severity": event.severity,
        "correlation_id": event.correlation_id,
        "trace_id": event.trace_id,
        "policy_id": event.policy_id,
        "policy_version_id": event.policy_version_id,
        "run_id": _event_run_id(event),
        "tool_id": _event_tool_id(event),
        "artifact_checksum": _event_artifact_checksum(event),
        "created_at": event.created_at,
        "hash_chain": hash_metadata or {},
        "control_mapping": {
            "id": mapping["id"],
            "version": mapping["mapping_version"] if "mapping_version" in mapping.keys() else "v1",
            "event_type": mapping["event_type"],
            "source_component": mapping["source_component"],
            "evidence_type": mapping["evidence_type"],
            "predicate": json.loads(mapping["predicate_json"] or "{}"),
        },
        "checkpoint": checkpoint_summary,
    }


def _runtime_action_source_manifest(
    *,
    action: Row,
    checkpoint_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "source_type": "tool_runtime_action",
        "source_id": action["id"],
        "request_id": action["request_id"],
        "correlation_id": action["correlation_id"],
        "agent_id": action["agent_id"],
        "credential_id": action["credential_id"],
        "tool_id": action["tool_id"],
        "permission_id": action["permission_id"],
        "decision_id": action["decision_id"],
        "action_status": action["action_status"],
        "reason_code": action["reason_code"],
        "upstream_status_code": action["upstream_status_code"],
        "latency_ms": action["latency_ms"],
        "payload_summary": json.loads(action["payload_summary_json"] or "{}"),
        "response_summary": json.loads(action["response_summary_json"] or "{}")
        if action["response_summary_json"]
        else None,
        "redaction_applied": bool(action["redaction_applied"]),
        "error_code": action["error_code"],
        "created_at": action["created_at"],
        "updated_at": action["updated_at"],
        "checkpoint": checkpoint_summary,
    }


def _event_run_id(event: AuditEventEnvelope) -> str | None:
    for key in ("run_id", "workflow_run_id", "runtime_session_id", "session_id"):
        value = event.payload_json.get(key)
        if value is not None:
            return str(value)
    return None


def _event_tool_id(event: AuditEventEnvelope) -> str | None:
    for key in ("tool_id", "tool_name", "mcp_tool_id"):
        value = event.payload_json.get(key)
        if value is not None:
            return str(value)
    return None


def _event_artifact_checksum(event: AuditEventEnvelope) -> str | None:
    for key in ("artifact_checksum", "checksum", "sha256"):
        value = event.payload_json.get(key)
        if value is not None:
            return str(value)
    return None


def _verification_manifest(
    *,
    verification: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    evidence_rows: list[Row],
    report: Row,
) -> dict[str, Any]:
    return {
        "complete": True,
        "completeness_reason": None,
        "date_from": report["date_from"],
        "date_to": report["date_to"],
        "audit_range_verification": verification,
        "checkpoint": checkpoint,
        "evidence_count": len(evidence_rows),
        "source_event_hashes": [
            {
                "evidence_item_id": row["id"],
                "source_type": row["source_type"],
                "source_id": row["source_id"],
                "source_event_hash": row["source_event_hash"],
                "hash_algorithm": row["source_event_hash_algorithm"],
                "control_mapping_id": row["control_mapping_id"],
                "control_mapping_version": row["control_mapping_version"],
            }
            for row in evidence_rows
            if "source_event_hash" in row.keys() and row["source_event_hash"]
        ],
        "linked_runtime_action_ids": [
            row["source_id"]
            for row in evidence_rows
            if row["source_type"] == "tool_runtime_action"
        ],
        "linked_policy_ids": sorted(
            {
                row["policy_id"]
                for row in evidence_rows
                if "policy_id" in row.keys() and row["policy_id"]
            }
        ),
    }


def _evidence_export_row(row: Row) -> dict[str, Any]:
    data = _row_dict(row)
    data["predicate_snapshot"] = _json_dict(row, "predicate_snapshot_json")
    data["source_manifest"] = _json_dict(row, "source_manifest_json")
    data["chain_proof"] = _json_dict(row, "chain_proof_json")
    data["linked_runtime_action_id"] = (
        row["source_id"] if row["source_type"] == "tool_runtime_action" else None
    )
    data["linked_policy_id"] = row["policy_id"] if "policy_id" in row.keys() else None
    data["linked_policy_version_id"] = (
        row["policy_version_id"] if "policy_version_id" in row.keys() else None
    )
    return data


def _manifest_checkpoint_id(summary: dict[str, Any]) -> str:
    manifest = summary.get("verification_manifest", {})
    if not isinstance(manifest, dict):
        return "n/a"
    checkpoint = manifest.get("checkpoint")
    if not isinstance(checkpoint, dict):
        return "n/a"
    checkpoint_id = checkpoint.get("id")
    return str(checkpoint_id) if checkpoint_id else "n/a"


def _render_report_markdown(
    *,
    report: Row,
    summary: dict[str, Any],
    evidence_rows: list[Row],
    violation_rows: list[Row],
) -> str:
    hash_status = "valid" if summary.get("audit_hash_valid") else "failed"
    lines = [
        f"# {report['name']}",
        "",
        f"Framework: {report['framework_name']}",
        f"Period: {report['date_from']} to {report['date_to']}",
        f"Status: {report['status']}",
        f"Audit hash status: {hash_status} ({summary.get('audit_hash_checked_count', 0)} events checked)",
        "",
        "## Summary",
        "",
        f"- Controls: {summary.get('control_count', 0)}",
        f"- Evidence items: {summary.get('evidence_count', 0)}",
        f"- Open violations: {summary.get('open_violation_count', 0)}",
        f"- Evidence completeness: {'complete' if summary.get('complete') else 'partial'}",
        "",
        "## Verification Manifest",
        "",
        f"- Audit range valid: {summary.get('audit_hash_valid')}",
        f"- Checkpoint: {_manifest_checkpoint_id(summary)}",
        f"- Source hashes: {len(summary.get('verification_manifest', {}).get('source_event_hashes', []))}",
        f"- Runtime actions: {', '.join(summary.get('verification_manifest', {}).get('linked_runtime_action_ids', [])) or 'n/a'}",
        f"- Policy IDs: {', '.join(summary.get('verification_manifest', {}).get('linked_policy_ids', [])) or 'n/a'}",
        "",
        "## Evidence",
        "",
    ]
    if evidence_rows:
        for evidence in evidence_rows:
            source_hash = evidence["source_event_hash"] if "source_event_hash" in evidence.keys() else None
            mapping_version = (
                evidence["control_mapping_version"]
                if "control_mapping_version" in evidence.keys()
                else None
            )
            linked_runtime_action = (
                evidence["source_id"] if evidence["source_type"] == "tool_runtime_action" else None
            )
            lines.append(
                "- "
                f"{evidence['control_code']}: {evidence['title']} "
                f"({evidence['status']}, {evidence['source_type']}:{evidence['source_id']}, "
                f"hash={source_hash or 'n/a'}, mapping_version={mapping_version or 'n/a'}, "
                f"runtime_action={linked_runtime_action or 'n/a'})"
            )
    else:
        lines.append("- No evidence matched the selected period.")
    lines.extend(["", "## Open Violations", ""])
    if violation_rows:
        for violation in violation_rows:
            lines.append(
                "- "
                f"{violation['control_code']}: {violation['severity']} "
                f"{violation['status']} - {violation['reason']}"
            )
    else:
        lines.append("- No open violations.")
    return "\n".join(lines) + "\n"
