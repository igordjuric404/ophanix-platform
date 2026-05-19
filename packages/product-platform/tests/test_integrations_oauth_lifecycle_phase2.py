from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.models import CredentialScopeRequest
from product_platform.api.settings import Settings
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.delegation import ToolDelegationRequirementCreate, ToolDelegationRepository
from product_platform.tool_gateway.invocation import ToolExecutionResult
from product_platform.tool_gateway.models import AgentToolPermissionGrantRequest, ToolDefinitionCreateRequest
from product_platform.tool_gateway.repository import ToolRegistryRepository


class CapturingExecutor:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, *, tool, payload, decision, principal):
        self.calls += 1
        return ToolExecutionResult(
            status="succeeded",
            body={"claim_status": "open"},
            upstream_status_code=200,
            latency_ms=5.0,
        )


class IntegrationsOAuthLifecyclePhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
            credential = AgentCredentialRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_metadata(
                agent_id="agent_oauth_lifecycle",
                credential_type="bearer",
                raw_token="oauth-lifecycle-token",
                issuer="oauth-lifecycle-test",
                expires_at="2030-01-01T00:00:00+00:00",
                scopes=[
                    CredentialScopeRequest(
                        scope="claims.lookup:read",
                        resource_type="tool",
                        resource_id="claims.oauth",
                    )
                ],
                status="active",
            )
            self.credential_id = credential["id"]
            registry = ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            tool = registry.create_tool(
                ToolDefinitionCreateRequest(
                    name="claims.oauth",
                    display_name="Claims OAuth",
                    owner_team="claims-platform",
                    required_scope="claims.lookup:read",
                    input_schema_json={
                        "type": "object",
                        "properties": {"claim_id": {"type": "string"}},
                        "required": ["claim_id"],
                    },
                ),
                created_by=DEMO_ADMIN_USER_ID,
            )
            self.tool_id = tool["id"]
            registry.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
            registry.grant_agent_tool_permission(
                "agent_oauth_lifecycle",
                AgentToolPermissionGrantRequest(
                    tool_id=self.tool_id,
                    scope="claims.lookup:read",
                    granted_reason="oauth lifecycle fixture",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )
            ToolDelegationRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_requirement(
                ToolDelegationRequirementCreate(
                    tool_id=self.tool_id,
                    provider="claims-oauth",
                    required_scopes=["claims.read"],
                    approval_required=True,
                )
            )
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-19T00:00:00Z",
                dev_login_allowed_emails=["oauth-admin@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.executor = CapturingExecutor()
        self.app.state.tool_gateway_executor = self.executor
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "oauth-admin@example.com", "roles": ["Security Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.admin_token = login.json()["access_token"]

    def _insert_agent(self, connection) -> None:
        now = "2026-05-19T00:00:00+00:00"
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
                "agent_oauth_lifecycle",
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                "agent_oauth_lifecycle",
                "OAuth lifecycle fixture.",
                "langgraph",
                "service",
                None,
                DEMO_ADMIN_USER_ID,
                DEMO_ADMIN_USER_ID,
                "active",
                now,
                now,
            ),
        )

    def _admin_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.admin_token}", "X-Environment-ID": DEMO_ENV_ID}

    def _gateway_headers(self, *, delegated: bool = False) -> dict[str, str]:
        headers = {
            "Authorization": "Bearer oauth-lifecycle-token",
            "X-Request-ID": "req-oauth-lifecycle",
            "X-Correlation-ID": "corr-oauth-lifecycle",
        }
        if delegated:
            headers["X-Delegated-User-ID"] = "user_123"
            headers["X-Delegated-Provider-Account-ID"] = "acct_456"
        return headers

    def _create_oauth_app(self) -> str:
        response = self.client.post(
            "/api/v1/integrations/oauth/apps",
            headers=self._admin_headers(),
            json={
                "provider": "claims-oauth",
                "client_id": "claims-client",
                "authorization_url": "https://auth.example.com/oauth/authorize",
                "token_url": "https://auth.example.com/oauth/token",
                "redirect_url": "https://app.ophanix.local/oauth/callback",
                "scopes": ["claims.read"],
                "client_secret_ref": "vault:oauth/claims/client-secret",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertNotIn("vault:oauth/claims/client-secret", response.text)
        return response.json()["id"]

    def _start_session(self, oauth_app_id: str) -> dict:
        response = self.client.post(
            "/api/v1/integrations/oauth/authorization-sessions",
            headers=self._admin_headers(),
            json={
                "oauth_app_id": oauth_app_id,
                "agent_id": "agent_oauth_lifecycle",
                "credential_id": self.credential_id,
                "tool_id": self.tool_id,
                "provider": "claims-oauth",
                "required_scopes": ["claims.read"],
                "user_id": "user_123",
                "provider_account_id": "acct_456",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_oauth_authorization_start_complete_refresh_and_revoke_lifecycle(self) -> None:
        oauth_app_id = self._create_oauth_app()
        session = self._start_session(oauth_app_id)

        raw_token_response = self.client.post(
            f"/api/v1/integrations/oauth/authorization-sessions/{session['authorization_session_id']}/complete",
            headers=self._admin_headers(),
            json={
                "user_id": "user_123",
                "provider_account_id": "acct_456",
                "scopes": ["claims.read"],
                "access_token": "ya29.raw-token-must-not-be-accepted",
                "access_token_ref": "vault:oauth/claims/user_123/access",
                "expires_at": "2030-01-01T00:00:00+00:00",
            },
        )
        self.assertEqual(raw_token_response.status_code, 422)
        self.assertNotIn("ya29.raw-token", raw_token_response.text)

        completed = self.client.post(
            f"/api/v1/integrations/oauth/authorization-sessions/{session['authorization_session_id']}/complete",
            headers=self._admin_headers(),
            json={
                "user_id": "user_123",
                "provider_account_id": "acct_456",
                "scopes": ["claims.read"],
                "access_token_ref": "vault:oauth/claims/user_123/access",
                "refresh_token_ref": "vault:oauth/claims/user_123/refresh",
                "expires_at": "2030-01-01T00:00:00+00:00",
                "approval_state": "approved",
            },
        )
        self.assertEqual(completed.status_code, 201, completed.text)
        authorization = completed.json()
        self.assertEqual(authorization["status"], "active")
        self.assertEqual(authorization["user_id"], "user_123")
        self.assertEqual(authorization["provider_account_id"], "acct_456")
        self.assertNotIn("vault:oauth/claims/user_123", completed.text)

        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM tool_delegated_authorizations WHERE id = ?",
                (authorization["id"],),
            ).fetchone()
        self.assertEqual(row["access_token_ref"], "vault:oauth/claims/user_123/access")
        self.assertEqual(row["refresh_token_ref"], "vault:oauth/claims/user_123/refresh")

        refreshed = self.client.post(
            f"/api/v1/integrations/oauth/delegated-authorizations/{authorization['id']}/refresh",
            headers=self._admin_headers(),
            json={
                "access_token_ref": "vault:oauth/claims/user_123/access-v2",
                "expires_at": "2031-01-01T00:00:00+00:00",
            },
        )
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        self.assertEqual(refreshed.json()["expires_at"], "2031-01-01T00:00:00+00:00")
        self.assertNotIn("access-v2", refreshed.text)

        revoked = self.client.post(
            f"/api/v1/integrations/oauth/delegated-authorizations/{authorization['id']}/revoke",
            headers=self._admin_headers(),
            json={"reason": "user disconnected provider account"},
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertEqual(revoked.json()["status"], "revoked")

    def test_gateway_authorization_status_uses_gateway_token(self) -> None:
        session = self._start_session(self._create_oauth_app())

        response = self.client.get(
            f"/api/v1/gateway/authorizations/{session['authorization_session_id']}",
            headers=self._gateway_headers(),
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["authorization_session_id"], session["authorization_session_id"])
        self.assertEqual(response.json()["status"], "pending_authorization")

    def test_revoked_delegated_authorization_cannot_be_used_for_tool_calls(self) -> None:
        session = self._start_session(self._create_oauth_app())
        completed = self.client.post(
            f"/api/v1/integrations/oauth/authorization-sessions/{session['authorization_session_id']}/complete",
            headers=self._admin_headers(),
            json={
                "user_id": "user_123",
                "provider_account_id": "acct_456",
                "scopes": ["claims.read"],
                "access_token_ref": "vault:oauth/claims/user_123/access",
                "refresh_token_ref": "vault:oauth/claims/user_123/refresh",
                "expires_at": "2030-01-01T00:00:00+00:00",
                "approval_state": "approved",
            },
        )
        self.assertEqual(completed.status_code, 201, completed.text)
        revoked = self.client.post(
            f"/api/v1/integrations/oauth/delegated-authorizations/{completed.json()['id']}/revoke",
            headers=self._admin_headers(),
            json={"reason": "user disconnected provider account"},
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)

        response = self.client.post(
            "/api/v1/tools/claims.oauth/invoke",
            headers=self._gateway_headers(delegated=True),
            json={"payload": {"claim_id": "claim_123"}},
        )

        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(response.json()["reason_code"], "authorization_required")
        self.assertEqual(response.json()["error"]["authorization"]["provider"], "claims-oauth")
        self.assertEqual(self.executor.calls, 0)


if __name__ == "__main__":
    unittest.main()
