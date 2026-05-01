from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.trust.repository import TrustRepository


class HandshakesThresholdsPhase1Tests(unittest.TestCase):
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
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def test_default_thresholds_are_seeded_idempotently(self) -> None:
        with self.database.transaction() as connection:
            repository = TrustRepository(connection, "org_default", "env_default")
            first_seed = repository.seed_default_thresholds()
            second_seed = repository.seed_default_thresholds()

            thresholds = {row["threshold_type"]: row for row in second_seed}

            self.assertEqual(len(first_seed), 4)
            self.assertEqual(len(second_seed), 4)
            self.assertEqual(thresholds["handoff"]["min_score"], 700)
            self.assertEqual(thresholds["handoff"]["required_tier"], "trusted")
            self.assertEqual(thresholds["mcp_tool_use"]["min_score"], 650)
            self.assertEqual(thresholds["privileged_runtime_action"]["min_score"], 850)
            self.assertEqual(thresholds["marketplace_install"]["min_score"], 600)

    def test_api_creates_threshold(self) -> None:
        response = self.client.post(
            "/api/v1/trust/thresholds",
            headers=self._headers(),
            json={
                "threshold_type": "protocol_bridge_use",
                "target_type": "bridge",
                "target_id": "bridge_alpha",
                "min_score": 720,
                "required_tier": "trusted",
                "enabled": True,
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["threshold_type"], "protocol_bridge_use")
        self.assertEqual(payload["target_type"], "bridge")
        self.assertEqual(payload["target_id"], "bridge_alpha")
        self.assertEqual(payload["min_score"], 720)

    def test_api_rejects_invalid_score(self) -> None:
        response = self.client.post(
            "/api/v1/trust/thresholds",
            headers=self._headers(),
            json={
                "threshold_type": "handoff",
                "target_type": "environment",
                "min_score": 1001,
                "required_tier": "trusted",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_api_lists_and_patches_threshold(self) -> None:
        listed = self.client.get(
            "/api/v1/trust/thresholds",
            headers=self._headers(),
        )
        self.assertEqual(listed.status_code, 200)
        handoff = next(
            item for item in listed.json() if item["threshold_type"] == "handoff"
        )

        patched = self.client.patch(
            f"/api/v1/trust/thresholds/{handoff['id']}",
            headers=self._headers(),
            json={"min_score": 710, "enabled": False},
        )

        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["min_score"], 710)
        self.assertEqual(patched.json()["enabled"], False)


if __name__ == "__main__":
    unittest.main()
