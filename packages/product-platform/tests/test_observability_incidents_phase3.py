from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.store import AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class ObservabilityIncidentsPhase3Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["incident@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "incident@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _create_incident(self) -> dict:
        response = self.client.post(
            "/api/v1/observability/incidents",
            headers=self._headers(),
            json={
                "severity": "critical",
                "title": "Repeated policy denials",
                "summary": "Agent demo is repeatedly denied by policy.",
                "correlation_id": "corr_incident_manual",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_create_incident(self) -> None:
        incident = self._create_incident()

        self.assertEqual(incident["status"], "open")
        self.assertEqual(incident["severity"], "critical")
        self.assertEqual(incident["correlation_id"], "corr_incident_manual")

        listed = self.client.get("/api/v1/observability/incidents", headers=self._headers())
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()[0]["id"], incident["id"])

    def test_acknowledge_changes_status(self) -> None:
        incident = self._create_incident()

        response = self.client.post(
            f"/api/v1/observability/incidents/{incident['id']}/ack",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "acknowledged")
        self.assertIsNotNone(response.json()["acknowledged_at"])

    def test_resolve_requires_resolution_note(self) -> None:
        incident = self._create_incident()

        response = self.client.post(
            f"/api/v1/observability/incidents/{incident['id']}/resolve",
            headers=self._headers(),
            json={},
        )

        self.assertEqual(response.status_code, 422)

    def test_incident_links_to_audit_events(self) -> None:
        with self.database.transaction() as connection:
            repository = AuditEventRepository(connection)
            first = repository.insert(
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="policy.decision",
                    source_component="policy-engine",
                    actor_type="system",
                    resource_type="policy",
                    resource_id="pol_default",
                    decision="deny",
                    severity="critical",
                    correlation_id="corr_repeated_denials",
                    payload_json={"reason": "too many denials"},
                )
            )
            second = repository.insert(
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="runtime.action",
                    source_component="runtime-control",
                    actor_type="system",
                    resource_type="runtime_action",
                    resource_id="act_denied",
                    decision="deny",
                    severity="warning",
                    correlation_id="corr_repeated_denials",
                    payload_json={"action": "invoke"},
                )
            )

        response = self.client.post(
            "/api/v1/observability/incidents/from-event",
            headers=self._headers(),
            json={"source_event_id": first.id, "title": "Repeated denials"},
        )

        self.assertEqual(response.status_code, 201, response.text)
        incident = response.json()
        self.assertEqual(incident["source_event_id"], first.id)
        self.assertEqual(incident["correlation_id"], "corr_repeated_denials")
        self.assertIn(first.id, incident["related_event_ids"])
        self.assertIn(second.id, incident["related_event_ids"])


if __name__ == "__main__":
    unittest.main()
