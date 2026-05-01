from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class PolicyEditorPhase4AffectedResourcesTests(unittest.TestCase):
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
            json={"email": "admin@example.com", "roles": ["Policy Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "X-Request-ID": "req-policy-impact"}

    def test_api_affected_resources_are_organization_scoped(self) -> None:
        policy = self.client.post(
            "/api/v1/policies",
            headers=self._headers(),
            json={"name": "Impact Guard", "scope": "agent"},
        )
        self.assertEqual(policy.status_code, 201)
        policy_id = policy.json()["id"]
        with self.database.transaction() as connection:
            now = "2026-05-01T00:00:00+00:00"
            connection.execute(
                """
                INSERT INTO organizations (id, name, slug, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("org_other", "Other Org", "other-org", now, now),
            )
            connection.execute(
                """
                INSERT INTO environments (id, organization_id, name, slug, type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("env_other", "org_other", "Other", "other", "development", now, now),
            )
            for agent_id, org_id, env_id, name in [
                ("agent_default", "org_default", "env_default", "Default Agent"),
                ("agent_other", "org_other", "env_other", "Other Agent"),
            ]:
                connection.execute(
                    """
                    INSERT INTO agents (
                        id, organization_id, environment_id, name, description, framework,
                        runtime_type, owner_user_id, sponsor_user_id, status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        agent_id,
                        org_id,
                        env_id,
                        name,
                        "",
                        "langgraph",
                        "service",
                        "owner",
                        "sponsor",
                        "active",
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO agent_policy_selections (
                        id, agent_id, policy_id, selection_type, status, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"aps_{agent_id}",
                        agent_id,
                        policy_id,
                        "policy_binding",
                        "selected",
                        now,
                    ),
                )

        response = self.client.get(
            f"/api/v1/policies/{policy_id}/affected-resources",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["policy_id"], policy_id)
        self.assertEqual(len(payload["resources"]), 1)
        self.assertEqual(payload["resources"][0]["target_id"], "agent_default")
        self.assertEqual(payload["resources"][0]["label"], "Default Agent")


if __name__ == "__main__":
    unittest.main()
