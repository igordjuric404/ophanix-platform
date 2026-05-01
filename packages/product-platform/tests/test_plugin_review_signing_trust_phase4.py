from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.marketplace.samples import sample_plugin_manifests
from product_platform.marketplace.usage_trust import (
    PluginUsageSignals,
    compute_usage_trust_delta,
)


class PluginUsageTrustPhase4Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["trust@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "trust@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _import_plugin(self) -> dict:
        response = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": {**sample_plugin_manifests()[0], "name": "usage-trust-assistant"}},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_successful_usage_increases_trust(self) -> None:
        delta, reason = compute_usage_trust_delta(
            PluginUsageSignals(
                daily_active_users=1000,
                total_invocations=5000,
                error_count=2,
                adoption_trend=0.2,
            )
        )

        self.assertGreater(delta, 0)
        self.assertIn("high adoption", reason)

    def test_incident_decreases_trust(self) -> None:
        delta, reason = compute_usage_trust_delta(
            PluginUsageSignals(
                daily_active_users=100,
                total_invocations=2000,
                error_count=400,
                incident_count=2,
            )
        )

        self.assertLess(delta, 0)
        self.assertIn("incident penalty", reason)

    def test_trust_recomputation_updates_tier(self) -> None:
        plugin = self._import_plugin()
        version_id = plugin["versions"][0]["id"]

        response = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/recompute-trust",
            headers=self._headers(),
            json={
                "daily_active_users": 1000,
                "total_invocations": 5000,
                "error_count": 2,
                "adoption_trend": 0.2,
                "source_event_id": "usage_event_1",
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        event = response.json()
        self.assertEqual(event["plugin_version_id"], version_id)
        self.assertGreater(event["delta"], 0)
        self.assertEqual(event["trust_tier"], "trusted")

        detail = self.client.get(
            f"/api/v1/marketplace/plugins/{plugin['id']}",
            headers=self._headers(),
        )
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["versions"][0]["trust_tier"], "trusted")


if __name__ == "__main__":
    unittest.main()
