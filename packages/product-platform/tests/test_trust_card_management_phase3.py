from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.trust.cards import TrustCardRepository


class TrustCardManagementPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_current", "Current Agent")
            self._insert_agent(connection, "agent_empty", "Empty Agent")
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

    def _insert_agent(self, connection, agent_id: str, name: str) -> None:
        now = "2026-05-01T00:00:00+00:00"
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
                "org_default",
                "env_default",
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

    def test_latest_valid_card_selected(self) -> None:
        with self.database.transaction() as connection:
            repository = TrustCardRepository(connection, "org_default", "env_default")
            older = repository.create_card(
                agent_id="agent_current",
                issuer="demo",
                card={"agent_did": "did:mesh:current", "version": "older"},
                signature="sig_older",
                valid_from="2026-04-01T00:00:00+00:00",
                valid_until="2026-06-01T00:00:00+00:00",
            )
            newer = repository.create_card(
                agent_id="agent_current",
                issuer="demo",
                card={"agent_did": "did:mesh:current", "version": "newer"},
                signature="sig_newer",
                valid_from="2026-04-01T00:00:00+00:00",
                valid_until="2026-06-01T00:00:00+00:00",
            )
            connection.execute(
                "UPDATE trust_cards SET issued_at = ? WHERE id = ?",
                ("2026-04-01T00:00:00+00:00", older["id"]),
            )
            connection.execute(
                "UPDATE trust_cards SET issued_at = ? WHERE id = ?",
                ("2026-05-01T00:00:00+00:00", newer["id"]),
            )

            current = repository.current_card(
                "agent_current",
                now="2026-05-02T00:00:00+00:00",
            )

            self.assertEqual(current["id"], newer["id"])

    def test_expired_card_not_selected(self) -> None:
        with self.database.transaction() as connection:
            repository = TrustCardRepository(connection, "org_default", "env_default")
            repository.create_card(
                agent_id="agent_current",
                issuer="demo",
                card={"agent_did": "did:mesh:current"},
                signature="sig_expired",
                valid_from="2026-04-01T00:00:00+00:00",
                valid_until="2026-04-15T00:00:00+00:00",
            )

            current = repository.current_card(
                "agent_current",
                now="2026-05-02T00:00:00+00:00",
            )

            self.assertIsNone(current)

    def test_api_agent_without_card_returns_clear_empty_state(self) -> None:
        response = self.client.get(
            "/api/v1/agents/agent_empty/trust-card",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["card"])
        self.assertIn("No valid trust card", response.json()["warning"])


if __name__ == "__main__":
    unittest.main()
