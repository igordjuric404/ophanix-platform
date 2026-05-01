from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class FrameworkConnectorRegistryOverallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            connection.execute(
                """
                INSERT INTO agents (
                    id, organization_id, environment_id, name, description, framework,
                    runtime_type, owner_user_id, sponsor_user_id, status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "agent_demo_support",
                    "org_default",
                    "env_default",
                    "Demo Support Agent",
                    "Handles support triage.",
                    "openai_agents",
                    "service",
                    "user_admin",
                    "user_admin",
                    "active",
                    "2026-05-01T00:00:00Z",
                    "2026-05-01T00:00:00Z",
                ),
            )
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["integrations-overall@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "integrations-overall@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self, correlation_id: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        return headers

    def test_configure_link_show_and_audit_framework_connector(self) -> None:
        frameworks = self.client.get("/api/v1/integrations/frameworks", headers=self._headers())
        self.assertEqual(frameworks.status_code, 200, frameworks.text)
        openai = next(item for item in frameworks.json() if item["id"] == "openai_agents")
        self.assertIn("ophanix integrations init openai_agents", openai["setup_snippet"])

        instance = self.client.post(
            "/api/v1/integrations/framework-instances",
            headers=self._headers("corr_create_connector"),
            json={
                "integration_id": "openai_agents",
                "name": "OpenAI Agents support connector",
                "config": {"project": "support-demo"},
            },
        )
        self.assertEqual(instance.status_code, 201, instance.text)

        link = self.client.post(
            f"/api/v1/integrations/framework-instances/{instance.json()['id']}/link-agent",
            headers=self._headers("corr_link_connector"),
            json={
                "agent_id": "agent_demo_support",
                "framework_agent_ref": "assistant:support-demo",
                "sdk_version": "0.3.0",
            },
        )
        self.assertEqual(link.status_code, 201, link.text)
        self.assertEqual(link.json()["telemetry_status"], "unknown")
        self.assertEqual(link.json()["policy_coverage_status"], "unknown")

        listed_links = self.client.get("/api/v1/integrations/framework-agents", headers=self._headers())
        self.assertEqual(listed_links.status_code, 200, listed_links.text)
        self.assertEqual(listed_links.json()[0]["agent_name"], "Demo Support Agent")

        with self.database.transaction() as connection:
            create_audit = connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE event_type = ?
                  AND resource_id = ?
                  AND correlation_id = ?
                """,
                ("integration.instance.created", instance.json()["id"], "corr_create_connector"),
            ).fetchone()
            link_audit = connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE event_type = ?
                  AND resource_id = ?
                  AND correlation_id = ?
                """,
                ("integration.framework_agent.linked", link.json()["id"], "corr_link_connector"),
            ).fetchone()
        self.assertIsNotNone(create_audit)
        self.assertIsNotNone(link_audit)


if __name__ == "__main__":
    unittest.main()
