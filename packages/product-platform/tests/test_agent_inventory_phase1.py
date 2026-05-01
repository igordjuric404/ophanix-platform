from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.api.tenancy import Environment, TenantStore
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class AgentInventoryPhase1ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            connection.execute(
                """
                INSERT INTO environments
                    (id, organization_id, name, slug, type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "env_other",
                    "org_default",
                    "Other",
                    "other",
                    "development",
                    "2026-04-30T00:00:00+00:00",
                    "2026-04-30T00:00:00+00:00",
                ),
            )
            self._insert_agent(
                connection,
                agent_id="agent_alpha",
                environment_id="env_default",
                name="Alpha",
                status="active",
                last_heartbeat_at="2026-04-30T09:00:00+00:00",
            )
            self._insert_agent(
                connection,
                agent_id="agent_beta",
                environment_id="env_default",
                name="Beta",
                status="draft",
                framework="crewai",
                last_heartbeat_at="2026-04-30T10:00:00+00:00",
            )
            self._insert_agent(
                connection,
                agent_id="agent_gamma",
                environment_id="env_default",
                name="Gamma",
                status="active",
                last_heartbeat_at="2026-04-30T11:00:00+00:00",
            )
            self._insert_agent(
                connection,
                agent_id="agent_other_env",
                environment_id="env_other",
                name="Other Env",
                status="active",
            )
        tenant_store = TenantStore(
            environments=[
                Environment(
                    id="env_default",
                    organization_id="org_default",
                    name="Development",
                    slug="development",
                    type="development",
                    created_at="2026-04-30T00:00:00+00:00",
                ),
                Environment(
                    id="env_other",
                    organization_id="org_default",
                    name="Other",
                    slug="other",
                    type="development",
                    created_at="2026-04-30T00:00:00+00:00",
                ),
            ]
        )
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=["viewer@example.com"],
                session_secret="test-secret",
            ),
            tenant_store=tenant_store,
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "viewer@example.com", "roles": ["Viewer"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _insert_agent(
        self,
        connection,
        *,
        agent_id: str,
        environment_id: str,
        name: str,
        status: str,
        framework: str = "langgraph",
        last_heartbeat_at: str | None = None,
    ) -> None:
        now = "2026-04-30T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, endpoint_url, owner_user_id, sponsor_user_id, status,
                trust_score, trust_tier, credential_status, credential_expires_at,
                last_heartbeat_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                "org_default",
                environment_id,
                name,
                f"{name} description",
                framework,
                "service",
                None,
                "owner_1",
                "sponsor_1",
                status,
                700.0,
                "standard",
                "active",
                "2026-05-01T00:00:00+00:00",
                last_heartbeat_at,
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO agent_capabilities (
                id, agent_id, capability_name, resource_type, status,
                requested_by, approved_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"cap_{agent_id}",
                agent_id,
                "claims:read",
                "claim",
                "approved",
                "owner_1",
                "owner_1",
                now,
            ),
        )

    def _headers(self, environment_id: str = "env_default") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": environment_id,
        }

    def test_list_returns_only_current_environment(self) -> None:
        response = self.client.get("/api/v1/agents", headers=self._headers())

        self.assertEqual(response.status_code, 200)
        ids = {agent["id"] for agent in response.json()}
        self.assertEqual(ids, {"agent_alpha", "agent_beta", "agent_gamma"})

    def test_status_filter_works(self) -> None:
        response = self.client.get(
            "/api/v1/agents?status=active",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {agent["id"] for agent in response.json()},
            {"agent_alpha", "agent_gamma"},
        )

    def test_pagination_is_stable(self) -> None:
        first_page = self.client.get(
            "/api/v1/agents?sort=name&limit=2&offset=0",
            headers=self._headers(),
        )
        second_page = self.client.get(
            "/api/v1/agents?sort=name&limit=2&offset=2",
            headers=self._headers(),
        )

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual([agent["id"] for agent in first_page.json()], ["agent_alpha", "agent_beta"])
        self.assertEqual([agent["id"] for agent in second_page.json()], ["agent_gamma"])

    def test_sorting_by_last_heartbeat_descending(self) -> None:
        response = self.client.get(
            "/api/v1/agents?sort=-last_heartbeat",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [agent["id"] for agent in response.json()],
            ["agent_gamma", "agent_beta", "agent_alpha"],
        )


if __name__ == "__main__":
    unittest.main()
