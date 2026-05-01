from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.marketplace.quality import assess_plugin_quality
from product_platform.marketplace.samples import sample_plugin_manifests


class PluginQualityAssessmentPhase3Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["quality@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "quality@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def test_low_documentation_score_generates_finding(self) -> None:
        assessment = assess_plugin_quality(
            {
                "name": "low-docs",
                "version": "1.0.0",
                "signature": "demo",
                "documentation": {"readme": False, "examples": False},
                "tests": {"count": 20, "integration": True, "edge_cases": True},
                "operations": {"health_check": True, "rollback": True, "owner": "team"},
            }
        )

        codes = {finding["code"] for finding in assessment.findings}
        self.assertIn("low_documentation", codes)

    def test_quality_assessment_persists_score(self) -> None:
        manifest = {
            **sample_plugin_manifests()[0],
            "name": "quality-ready-assistant",
            "documentation": {"readme": True, "examples": True, "api_docs": True, "changelog": True},
            "tests": {"count": 20, "integration": True, "edge_cases": True},
            "operations": {"health_check": True, "rollback": True, "owner": "platform"},
        }
        imported = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(imported.status_code, 201, imported.text)
        version_id = imported.json()["versions"][0]["id"]

        response = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/assess-quality",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 201, response.text)
        assessment = response.json()
        self.assertEqual(assessment["plugin_version_id"], version_id)
        self.assertGreaterEqual(assessment["score"], 90)
        self.assertEqual(assessment["findings"], [])

        detail = self.client.get(
            f"/api/v1/marketplace/plugins/{imported.json()['id']}",
            headers=self._headers(),
        )
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["versions"][0]["quality_score"], assessment["score"])


if __name__ == "__main__":
    unittest.main()
