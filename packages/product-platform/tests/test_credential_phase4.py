from __future__ import annotations

from datetime import datetime, timezone
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import (
    AgentCredentialRepository,
    CredentialExpiryMonitor,
    credential_expires_within_threshold,
)
from product_platform.agents.models import CredentialScopeRequest
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class CredentialPhase4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com", "viewer@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.admin_token, self.admin_user = self._login("admin@example.com", ["Platform Admin"])
        self.viewer_token, self.viewer_user = self._login("viewer@example.com", ["Viewer"])

    def _insert_agent(self, connection) -> None:
        now = "2026-04-30T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, endpoint_url, owner_user_id, sponsor_user_id, status,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "agent_expiry_demo",
                "org_default",
                "env_default",
                "Expiry Demo",
                "Agent used for credential expiry tests.",
                "langgraph",
                "service",
                None,
                "user_admin",
                "user_admin",
                "active",
                now,
                now,
            ),
        )

    def _login(self, email: str, roles: list[str]) -> tuple[str, dict]:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        return payload["access_token"], payload["user"]

    def _headers(self, token: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token or self.admin_token}",
            "X-Environment-ID": "env_default",
        }

    def _repository(self, connection=None) -> AgentCredentialRepository:
        return AgentCredentialRepository(
            connection or self.database.connect(),
            organization_id="org_default",
            environment_id="env_default",
        )

    def _create_credential(
        self,
        *,
        expires_at: str,
        raw_token: str,
    ) -> str:
        with self.database.transaction() as connection:
            row = self._repository(connection).create_metadata(
                agent_id="agent_expiry_demo",
                credential_type="bearer",
                raw_token=raw_token,
                issuer="local-agentmesh",
                expires_at=expires_at,
                scopes=[CredentialScopeRequest(scope="claims:read", resource_type="claim")],
                metadata_json={"ttl_seconds": 600},
                issued_at="2026-04-30T00:00:00+00:00",
            )
        return row["id"]

    def test_unit_expiry_threshold_calculation(self) -> None:
        now = datetime(2026, 4, 30, 0, 0, tzinfo=timezone.utc)

        self.assertTrue(
            credential_expires_within_threshold(
                "2026-04-30T12:00:00+00:00",
                now=now,
                threshold_hours=24,
            )
        )
        self.assertFalse(
            credential_expires_within_threshold(
                "2026-05-02T00:00:00+00:00",
                now=now,
                threshold_hours=24,
            )
        )
        self.assertFalse(
            credential_expires_within_threshold(
                "2026-04-29T23:00:00+00:00",
                now=now,
                threshold_hours=24,
            )
        )

    def test_integration_expiry_job_marks_credential_expiring_soon(self) -> None:
        soon_id = self._create_credential(
            expires_at="2026-04-30T12:00:00+00:00",
            raw_token="soon-token",
        )
        self._create_credential(
            expires_at="2026-05-05T00:00:00+00:00",
            raw_token="far-token",
        )

        with self.database.transaction() as connection:
            repository = self._repository(connection)
            result = CredentialExpiryMonitor(
                repository,
                AuditEventRepository(connection),
            ).run(
                threshold_hours=24,
                actor_id=self.admin_user["id"],
                now=datetime(2026, 4, 30, 0, 0, tzinfo=timezone.utc),
            )

        self.assertEqual(result.processed_count, 1)
        self.assertEqual(result.credential_ids, [soon_id])
        row = self._repository().get(soon_id)
        self.assertEqual(row["status"], "expiring_soon")
        self.assertIn("auto_rotation_policy", row["metadata_json"])
        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                event_type="agent.credential.expiring_soon",
                agent_id="agent_expiry_demo",
            )
        )
        self.assertEqual(len(events), 1)

    def test_api_expiring_endpoint_returns_correct_credentials(self) -> None:
        soon_id = self._create_credential(
            expires_at="2026-04-30T12:00:00+00:00",
            raw_token="soon-api-token",
        )
        self._create_credential(
            expires_at="2026-05-05T00:00:00+00:00",
            raw_token="far-api-token",
        )

        response = self.client.get(
            "/api/v1/credentials/expiring?threshold_hours=24&now=2026-04-30T00:00:00+00:00",
            headers=self._headers(self.viewer_token),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([credential["id"] for credential in response.json()], [soon_id])
        self.assertNotIn("token_hash", response.json()[0])


if __name__ == "__main__":
    unittest.main()
