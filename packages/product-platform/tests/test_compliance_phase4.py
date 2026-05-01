from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class CompliancePhase4ReportTests(unittest.TestCase):
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

    def _soc2_framework_id(self) -> str:
        response = self.client.get("/api/v1/compliance/frameworks", headers=self._headers())
        self.assertEqual(response.status_code, 200, response.text)
        return next(framework["id"] for framework in response.json() if framework["name"] == "SOC 2")

    def _insert_policy_denial_and_recompute(self) -> None:
        with self.database.transaction() as connection:
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="policy.decision",
                    source_component="policy-engine",
                    actor_type="user",
                    actor_id="user_policy",
                    agent_id="agent_report",
                    resource_type="policy",
                    resource_id="policy_refund",
                    decision="deny",
                    severity="warning",
                    policy_id="policy_refund",
                    payload_json={"matched_rule": "refund_limit", "reason": "blocked by policy"},
                )
            )
        recompute = self.client.post(
            "/api/v1/compliance/evidence/recompute",
            headers=self._headers(),
        )
        self.assertEqual(recompute.status_code, 201, recompute.text)

    def _create_report(self) -> dict[str, object]:
        response = self.client.post(
            "/api/v1/compliance/reports",
            headers=self._headers(),
            json={
                "framework_id": self._soc2_framework_id(),
                "name": "SOC 2 Evidence Report",
                "date_from": "2020-01-01",
                "date_to": "2030-01-01",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_create_draft_report_and_reject_invalid_date_range(self) -> None:
        report = self._create_report()
        invalid = self.client.post(
            "/api/v1/compliance/reports",
            headers=self._headers(),
            json={
                "framework_id": self._soc2_framework_id(),
                "name": "Invalid Report",
                "date_from": "2030-01-01",
                "date_to": "2020-01-01",
            },
        )

        self.assertEqual(report["status"], "draft")
        self.assertEqual(report["summary"], {})
        self.assertEqual(invalid.status_code, 422, invalid.text)

    def test_generate_report_selects_evidence_and_open_violations(self) -> None:
        self._insert_policy_denial_and_recompute()
        report = self._create_report()

        generated = self.client.post(
            f"/api/v1/compliance/reports/{report['id']}/generate",
            headers=self._headers(),
        )

        self.assertEqual(generated.status_code, 200, generated.text)
        payload = generated.json()
        self.assertEqual(payload["status"], "generated")
        self.assertTrue(payload["artifact_uri"].startswith("compliance-report://"))
        self.assertGreaterEqual(payload["summary"]["evidence_count"], 1)
        self.assertGreaterEqual(payload["summary"]["open_violation_count"], 1)
        self.assertGreaterEqual(len(payload["evidence_item_ids"]), 1)
        self.assertIn("SOC 2", payload["rendered_markdown"])
        self.assertIn("## Evidence", payload["rendered_markdown"])
        self.assertIn("policy_decision evidence", payload["rendered_markdown"])
        self.assertIn("## Open Violations", payload["rendered_markdown"])
        self.assertIn("Audit hash status:", payload["rendered_markdown"])

    def test_download_returns_generated_markdown(self) -> None:
        self._insert_policy_denial_and_recompute()
        report = self._create_report()
        generated = self.client.post(
            f"/api/v1/compliance/reports/{report['id']}/generate",
            headers=self._headers(),
        )
        self.assertEqual(generated.status_code, 200, generated.text)

        downloaded = self.client.get(
            f"/api/v1/compliance/reports/{report['id']}/download",
            headers=self._headers(),
        )

        self.assertEqual(downloaded.status_code, 200, downloaded.text)
        self.assertIn("# SOC 2 Evidence Report", downloaded.text)
        self.assertIn("Audit hash status:", downloaded.text)

    def test_attestation_requires_statement_and_emits_audit_event(self) -> None:
        self._insert_policy_denial_and_recompute()
        report = self._create_report()
        generated = self.client.post(
            f"/api/v1/compliance/reports/{report['id']}/generate",
            headers=self._headers(),
        )
        self.assertEqual(generated.status_code, 200, generated.text)

        rejected = self.client.post(
            f"/api/v1/compliance/reports/{report['id']}/attest",
            headers=self._headers(),
            json={"statement": ""},
        )
        attested = self.client.post(
            f"/api/v1/compliance/reports/{report['id']}/attest",
            headers=self._headers(),
            json={"statement": "I attest this evidence package.", "signature_ref": "sig-1"},
        )

        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertEqual(attested.status_code, 201, attested.text)
        self.assertEqual("sig-1", attested.json()["signature_ref"])
        loaded = self.client.get(
            f"/api/v1/compliance/reports/{report['id']}",
            headers=self._headers(),
        )
        self.assertEqual(loaded.json()["status"], "attested")
        self.assertEqual(1, loaded.json()["attestation_count"])
        with self.database.connect() as connection:
            events = AuditEventRepository(connection).query(
                AuditEventQuery(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="compliance.report.attested",
                    resource_id=report["id"],
                    limit=10,
                )
            )
        self.assertEqual(1, len(events))
        self.assertEqual("attested", events[0].decision)


if __name__ == "__main__":
    unittest.main()
