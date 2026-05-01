from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class DiscoveryScanRunnerPhase3Tests(unittest.TestCase):
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

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _create_config_target(self, path: str) -> str:
        response = self.client.post(
            "/api/v1/discovery/targets",
            headers=self._headers(),
            json={
                "scanner_type": "config",
                "target_type": "filesystem",
                "target_value": path,
                "config_json": {"paths": [path], "max_depth": 2},
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_integration_config_scanner_run_persists_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "agentmesh.yaml"), "w", encoding="utf-8") as file:
                file.write("name: demo-agent\n")
            target_id = self._create_config_target(tmpdir)

            response = self.client.post(
                "/api/v1/discovery/runs",
                headers=self._headers(),
                json={"target_id": target_id},
            )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["target_id"], target_id)
        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["summary_json"]["raw_finding_count"], 1)
        self.assertEqual(payload["raw_finding_count"], 1)

        detail = self.client.get(
            f"/api/v1/discovery/runs/{payload['id']}",
            headers=self._headers(),
        )
        self.assertEqual(detail.status_code, 200)
        findings = detail.json()["raw_findings"]
        self.assertEqual(len(findings), 1)
        self.assertIn("agt agent at agentmesh.yaml", findings[0]["raw_payload_json"]["name"])

    def test_integration_failed_scan_records_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target_id = self._create_config_target(tmpdir)

        response = self.client.post(
            "/api/v1/discovery/runs",
            headers=self._headers(),
            json={"target_id": target_id},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["status"], "failed")
        self.assertIn("valid directory", payload["error_message"])
        self.assertEqual(payload["raw_finding_count"], 0)

    def test_integration_completion_emits_audit_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "agentmesh.yaml"), "w", encoding="utf-8") as file:
                file.write("name: auditable-agent\n")
            target_id = self._create_config_target(tmpdir)
            run = self.client.post(
                "/api/v1/discovery/runs",
                headers=self._headers(),
                json={"target_id": target_id},
            ).json()

        audit_response = self.client.get(
            "/api/v1/audit/events",
            headers=self._headers(),
            params={"resource_type": "discovery_run", "resource_id": run["id"]},
        )

        self.assertEqual(audit_response.status_code, 200)
        event_types = [event["event_type"] for event in audit_response.json()]
        self.assertIn("discovery.scan.started", event_types)
        self.assertIn("discovery.scan.completed", event_types)


if __name__ == "__main__":
    unittest.main()
