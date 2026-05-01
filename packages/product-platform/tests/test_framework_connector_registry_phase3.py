from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class FrameworkAgentLinksPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_demo", "Demo Support Agent", "env_default")
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["framework-agents@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "framework-agents@example.com", "roles": ["Platform Admin"]},
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

    def _create_instance(self) -> dict:
        response = self.client.post(
            "/api/v1/integrations/framework-instances",
            headers=self._headers(),
            json={
                "integration_id": "openai_agents",
                "name": "OpenAI Agents connector",
                "config": {"project": "demo-project"},
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _link_agent(self, instance_id: str) -> dict:
        response = self.client.post(
            f"/api/v1/integrations/framework-instances/{instance_id}/link-agent",
            headers=self._headers(),
            json={
                "agent_id": "agent_demo",
                "framework_agent_ref": "assistant:demo-support",
                "sdk_version": "0.3.0",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_links_agent_to_connector(self) -> None:
        instance = self._create_instance()

        link = self._link_agent(instance["id"])

        self.assertEqual(link["integration_instance_id"], instance["id"])
        self.assertEqual(link["agent_id"], "agent_demo")
        self.assertEqual(link["agent_name"], "Demo Support Agent")
        self.assertEqual(link["framework_agent_ref"], "assistant:demo-support")
        listed = self.client.get("/api/v1/integrations/framework-agents", headers=self._headers())
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()[0]["id"], link["id"])

    def test_cannot_link_agent_from_another_environment(self) -> None:
        instance = self._create_instance()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO environments (id, organization_id, name, slug, type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("env_other", "org_default", "Other", "other", "development", "2026-05-01T00:00:00Z", "2026-05-01T00:00:00Z"),
            )
            self._insert_agent(connection, "agent_other", "Other Agent", "env_other")

        response = self.client.post(
            f"/api/v1/integrations/framework-instances/{instance['id']}/link-agent",
            headers=self._headers(),
            json={
                "agent_id": "agent_other",
                "framework_agent_ref": "assistant:other",
                "sdk_version": "0.3.0",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("selected environment", response.json()["message"])

    def test_coverage_status_defaults_to_unknown_until_health_check(self) -> None:
        instance = self._create_instance()

        link = self._link_agent(instance["id"])

        self.assertEqual(link["telemetry_status"], "unknown")
        self.assertEqual(link["policy_coverage_status"], "unknown")

    def test_unlink_emits_audit_event(self) -> None:
        instance = self._create_instance()
        link = self._link_agent(instance["id"])

        response = self.client.delete(
            f"/api/v1/integrations/framework-agents/{link['id']}",
            headers=self._headers("corr_unlink_framework_agent"),
        )

        self.assertEqual(response.status_code, 204, response.text)
        with self.database.transaction() as connection:
            audit = connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE event_type = ?
                  AND resource_id = ?
                  AND correlation_id = ?
                """,
                ("integration.framework_agent.unlinked", link["id"], "corr_unlink_framework_agent"),
            ).fetchone()
        self.assertIsNotNone(audit)

    def _insert_agent(self, connection, agent_id: str, name: str, environment_id: str) -> None:
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
                agent_id,
                "org_default",
                environment_id,
                name,
                "Demo framework-linked agent.",
                "openai_agents",
                "service",
                "user_admin",
                "user_admin",
                "active",
                "2026-05-01T00:00:00Z",
                "2026-05-01T00:00:00Z",
            ),
        )


if __name__ == "__main__":
    unittest.main()
