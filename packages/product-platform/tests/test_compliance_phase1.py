from __future__ import annotations

import base64
import json
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.store import AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class CompliancePhase1AuditExplorerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            audit = AuditEventRepository(connection)
            audit.insert(
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="policy.decision",
                    source_component="policy-engine",
                    actor_type="user",
                    actor_id="user_policy",
                    agent_id="agent_compliance",
                    resource_type="policy_evaluation",
                    resource_id="peval_1",
                    decision="deny",
                    severity="warning",
                    correlation_id="corr-compliance",
                    policy_id="policy_1",
                    payload_json={"matched_rule": "deny_delete", "reason": "blocked"},
                )
            )
            audit.insert(
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="runtime.action",
                    source_component="runtime-control",
                    actor_type="system",
                    actor_id="worker",
                    resource_type="runtime_action",
                    resource_id="raction_1",
                    decision="allow",
                    severity="info",
                    correlation_id="corr-runtime",
                    payload_json={"action": "billing.lookup"},
                )
            )
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

    def test_audit_explorer_filters_planned_fields(self) -> None:
        response = self.client.get(
            "/api/v1/audit/events",
            headers=self._headers(),
            params={
                "source_component": "policy-engine",
                "actor_id": "user_policy",
                "actor_type": "user",
                "resource_type": "policy_evaluation",
                "resource_id": "peval_1",
                "severity": "warning",
                "decision": "deny",
                "correlation_id": "corr-compliance",
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        events = response.json()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source_component"], "policy-engine")
        self.assertEqual(events[0]["actor_id"], "user_policy")
        self.assertEqual(events[0]["resource_id"], "peval_1")

    def test_audit_export_stores_requested_filters(self) -> None:
        response = self.client.post(
            "/api/v1/audit/export",
            headers=self._headers(),
            json={
                "format": "json",
                "filters": {
                    "source_component": "policy-engine",
                    "actor_id": "user_policy",
                    "decision": "deny",
                    "empty": "",
                },
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertEqual(payload["organization_id"], "org_default")
        self.assertEqual(payload["format"], "json")
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["artifact_uri"].startswith("audit-export://"))
        self.assertNotIn("empty", payload["filters"])
        self.assertEqual(
            payload["filters"],
            {"actor_id": "user_policy", "decision": "deny", "source_component": "policy-engine"},
        )

        artifacts = self.client.get(
            "/api/v1/artifacts",
            headers=self._headers(),
            params={"artifact_type": "audit.export"},
        )
        self.assertEqual(artifacts.status_code, 200, artifacts.text)
        artifact_id = artifacts.json()[0]["id"]
        download = self.client.get(
            f"/api/v1/artifacts/{artifact_id}/download",
            headers=self._headers(),
        )
        self.assertEqual(download.status_code, 200, download.text)
        content = json.loads(base64.b64decode(download.json()["content_base64"]))
        self.assertEqual(content["event_count"], 1)
        self.assertEqual(content["events"][0]["event_type"], "policy.decision")
        self.assertEqual(content["events"][0]["actor_id"], "user_policy")

    def test_audit_export_rejects_unknown_filters(self) -> None:
        response = self.client.post(
            "/api/v1/audit/export",
            headers=self._headers(),
            json={"format": "json", "filters": {"unsupported": "value"}},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported audit export filter", response.text)

    def test_audit_export_rejects_environment_filter_mismatch(self) -> None:
        response = self.client.post(
            "/api/v1/audit/export",
            headers=self._headers(),
            json={"format": "json", "filters": {"environment_id": "env_other"}},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("environment filter must match", response.text)

    def test_audit_csv_export_escapes_spreadsheet_formula_cells(self) -> None:
        with self.database.transaction() as connection:
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="policy.decision",
                    source_component="policy-engine",
                    actor_type="user",
                    actor_id="=HYPERLINK(\"https://attacker.example\",\"click\")",
                    resource_type="policy_evaluation",
                    resource_id="@danger",
                    decision="deny",
                    severity="warning",
                    payload_json={"reason": "+SUM(1,1)"},
                )
            )

        response = self.client.post(
            "/api/v1/audit/export",
            headers=self._headers(),
            json={
                "format": "csv",
                "filters": {
                    "actor_id": "=HYPERLINK(\"https://attacker.example\",\"click\")",
                },
            },
        )
        self.assertEqual(response.status_code, 201, response.text)

        artifacts = self.client.get(
            "/api/v1/artifacts",
            headers=self._headers(),
            params={"artifact_type": "audit.export"},
        )
        artifact_id = artifacts.json()[0]["id"]
        download = self.client.get(
            f"/api/v1/artifacts/{artifact_id}/download",
            headers=self._headers(),
        )
        content = base64.b64decode(download.json()["content_base64"]).decode()

        self.assertIn("'=HYPERLINK", content)
        self.assertIn("'@danger", content)


if __name__ == "__main__":
    unittest.main()
