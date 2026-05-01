"""Normalization and reconciliation persistence for discovery findings."""

from __future__ import annotations

import json
from datetime import datetime
from sqlite3 import Connection, Row
from typing import Any

from agent_discovery.models import AgentStatus, DiscoveredAgent
from agent_discovery.risk import RiskScorer

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.discovery.models import (
    DiscoveryEvidenceResponse,
    DiscoveryFindingResponse,
)


class DiscoveryFindingNotFoundError(ValueError):
    """Raised when a finding is not visible in the tenant scope."""


class DiscoveryFindingRepository:
    """Persistence for normalized discovery findings."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def reconcile_run(self, run_id: str) -> list[Row]:
        """Normalize raw findings from a scan run into deduplicated findings."""

        raw_rows = self._raw_findings_for_run(run_id)
        normalized_by_fingerprint: dict[str, Row] = {}
        for raw_row in raw_rows:
            payload = json.loads(raw_row["raw_payload_json"])
            fingerprint = str(payload.get("fingerprint") or raw_row["fingerprint"])
            row = self._upsert_finding(fingerprint, payload)
            self._store_evidence(row["id"], run_id, payload)
            loaded = self.get_finding(row["id"])
            if loaded is not None:
                normalized_by_fingerprint[fingerprint] = loaded
        return list(normalized_by_fingerprint.values())

    def list_findings(
        self,
        *,
        risk_level: str | None = None,
        status: str | None = None,
        source: str | None = None,
        owner: str | None = None,
        registry_match: str | None = None,
        include_suppressed: bool = True,
    ) -> list[Row]:
        """List normalized findings for the selected environment."""

        clauses = [
            "organization_id = ?",
            "environment_id = ?",
        ]
        params: list[Any] = [self.organization_id, self.environment_id]
        if not include_suppressed:
            clauses.append("status != 'suppressed'")
        if risk_level:
            clauses.append("risk_level = ?")
            params.append(risk_level)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if source:
            clauses.append("LOWER(COALESCE(source, '')) LIKE ?")
            params.append(f"%{source.lower()}%")
        if owner:
            clauses.append("LOWER(COALESCE(owner_hint, '')) LIKE ?")
            params.append(f"%{owner.lower()}%")
        if registry_match:
            normalized_match = registry_match.strip().lower()
            if normalized_match in {"matched", "registered", "true", "yes"}:
                clauses.append("registry_agent_id IS NOT NULL")
            elif normalized_match in {"unmatched", "unregistered", "false", "no", "none"}:
                clauses.append("registry_agent_id IS NULL")
            else:
                raise ValueError("registry_match must be matched or unmatched.")

        where_clause = "\n              AND ".join(clauses)
        return self.connection.execute(
            f"""
            SELECT *
            FROM discovery_findings
            WHERE {where_clause}
            ORDER BY last_seen_at DESC, id DESC
            """,
            tuple(params),
        ).fetchall()

    def get_finding(self, finding_id: str) -> Row | None:
        """Get one finding by tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM discovery_findings
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (finding_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_evidence(self, finding_id: str) -> list[Row]:
        """List evidence for a finding."""

        return self.connection.execute(
            """
            SELECT e.*
            FROM discovery_evidence e
            JOIN discovery_findings f ON f.id = e.finding_id
            WHERE e.finding_id = ?
              AND f.organization_id = ?
              AND f.environment_id = ?
            ORDER BY e.created_at ASC, e.id ASC
            """,
            (finding_id, self.organization_id, self.environment_id),
        ).fetchall()

    def score_finding(self, finding_id: str) -> Row:
        """Calculate and persist risk for one finding."""

        finding = self.get_finding(finding_id)
        if finding is None:
            raise DiscoveryFindingNotFoundError("Discovery finding not found.")
        assessment = RiskScorer().score(_finding_row_to_discovered_agent(finding))
        self.connection.execute(
            """
            UPDATE discovery_findings
            SET risk_score = ?,
                risk_level = ?,
                risk_factors_json = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (
                assessment.score,
                assessment.level.value,
                json.dumps(assessment.factors, sort_keys=True),
                utc_now_iso(),
                finding_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        loaded = self.get_finding(finding_id)
        if loaded is None:
            raise DiscoveryFindingNotFoundError("Discovery finding not found.")
        return loaded

    def update_governance_state(
        self,
        finding_id: str,
        *,
        status: str,
        owner_hint: str | None,
        registry_agent_id: str | None,
    ) -> Row:
        """Update governance fields and recalculate risk."""

        existing = self.get_finding(finding_id)
        if existing is None:
            raise DiscoveryFindingNotFoundError("Discovery finding not found.")
        self.connection.execute(
            """
            UPDATE discovery_findings
            SET status = ?,
                owner_hint = ?,
                registry_agent_id = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (
                status,
                owner_hint,
                registry_agent_id,
                utc_now_iso(),
                finding_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        return self.score_finding(finding_id)

    def reconcile_registry(self) -> list[Row]:
        """Match normalized findings against the product agent registry."""

        provider = ProductRegistryProvider(
            self.connection,
            self.organization_id,
            self.environment_id,
        )
        reconciled: list[Row] = []
        for finding in self.list_findings():
            matches = provider.match_finding(finding)
            if len(matches) == 1:
                agent = matches[0]
                reconciled.append(
                    self.update_governance_state(
                        finding["id"],
                        status="registered",
                        owner_hint=agent.get("owner_user_id"),
                        registry_agent_id=agent["id"],
                    )
                )
            elif len(matches) > 1:
                reconciled.append(
                    self.update_governance_state(
                        finding["id"],
                        status="manual_review",
                        owner_hint=finding["owner_hint"],
                        registry_agent_id=None,
                    )
                )
            else:
                reconciled.append(
                    self.update_governance_state(
                        finding["id"],
                        status="shadow_candidate",
                        owner_hint=finding["owner_hint"],
                        registry_agent_id=None,
                    )
                )
        return reconciled

    def assign_owner(self, finding_id: str, owner_user_id: str, *, actor_id: str) -> Row:
        """Assign owner and record the triage action."""

        row = self.update_governance_state(
            finding_id,
            status="owner_assigned",
            owner_hint=owner_user_id,
            registry_agent_id=None,
        )
        self.record_action(
            finding_id,
            action_type="assign_owner",
            status="completed",
            actor_id=actor_id,
            result={"owner_user_id": owner_user_id},
        )
        return row

    def suppress(
        self,
        finding_id: str,
        *,
        reason: str,
        expires_at: str | None,
        actor_id: str,
    ) -> Row:
        """Suppress a finding with an audit-ready reason."""

        finding = self.get_finding(finding_id)
        if finding is None:
            raise DiscoveryFindingNotFoundError("Discovery finding not found.")
        now = utc_now_iso()
        suppression_id = generate_id("sup")
        self.connection.execute(
            """
            INSERT INTO discovery_suppressions (
                id, finding_id, reason, expires_at, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (suppression_id, finding_id, reason, expires_at, actor_id, now),
        )
        row = self.update_governance_state(
            finding_id,
            status="suppressed",
            owner_hint=finding["owner_hint"],
            registry_agent_id=finding["registry_agent_id"],
        )
        self.record_action(
            finding_id,
            action_type="suppress",
            status="completed",
            actor_id=actor_id,
            result={"reason": reason, "expires_at": expires_at, "suppression_id": suppression_id},
        )
        return row

    def mark_decommissioned(self, finding_id: str, *, actor_id: str) -> Row:
        """Mark a finding as decommissioned."""

        finding = self.get_finding(finding_id)
        if finding is None:
            raise DiscoveryFindingNotFoundError("Discovery finding not found.")
        row = self.update_governance_state(
            finding_id,
            status="decommissioned",
            owner_hint=finding["owner_hint"],
            registry_agent_id=finding["registry_agent_id"],
        )
        self.record_action(
            finding_id,
            action_type="mark_decommissioned",
            status="completed",
            actor_id=actor_id,
            result={"status": "decommissioned"},
        )
        return row

    def link_registration_draft(
        self,
        finding_id: str,
        *,
        agent_id: str,
        actor_id: str,
    ) -> Row:
        """Link a finding to a newly created registration draft."""

        finding = self.get_finding(finding_id)
        if finding is None:
            raise DiscoveryFindingNotFoundError("Discovery finding not found.")
        row = self.update_governance_state(
            finding_id,
            status="registration_draft_created",
            owner_hint=finding["owner_hint"],
            registry_agent_id=agent_id,
        )
        self.record_action(
            finding_id,
            action_type="register_agent",
            status="completed",
            actor_id=actor_id,
            result={"agent_id": agent_id},
        )
        return row

    def record_action(
        self,
        finding_id: str,
        *,
        action_type: str,
        status: str,
        actor_id: str,
        result: dict[str, Any],
    ) -> Row:
        """Record a reconciliation action."""

        action_id = generate_id("act")
        self.connection.execute(
            """
            INSERT INTO reconciliation_actions (
                id, finding_id, action_type, status, actor_id, result_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_id,
                finding_id,
                action_type,
                status,
                actor_id,
                json.dumps(result, sort_keys=True),
                utc_now_iso(),
            ),
        )
        row = self.connection.execute(
            "SELECT * FROM reconciliation_actions WHERE id = ?",
            (action_id,),
        ).fetchone()
        if row is None:
            raise DiscoveryFindingNotFoundError("Reconciliation action could not be loaded.")
        return row

    def _raw_findings_for_run(self, run_id: str) -> list[Row]:
        return self.connection.execute(
            """
            SELECT raw.*
            FROM discovery_raw_findings raw
            JOIN discovery_runs run ON run.id = raw.run_id
            WHERE raw.run_id = ?
              AND run.organization_id = ?
              AND run.environment_id = ?
            ORDER BY raw.created_at ASC, raw.id ASC
            """,
            (run_id, self.organization_id, self.environment_id),
        ).fetchall()

    def _upsert_finding(self, fingerprint: str, payload: dict[str, Any]) -> Row:
        existing = self.connection.execute(
            """
            SELECT *
            FROM discovery_findings
            WHERE organization_id = ?
              AND environment_id = ?
              AND fingerprint = ?
            """,
            (self.organization_id, self.environment_id, fingerprint),
        ).fetchone()
        now = utc_now_iso()
        evidence = payload.get("evidence") or []
        source = _source_from_payload(payload)
        first_seen_at = str(payload.get("first_seen_at") or now)
        last_seen_at = str(payload.get("last_seen_at") or now)
        merge_keys = payload.get("merge_keys") or {}
        if existing is None:
            finding_id = generate_id("finding")
            self.connection.execute(
                """
                INSERT INTO discovery_findings (
                    id, organization_id, environment_id, fingerprint, detected_name,
                    agent_type, source, owner_hint, registry_agent_id, status,
                    risk_score, risk_level, risk_factors_json, did, endpoint_url,
                    merge_keys_json, first_seen_at, last_seen_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    finding_id,
                    self.organization_id,
                    self.environment_id,
                    fingerprint,
                    str(payload.get("name") or fingerprint),
                    str(payload.get("agent_type") or "unknown"),
                    source,
                    payload.get("owner"),
                    "new",
                    0.0,
                    "info",
                    "[]",
                    payload.get("did"),
                    payload.get("endpoint_url"),
                    json.dumps(merge_keys, sort_keys=True),
                    first_seen_at,
                    last_seen_at,
                    now,
                    now,
                ),
            )
            loaded = self.get_finding(finding_id)
            if loaded is None:
                raise DiscoveryFindingNotFoundError("Created discovery finding could not be loaded.")
            return loaded

        self.connection.execute(
            """
            UPDATE discovery_findings
            SET detected_name = ?,
                agent_type = ?,
                source = ?,
                owner_hint = ?,
                did = ?,
                endpoint_url = ?,
                merge_keys_json = ?,
                last_seen_at = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (
                str(payload.get("name") or existing["detected_name"]),
                str(payload.get("agent_type") or existing["agent_type"]),
                source,
                payload.get("owner"),
                payload.get("did"),
                payload.get("endpoint_url"),
                json.dumps(merge_keys, sort_keys=True),
                last_seen_at,
                now,
                existing["id"],
                self.organization_id,
                self.environment_id,
            ),
        )
        loaded = self.get_finding(existing["id"])
        if loaded is None:
            raise DiscoveryFindingNotFoundError("Discovery finding could not be loaded.")
        return loaded

    def _store_evidence(self, finding_id: str, run_id: str, payload: dict[str, Any]) -> None:
        evidence_items = payload.get("evidence") or [
            {
                "basis": "raw",
                "source": _source_from_payload(payload) or payload.get("fingerprint") or "unknown",
                "confidence": payload.get("confidence") or 0,
            }
        ]
        now = utc_now_iso()
        for evidence in evidence_items:
            self.connection.execute(
                """
                INSERT INTO discovery_evidence (
                    id, finding_id, run_id, evidence_type, evidence_value,
                    confidence, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generate_id("evd"),
                    finding_id,
                    run_id,
                    str(evidence.get("basis") or "raw"),
                    str(evidence.get("source") or _source_from_payload(payload) or "unknown"),
                    float(evidence.get("confidence") or payload.get("confidence") or 0),
                    now,
                ),
            )


def _source_from_payload(payload: dict[str, Any]) -> str | None:
    evidence = payload.get("evidence") or []
    if evidence:
        source = evidence[0].get("source")
        if source:
            return str(source)
    merge_keys = payload.get("merge_keys") or {}
    for key in ("config_path", "repo", "endpoint_url", "docker_path"):
        if merge_keys.get(key):
            return str(merge_keys[key])
    return None


class ProductRegistryProvider:
    """Registry provider backed by product `agents` and `agent_identities`."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def list_registered_agents(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT a.id, a.name, a.endpoint_url, a.owner_user_id, i.did
            FROM agents a
            LEFT JOIN agent_identities i ON i.agent_id = a.id
            WHERE a.organization_id = ?
              AND a.environment_id = ?
              AND a.deleted_at IS NULL
            ORDER BY a.name ASC, a.id ASC
            """,
            (self.organization_id, self.environment_id),
        ).fetchall()
        return [dict(row) for row in rows]

    def match_finding(self, finding: Row) -> list[dict[str, Any]]:
        agents = self.list_registered_agents()
        merge_keys = json.loads(finding["merge_keys_json"])
        match_stages = [
            lambda agent: bool(finding["did"] and agent.get("did") == finding["did"]),
            lambda agent: bool(
                finding["endpoint_url"]
                and agent.get("endpoint_url")
                and agent["endpoint_url"] == finding["endpoint_url"]
            ),
            lambda agent: bool(
                merge_keys.get("endpoint_url")
                and agent.get("endpoint_url")
                and agent["endpoint_url"] == merge_keys["endpoint_url"]
            ),
            lambda agent: _names_match(finding["detected_name"], str(agent.get("name") or "")),
        ]
        for matcher in match_stages:
            matches = [agent for agent in agents if matcher(agent)]
            if matches:
                return matches
        return []


def _names_match(finding_name: str, agent_name: str) -> bool:
    finding = finding_name.strip().lower()
    agent = agent_name.strip().lower()
    if not finding or not agent:
        return False
    return finding == agent or finding in agent or agent in finding


def discovery_evidence_response(row: Row) -> DiscoveryEvidenceResponse:
    """Serialize a discovery evidence row."""

    return DiscoveryEvidenceResponse(
        id=row["id"],
        finding_id=row["finding_id"],
        run_id=row["run_id"],
        evidence_type=row["evidence_type"],
        evidence_value=row["evidence_value"],
        confidence=row["confidence"],
        created_at=row["created_at"],
    )


def discovery_finding_response(
    repository: DiscoveryFindingRepository,
    row: Row,
    *,
    include_evidence: bool = False,
) -> DiscoveryFindingResponse:
    """Serialize a normalized finding row."""

    return DiscoveryFindingResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        fingerprint=row["fingerprint"],
        detected_name=row["detected_name"],
        agent_type=row["agent_type"],
        source=row["source"],
        owner_hint=row["owner_hint"],
        registry_agent_id=row["registry_agent_id"],
        status=row["status"],
        risk_score=row["risk_score"],
        risk_level=row["risk_level"],
        risk_factors=json.loads(row["risk_factors_json"]),
        first_seen_at=row["first_seen_at"],
        last_seen_at=row["last_seen_at"],
        evidence=[
            discovery_evidence_response(evidence)
            for evidence in repository.list_evidence(row["id"])
        ]
        if include_evidence
        else [],
    )


def _finding_row_to_discovered_agent(row: Row) -> DiscoveredAgent:
    status = {
        "registered": AgentStatus.REGISTERED,
        "shadow_candidate": AgentStatus.SHADOW,
        "decommissioned": AgentStatus.DECOMMISSIONED,
    }.get(row["status"], AgentStatus.UNREGISTERED)
    merge_keys = json.loads(row["merge_keys_json"])
    return DiscoveredAgent(
        fingerprint=row["fingerprint"],
        name=row["detected_name"],
        agent_type=row["agent_type"],
        did=row["did"],
        owner=row["owner_hint"],
        status=status,
        confidence=1.0,
        merge_keys=merge_keys,
        first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
        last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
    )
