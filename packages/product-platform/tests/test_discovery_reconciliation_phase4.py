from __future__ import annotations

import json
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.discovery.findings import DiscoveryFindingRepository
from product_platform.discovery.models import DiscoveryTargetCreateRequest
from product_platform.discovery.repository import DiscoveryRepository


class DiscoveryReconciliationPhase4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            discovery = DiscoveryRepository(connection, "org_default", "env_default")
            target = discovery.create_target(
                DiscoveryTargetCreateRequest(
                    scanner_type="process",
                    target_type="host",
                    target_value="localhost",
                    config_json={},
                )
            )
            self.run = discovery.create_run(target)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
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
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _create_finding(self, fingerprint: str = "fp_action", name: str = "Action Agent") -> str:
        payload = {
            "fingerprint": fingerprint,
            "name": name,
            "agent_type": "crewai",
            "confidence": 0.95,
            "merge_keys": {"config_path": "/repo/agentmesh.yaml"},
            "first_seen_at": "2026-04-30T10:00:00+00:00",
            "last_seen_at": "2026-04-30T10:00:00+00:00",
            "evidence": [
                {
                    "scanner": "config",
                    "basis": "config_file",
                    "source": "/repo/agentmesh.yaml",
                    "detail": "Agent config file",
                    "confidence": 0.95,
                    "timestamp": "2026-04-30T10:00:00+00:00",
                }
            ],
        }
        with self.database.transaction() as connection:
            discovery = DiscoveryRepository(connection, "org_default", "env_default")
            discovery.persist_raw_findings(self.run["id"], [json.loads(json.dumps(payload))])
            repository = DiscoveryFindingRepository(connection, "org_default", "env_default")
            finding = repository.reconcile_run(self.run["id"])[0]
            repository.score_finding(finding["id"])
            return finding["id"]

    def test_api_assign_owner_updates_finding(self) -> None:
        finding_id = self._create_finding()

        response = self.client.post(
            f"/api/v1/discovery/findings/{finding_id}/assign-owner",
            headers=self._headers(),
            json={"owner_user_id": "owner_42"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["owner_hint"], "owner_42")
        self.assertEqual(payload["status"], "owner_assigned")

    def test_api_suppress_requires_reason(self) -> None:
        finding_id = self._create_finding("fp_suppress")

        response = self.client.post(
            f"/api/v1/discovery/findings/{finding_id}/suppress",
            headers=self._headers(),
            json={},
        )

        self.assertEqual(response.status_code, 422)

    def test_api_register_creates_agent_draft(self) -> None:
        finding_id = self._create_finding("fp_register", "Registerable Agent")

        response = self.client.post(
            f"/api/v1/discovery/findings/{finding_id}/register-agent",
            headers=self._headers(),
            json={"owner_user_id": "owner_1", "sponsor_user_id": "sponsor_1"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "registration_draft_created")
        self.assertTrue(payload["registry_agent_id"].startswith("agent_"))

        agent = self.client.get(
            f"/api/v1/agents/{payload['registry_agent_id']}",
            headers=self._headers(),
        )
        self.assertEqual(agent.status_code, 200)
        self.assertEqual(agent.json()["summary"]["name"], "Registerable Agent")

    def test_integration_triage_action_emits_audit_event(self) -> None:
        finding_id = self._create_finding("fp_audit")
        action = self.client.post(
            f"/api/v1/discovery/findings/{finding_id}/assign-owner",
            headers=self._headers(),
            json={"owner_user_id": "owner_audit"},
        )
        audit = self.client.get(
            "/api/v1/audit/events",
            headers=self._headers(),
            params={"resource_type": "discovery_finding", "resource_id": finding_id},
        )

        self.assertEqual(action.status_code, 200)
        self.assertEqual(audit.status_code, 200)
        self.assertIn("discovery.finding.action", {event["event_type"] for event in audit.json()})


if __name__ == "__main__":
    unittest.main()
