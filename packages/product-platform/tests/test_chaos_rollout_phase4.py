from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class RolloutActionsPhase4Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["rollout-actions@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "rollout-actions@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _create_rollout(self) -> dict:
        response = self.client.post(
            "/api/v1/observability/rollouts",
            headers=self._headers(),
            json={
                "name": "Demo canary rollout",
                "target_type": "agent",
                "target_id": "agent_demo",
                "strategy": "canary",
                "config": {
                    "stages": [5, 25, 100],
                    "gates": {"require_slo_healthy": True},
                },
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_advance_changes_stage(self) -> None:
        rollout = self._create_rollout()

        response = self.client.post(
            f"/api/v1/observability/rollouts/{rollout['id']}/advance",
            headers=self._headers(),
            json={"metrics": {"slo_status": "healthy"}},
        )

        self.assertEqual(response.status_code, 200, response.text)
        advanced = response.json()
        self.assertEqual(advanced["current_stage"], 5)
        self.assertEqual(advanced["status"], "running")
        self.assertEqual(advanced["events"][0]["decision"], "advanced")
        self.assertEqual(advanced["events"][0]["metrics"]["to_stage"], 5)

    def test_rollback_changes_status(self) -> None:
        rollout = self._create_rollout()
        advance = self.client.post(
            f"/api/v1/observability/rollouts/{rollout['id']}/advance",
            headers=self._headers(),
            json={"metrics": {"slo_status": "healthy"}},
        )
        self.assertEqual(advance.status_code, 200, advance.text)

        response = self.client.post(
            f"/api/v1/observability/rollouts/{rollout['id']}/rollback",
            headers=self._headers(),
            json={"reason": "Canary quality dropped"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        rolled_back = response.json()
        self.assertEqual(rolled_back["status"], "rolled_back")
        self.assertEqual(rolled_back["current_stage"], 0)
        self.assertEqual(rolled_back["events"][0]["decision"], "rolled_back")
        self.assertEqual(rolled_back["events"][0]["metrics"]["reason"], "Canary quality dropped")


if __name__ == "__main__":
    unittest.main()
