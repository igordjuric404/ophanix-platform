from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.runtime.models import SandboxProfileCreateRequest, SandboxProfileTestRequest
from product_platform.runtime.sandbox import SandboxProfileRepository, SandboxTestAdapter


class SandboxProfilesPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_sandbox", "Sandboxed Agent")
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["security@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "security@example.com", "roles": ["Security Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _insert_agent(self, connection, agent_id: str, name: str) -> None:
        now = "2026-05-01T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, owner_user_id, sponsor_user_id, status, trust_score,
                trust_tier, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                "org_default",
                "env_default",
                name,
                "Sandbox test agent",
                "langgraph",
                "service",
                "user_admin",
                "user_admin",
                "active",
                760,
                "trusted",
                now,
                now,
            ),
        )

    def _create_profile_api(self) -> dict:
        created = self.client.post(
            "/api/v1/runtime/sandbox-profiles",
            headers=self._headers(),
            json={
                "name": "Strict Sandbox",
                "provider_type": "subprocess",
                "blocked_imports": ["os", "subprocess", "socket"],
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        return created.json()

    def test_blocked_import_is_denied_by_adapter(self) -> None:
        with self.database.transaction() as connection:
            repository = SandboxProfileRepository(connection, "org_default", "env_default")
            profile = repository.create_profile(
                SandboxProfileCreateRequest(
                    name="Adapter Sandbox",
                    provider_type="subprocess",
                    blocked_imports=["os"],
                )
            )

            decision = SandboxTestAdapter(repository).test_profile(
                profile["id"],
                SandboxProfileTestRequest(code="import os\nprint(os.getcwd())"),
            )

            self.assertEqual(decision.decision, "denied")
            self.assertIn("blocked module 'os'", decision.reason)
            self.assertEqual(decision.violations[0].violation_type, "blocked_import")

    def test_allowed_sample_passes(self) -> None:
        profile = self._create_profile_api()

        tested = self.client.post(
            f"/api/v1/runtime/sandbox-profiles/{profile['id']}/test",
            headers=self._headers(),
            json={"code": "import json\npayload = json.dumps({'ok': True})"},
        )

        self.assertEqual(tested.status_code, 200, tested.text)
        self.assertEqual(tested.json()["decision"], "allowed")
        self.assertEqual(tested.json()["violations"], [])
        self.assertIsNone(tested.json()["id"])

    def test_dangerous_sample_denied_and_persisted_for_agent_action(self) -> None:
        profile = self._create_profile_api()

        tested = self.client.post(
            f"/api/v1/runtime/sandbox-profiles/{profile['id']}/test",
            headers=self._headers(),
            json={
                "code": "import subprocess\nsubprocess.run(['echo', 'unsafe'])",
                "agent_id": "agent_sandbox",
                "action_name": "demo.unsafe_shell",
            },
        )

        self.assertEqual(tested.status_code, 200, tested.text)
        payload = tested.json()
        self.assertEqual(payload["decision"], "denied")
        self.assertIsNotNone(payload["id"])
        self.assertIn("subprocess", payload["reason"])
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM sandbox_decisions").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["agent_id"], "agent_sandbox")
        self.assertEqual(rows[0]["action_name"], "demo.unsafe_shell")
        self.assertEqual(rows[0]["decision"], "denied")


if __name__ == "__main__":
    unittest.main()
