from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.store import AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.runtime_audit import (
    ToolRuntimeActionCreate,
    ToolRuntimeActionRepository,
)


class CompliancePhase2ControlEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "X-Environment-ID": "env_default"}

    def _insert_audit_event(self, event: AuditEventEnvelope) -> str:
        with self.database.transaction() as connection:
            return AuditEventRepository(connection).insert(event).id

    def test_seed_defaults_is_idempotent(self) -> None:
        first = self.client.get("/api/v1/compliance/frameworks", headers=self._headers())
        second = self.client.get("/api/v1/compliance/frameworks", headers=self._headers())
        controls = self.client.get("/api/v1/compliance/controls", headers=self._headers())

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(controls.status_code, 200, controls.text)
        framework_names = {framework["name"] for framework in first.json()}
        self.assertEqual({"SOC 2", "GDPR", "EU AI Act", "Internal Governance"}, framework_names)
        self.assertEqual(len(first.json()), len(second.json()))
        self.assertEqual(
            {"CC6.1", "CC6.6", "Art.32", "LOG-1", "GOV-1"},
            {control["control_code"] for control in controls.json()},
        )

        with self.database.connect() as connection:
            framework_count = connection.execute(
                "SELECT COUNT(*) FROM control_frameworks WHERE organization_id = ?",
                ("org_default",),
            ).fetchone()[0]
            control_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM controls c
                JOIN control_frameworks f ON f.id = c.framework_id
                WHERE f.organization_id = ?
                """,
                ("org_default",),
            ).fetchone()[0]
        self.assertEqual(framework_count, 4)
        self.assertEqual(control_count, 5)

    def test_policy_decision_event_maps_to_policy_controls(self) -> None:
        event_id = self._insert_audit_event(
            AuditEventEnvelope(
                organization_id="org_default",
                environment_id="env_default",
                event_type="policy.decision",
                source_component="policy-engine",
                actor_type="user",
                actor_id="user_policy",
                agent_id="agent_compliance",
                resource_type="policy",
                resource_id="policy_refund",
                decision="deny",
                severity="warning",
                policy_id="policy_refund",
                payload_json={"matched_rule": "refund_limit", "reason": "blocked"},
            )
        )

        recompute = self.client.post(
            "/api/v1/compliance/evidence/recompute",
            headers=self._headers(),
        )
        evidence = self.client.get(
            "/api/v1/compliance/evidence",
            headers=self._headers(),
            params={"status": "fresh"},
        )

        self.assertEqual(recompute.status_code, 201, recompute.text)
        self.assertEqual(evidence.status_code, 200, evidence.text)
        self.assertEqual(recompute.json()["evidence_count"], 2)
        policy_evidence = [
            item for item in evidence.json() if item["source_id"] == event_id
        ]
        self.assertEqual({"CC6.6", "Art.32"}, {item["control_code"] for item in policy_evidence})
        self.assertTrue(
            all(item["title"].startswith("policy_decision evidence") for item in policy_evidence)
        )

    def test_credential_rotation_maps_to_credential_lifecycle_control(self) -> None:
        event_id = self._insert_audit_event(
            AuditEventEnvelope(
                organization_id="org_default",
                environment_id="env_default",
                event_type="agent.credential.rotated",
                source_component="agent-registry",
                actor_type="user",
                actor_id="user_admin",
                agent_id="agent_credential",
                resource_type="agent_credential",
                resource_id="cred_new",
                decision="allow",
                severity="info",
                payload_json={
                    "previous_credential_id": "cred_old",
                    "new_credential_id": "cred_new",
                    "reason": "scheduled rotation",
                },
            )
        )

        recompute = self.client.post(
            "/api/v1/compliance/evidence/recompute",
            headers=self._headers(),
        )
        evidence = self.client.get(
            "/api/v1/compliance/evidence",
            headers=self._headers(),
            params={"status": "fresh"},
        )

        self.assertEqual(recompute.status_code, 201, recompute.text)
        self.assertEqual(evidence.status_code, 200, evidence.text)
        rotation_evidence = [
            item for item in evidence.json() if item["source_id"] == event_id
        ]
        self.assertEqual(1, len(rotation_evidence))
        self.assertEqual("CC6.1", rotation_evidence[0]["control_code"])
        self.assertEqual(
            "credential_lifecycle evidence from agent.credential.rotated",
            rotation_evidence[0]["title"],
        )

    def test_recompute_refreshes_existing_evidence_without_duplicates(self) -> None:
        self._insert_audit_event(
            AuditEventEnvelope(
                organization_id="org_default",
                environment_id="env_default",
                event_type="policy.decision",
                source_component="policy-engine",
                actor_type="user",
                actor_id="user_policy",
                resource_type="policy",
                resource_id="policy_refund",
                decision="allow",
                severity="info",
                policy_id="policy_refund",
                payload_json={"matched_rule": "allow_refund", "reason": "ok"},
            )
        )

        first = self.client.post("/api/v1/compliance/evidence/recompute", headers=self._headers())
        evidence_after_first = self.client.get(
            "/api/v1/compliance/evidence",
            headers=self._headers(),
        )
        second = self.client.post("/api/v1/compliance/evidence/recompute", headers=self._headers())
        evidence_after_second = self.client.get(
            "/api/v1/compliance/evidence",
            headers=self._headers(),
        )

        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(first.json()["evidence_count"], 2)
        self.assertEqual(first.json()["refreshed_count"], 0)
        self.assertEqual(second.json()["evidence_count"], 2)
        self.assertEqual(second.json()["refreshed_count"], 2)
        self.assertEqual(len(evidence_after_first.json()), len(evidence_after_second.json()))

    def test_recompute_paginates_more_than_500_matching_events(self) -> None:
        with self.database.transaction() as connection:
            audit = AuditEventRepository(connection)
            for index in range(505):
                audit.insert(
                    AuditEventEnvelope(
                        organization_id="org_default",
                        environment_id="env_default",
                        event_type="policy.decision",
                        source_component="policy-engine",
                        actor_type="system",
                        actor_id=f"bulk_{index}",
                        resource_type="policy",
                        resource_id=f"policy_{index}",
                        decision="allow",
                        severity="info",
                        policy_id=f"policy_{index}",
                        payload_json={"matched_rule": "bulk_allow", "index": index},
                        created_at=(
                            f"2026-05-01T{(index // 3600) % 24:02d}:"
                            f"{(index // 60) % 60:02d}:{index % 60:02d}+00:00"
                        ),
                    )
                )

        recompute = self.client.post(
            "/api/v1/compliance/evidence/recompute",
            headers=self._headers(),
        )

        self.assertEqual(recompute.status_code, 201, recompute.text)
        payload = recompute.json()
        self.assertTrue(payload["complete"])
        self.assertEqual(payload["scanned_event_count"], 1010)
        self.assertEqual(payload["evidence_count"], 1010)
        self.assertEqual(payload["cursor"]["page_size"], 500)

    def test_violation_refresh_paginates_more_than_500_matching_events(self) -> None:
        denied_event_id = ""
        with self.database.transaction() as connection:
            audit = AuditEventRepository(connection)
            for index in range(501):
                event = audit.insert(
                    AuditEventEnvelope(
                        organization_id="org_default",
                        environment_id="env_default",
                        event_type="policy.decision",
                        source_component="policy-engine",
                        actor_type="system",
                        actor_id=f"bulk_violation_{index}",
                        resource_type="policy",
                        resource_id=f"policy_violation_{index}",
                        decision="deny" if index == 0 else "allow",
                        severity="warning" if index == 0 else "info",
                        policy_id=f"policy_violation_{index}",
                        payload_json={
                            "matched_rule": "oldest_deny" if index == 0 else "bulk_allow",
                            "reason": "oldest denied event",
                        },
                        created_at=(
                            f"2026-05-01T{(index // 3600) % 24:02d}:"
                            f"{(index // 60) % 60:02d}:{index % 60:02d}+00:00"
                        ),
                    )
                )
                if index == 0:
                    denied_event_id = event.id

        recompute = self.client.post(
            "/api/v1/compliance/evidence/recompute",
            headers=self._headers(),
        )
        violations = self.client.get(
            "/api/v1/compliance/violations",
            headers=self._headers(),
            params={"status": "open"},
        )

        self.assertEqual(recompute.status_code, 201, recompute.text)
        source_ids = {violation["source_event_id"] for violation in violations.json()}
        self.assertIn(denied_event_id, source_ids)

    def test_evidence_contains_source_hashes_and_mapping_snapshot(self) -> None:
        event_id = self._insert_audit_event(
            AuditEventEnvelope(
                organization_id="org_default",
                environment_id="env_default",
                event_type="policy.decision",
                source_component="policy-engine",
                actor_type="user",
                actor_id="user_policy",
                agent_id="agent_compliance",
                resource_type="policy",
                resource_id="policy_hash",
                decision="allow",
                severity="info",
                correlation_id="corr-hash",
                trace_id="trace-hash",
                policy_id="policy_hash",
                policy_version_id="pv_hash",
                payload_json={"matched_rule": "allow_hash", "run_id": "run_hash"},
            )
        )

        recompute = self.client.post(
            "/api/v1/compliance/evidence/recompute",
            headers=self._headers(),
        )
        evidence = self.client.get(
            "/api/v1/compliance/evidence",
            headers=self._headers(),
            params={"status": "fresh"},
        )

        self.assertEqual(recompute.status_code, 201, recompute.text)
        item = next(item for item in evidence.json() if item["source_id"] == event_id)
        self.assertIsNotNone(item["source_event_hash"])
        self.assertEqual("sha256", item["source_event_hash_algorithm"])
        self.assertEqual("trace-hash", item["trace_id"])
        self.assertEqual("run_hash", item["run_id"])
        self.assertEqual("policy_hash", item["policy_id"])
        self.assertEqual("pv_hash", item["policy_version_id"])
        self.assertEqual("v1", item["control_mapping_version"])
        self.assertEqual({}, item["predicate_snapshot"])
        self.assertEqual(event_id, item["source_manifest"]["source_id"])
        self.assertEqual(item["source_event_hash"], item["chain_proof"]["hash_chain"]["current_hash"])

    def test_tool_runtime_action_appears_in_compliance_evidence(self) -> None:
        with self.database.transaction() as connection:
            action = ToolRuntimeActionRepository(
                connection,
                "org_default",
                "env_default",
            ).create_action(
                ToolRuntimeActionCreate(
                    request_id="req-runtime-evidence",
                    correlation_id="corr-runtime-evidence",
                    action_status="denied",
                    reason_code="policy_denied",
                    payload_summary={"tool_name": "danger.delete"},
                    error_code="tool_call_denied",
                ),
                created_at="2026-05-01T00:00:00+00:00",
            )

        recompute = self.client.post(
            "/api/v1/compliance/evidence/recompute",
            headers=self._headers(),
        )
        evidence = self.client.get(
            "/api/v1/compliance/evidence",
            headers=self._headers(),
        )

        self.assertEqual(recompute.status_code, 201, recompute.text)
        runtime_items = [
            item for item in evidence.json() if item["source_type"] == "tool_runtime_action"
        ]
        self.assertEqual(1, len(runtime_items))
        self.assertEqual(action["id"], runtime_items[0]["source_id"])
        self.assertEqual("LOG-1", runtime_items[0]["control_code"])
        self.assertEqual("tool-runtime-action-v1", runtime_items[0]["control_mapping_version"])
        self.assertEqual(
            "req-runtime-evidence",
            runtime_items[0]["source_manifest"]["request_id"],
        )

    def test_custom_mapping_predicate_matches_payload_fields(self) -> None:
        controls = self.client.get("/api/v1/compliance/controls", headers=self._headers())
        self.assertEqual(controls.status_code, 200, controls.text)
        control_id = next(
            control["id"] for control in controls.json() if control["control_code"] == "GOV-1"
        )
        mapping = self.client.post(
            "/api/v1/compliance/control-mappings",
            headers=self._headers(),
            json={
                "control_id": control_id,
                "event_type": "custom.finding",
                "source_component": "custom-scanner",
                "predicate": {"payload.risk": "high"},
                "evidence_type": "custom_risk",
            },
        )
        self.assertEqual(mapping.status_code, 201, mapping.text)
        matched_event_id = self._insert_audit_event(
            AuditEventEnvelope(
                organization_id="org_default",
                environment_id="env_default",
                event_type="custom.finding",
                source_component="custom-scanner",
                actor_type="system",
                resource_type="finding",
                resource_id="finding_high",
                severity="warning",
                payload_json={"risk": "high"},
            )
        )
        self._insert_audit_event(
            AuditEventEnvelope(
                organization_id="org_default",
                environment_id="env_default",
                event_type="custom.finding",
                source_component="custom-scanner",
                actor_type="system",
                resource_type="finding",
                resource_id="finding_low",
                severity="info",
                payload_json={"risk": "low"},
            )
        )

        recompute = self.client.post(
            "/api/v1/compliance/evidence/recompute",
            headers=self._headers(),
        )
        evidence = self.client.get(
            "/api/v1/compliance/evidence",
            headers=self._headers(),
            params={"control_id": control_id},
        )

        self.assertEqual(recompute.status_code, 201, recompute.text)
        matched = [
            item for item in evidence.json() if item["title"].startswith("custom_risk evidence")
        ]
        self.assertEqual(1, len(matched))
        self.assertEqual(matched_event_id, matched[0]["source_id"])


if __name__ == "__main__":
    unittest.main()
