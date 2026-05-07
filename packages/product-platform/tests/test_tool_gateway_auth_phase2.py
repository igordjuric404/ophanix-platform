from __future__ import annotations

import unittest

from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.models import CredentialScopeRequest
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.auth import GatewayAuthenticationError, GatewayTokenVerifier


class ToolGatewayAuthPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, agent_id="agent_gateway_active", status="active")
            self._insert_agent(connection, agent_id="agent_gateway_suspended", status="suspended")
        self.connection = self.database.connect()
        self.credentials = AgentCredentialRepository(self.connection, DEMO_ORG_ID, DEMO_ENV_ID)
        self.verifier = GatewayTokenVerifier(self.connection)

    def _insert_agent(self, connection, *, agent_id: str, status: str) -> None:
        now = "2026-05-01T00:00:00+00:00"
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
                agent_id,
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                agent_id,
                "Gateway auth test agent.",
                "langgraph",
                "service",
                None,
                DEMO_ADMIN_USER_ID,
                DEMO_ADMIN_USER_ID,
                status,
                now,
                now,
            ),
        )

    def _credential(
        self,
        *,
        raw_token: str,
        agent_id: str = "agent_gateway_active",
        status: str = "active",
        expires_at: str = "2030-01-01T00:00:00+00:00",
    ) -> str:
        row = self.credentials.create_metadata(
            agent_id=agent_id,
            credential_type="bearer",
            raw_token=raw_token,
            issuer="gateway-test",
            expires_at=expires_at,
            scopes=[
                CredentialScopeRequest(
                    scope="claims.lookup:read",
                    resource_type="tool",
                    resource_id="claims.lookup",
                )
            ],
            status=status,
        )
        return row["id"]

    def test_unit_active_credential_verifies(self) -> None:
        with self.database.transaction():
            credential_id = self._credential(raw_token="active-token")
            principal = self.verifier.verify_token(
                "active-token",
                request_id="req-active",
                now="2026-05-01T00:00:00+00:00",
            )

        self.assertEqual(principal.organization_id, DEMO_ORG_ID)
        self.assertEqual(principal.environment_id, DEMO_ENV_ID)
        self.assertEqual(principal.agent_id, "agent_gateway_active")
        self.assertEqual(principal.credential_id, credential_id)
        self.assertEqual(principal.scopes, ["claims.lookup:read"])
        self.assertEqual(principal.request_id, "req-active")

    def test_unit_expired_credential_is_rejected(self) -> None:
        with self.database.transaction():
            credential_id = self._credential(
                raw_token="expired-token",
                expires_at="2020-01-01T00:00:00+00:00",
            )
            with self.assertRaises(GatewayAuthenticationError) as context:
                self.verifier.verify_token(
                    "expired-token",
                    request_id="req-expired",
                    now="2026-05-01T00:00:00+00:00",
                )

        self.assertEqual(context.exception.reason_code, "credential_expired")
        row = self.connection.execute(
            "SELECT status FROM agent_credentials WHERE id = ?",
            (credential_id,),
        ).fetchone()
        self.assertEqual(row["status"], "expired")

    def test_unit_revoked_credential_is_rejected(self) -> None:
        with self.database.transaction():
            self._credential(raw_token="revoked-token", status="revoked")
            with self.assertRaises(GatewayAuthenticationError) as context:
                self.verifier.verify_token(
                    "revoked-token",
                    request_id="req-revoked",
                    now="2026-05-01T00:00:00+00:00",
                )

        self.assertEqual(context.exception.reason_code, "credential_inactive")

    def test_unit_credential_for_suspended_agent_is_rejected(self) -> None:
        with self.database.transaction():
            self._credential(
                raw_token="suspended-token",
                agent_id="agent_gateway_suspended",
            )
            with self.assertRaises(GatewayAuthenticationError) as context:
                self.verifier.verify_token(
                    "suspended-token",
                    request_id="req-suspended",
                    now="2026-05-01T00:00:00+00:00",
                )

        self.assertEqual(context.exception.reason_code, "agent_inactive")
        self.assertEqual(context.exception.agent_id, "agent_gateway_suspended")

    def test_integration_successful_verification_updates_last_used_at(self) -> None:
        with self.database.transaction():
            credential_id = self._credential(raw_token="last-used-token")
            before = self.connection.execute(
                "SELECT last_used_at FROM agent_credentials WHERE id = ?",
                (credential_id,),
            ).fetchone()["last_used_at"]
            principal = self.verifier.verify_token(
                "last-used-token",
                request_id="req-last-used",
                now="2026-05-01T00:00:00+00:00",
            )
            after = self.connection.execute(
                "SELECT last_used_at FROM agent_credentials WHERE id = ?",
                (credential_id,),
            ).fetchone()["last_used_at"]

        self.assertIsNone(before)
        self.assertIsNotNone(after)
        self.assertEqual(principal.credential_id, credential_id)


if __name__ == "__main__":
    unittest.main()
