from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class DiscoveryScanRunnerOverallValidationTests(unittest.TestCase):
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

    def test_config_scan_end_to_end_persists_history_findings_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "agentmesh.yaml"), "w", encoding="utf-8") as file:
                file.write("name: overall-validation-agent\nframework: agentmesh\n")

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

        detail = self.client.get(
            f"/api/v1/discovery/runs/{run_payload['id']}",
            headers=self._headers(),
        )
        history = self.client.get("/api/v1/discovery/runs", headers=self._headers())
        audit = self.client.get(
            "/api/v1/audit/events",
            headers=self._headers(),
            params={"resource_type": "discovery_run", "resource_id": run_payload["id"]},
        )

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(audit.status_code, 200)
        finding_payload = detail.json()["raw_findings"][0]["raw_payload_json"]
        self.assertEqual(finding_payload["agent_type"], "agt")
        self.assertIn(run_payload["id"], {item["id"] for item in history.json()})
        self.assertEqual(
            {event["event_type"] for event in audit.json()},
            {"discovery.scan.started", "discovery.scan.completed"},
        )


if __name__ == "__main__":
    unittest.main()
