from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class DiscoveryReconciliationOverallValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
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
        self.user = login.json()["user"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def test_scan_reconcile_register_shadow_finding_and_emit_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "agentmesh.yaml"), "w", encoding="utf-8") as file:
                file.write("name: overall-shadow-agent\nframework: agentmesh\n")

            target = self.client.post(
                "/api/v1/discovery/targets",
                headers=self._headers(),
                json={
                    "scanner_type": "config",
                    "target_type": "filesystem",
                    "target_value": tmpdir,
                    "config_json": {"paths": [tmpdir], "max_depth": 2},
                },
            )
            self.assertEqual(target.status_code, 201)

            run = self.client.post(
                "/api/v1/discovery/runs",
                headers=self._headers(),
                json={"target_id": target.json()["id"]},
            )
            self.assertEqual(run.status_code, 201)

        run_payload = run.json()
        self.assertEqual(run_payload["status"], "succeeded")
        self.assertEqual(run_payload["raw_finding_count"], 1)

        reconciled = self.client.post(
            f"/api/v1/discovery/reconcile-run/{run_payload['id']}",
            headers=self._headers(),
        )
        self.assertEqual(reconciled.status_code, 200)
        findings = reconciled.json()
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["status"], "shadow_candidate")
        self.assertIn(finding["risk_level"], {"high", "critical"})
        self.assertEqual(len(finding["evidence"]), 1)

        shadow_queue = self.client.get(
            "/api/v1/discovery/findings",
            headers=self._headers(),
            params={"status": "shadow_candidate", "registry_match": "unmatched"},
        )
        self.assertEqual(shadow_queue.status_code, 200)
        self.assertIn(finding["id"], {item["id"] for item in shadow_queue.json()})

        registered = self.client.post(
            f"/api/v1/discovery/findings/{finding['id']}/register-agent",
            headers=self._headers(),
            json={
                "owner_user_id": self.user["id"],
                "sponsor_user_id": self.user["id"],
                "runtime_type": "service",
            },
        )
        self.assertEqual(registered.status_code, 200)
        registered_payload = registered.json()
        agent_id = registered_payload["registry_agent_id"]
        self.assertEqual(registered_payload["status"], "registration_draft_created")
        self.assertTrue(agent_id.startswith("agent_"))

        inventory = self.client.get(
            "/api/v1/agents",
            headers=self._headers(),
            params={"status": "draft", "owner_user_id": self.user["id"]},
        )
        detail = self.client.get(f"/api/v1/agents/{agent_id}", headers=self._headers())
        audit = self.client.get(
            "/api/v1/audit/events",
            headers=self._headers(),
            params={"resource_type": "discovery_finding", "resource_id": finding["id"]},
        )

        self.assertEqual(inventory.status_code, 200)
        self.assertIn(agent_id, {agent["id"] for agent in inventory.json()})
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["summary"]["id"], agent_id)
        self.assertEqual(detail.json()["summary"]["status"], "draft")
        self.assertEqual(audit.status_code, 200)
        self.assertIn("discovery.finding.action", {event["event_type"] for event in audit.json()})


if __name__ == "__main__":
    unittest.main()
