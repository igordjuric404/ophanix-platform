from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import AgentCredentialIssuer, hash_credential_token
from product_platform.agents.models import CredentialScopeRequest
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class CredentialPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent_with_identity(connection)
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

    def _insert_agent_with_identity(self, connection) -> None:
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
                "agent_issuer_demo",
                "org_default",
                "env_default",
                "Issuer Demo",
                "Agent used for credential issuance tests.",
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
        connection.execute(
            """
            INSERT INTO agent_identities (
                id, agent_id, did, public_key_fingerprint, key_type,
                identity_status, bootstrap_material_json, bootstrap_retrieved_at,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "ident_issuer_demo",
                "agent_issuer_demo",
                "did:agentmesh:test:issuer-demo",
                "fingerprint",
                "ed25519",
                "active",
                None,
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
                "cap_issuer_read",
                "agent_issuer_demo",
                "claims:read",
                "claim",
                "approved",
                "user_admin",
                "user_admin",
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

    def test_unit_issuance_adapter_returns_one_time_token_material(self) -> None:
        issued = AgentCredentialIssuer(default_ttl_seconds=600).issue(
            agent_did="did:agentmesh:test:issuer-demo",
            scopes=[
                CredentialScopeRequest(
                    scope="claims:read",
                    resource_type="claim",
                    resource_id="claim/*",
                )
            ],
            issued_for="phase2-unit-test",
        )

        self.assertTrue(issued.token)
        self.assertEqual(issued.token_hash, hash_credential_token(issued.token))
        self.assertEqual(issued.bearer_token, f"Bearer {issued.token}")
        self.assertEqual(issued.status, "active")
        self.assertIn("+00:00", issued.issued_at)
        self.assertIn("+00:00", issued.expires_at)

    def test_api_issue_credential_with_scopes_returns_token_once(self) -> None:
        response = self.client.post(
            "/api/v1/agents/agent_issuer_demo/credentials",
            headers=self._headers(),
            json={
                "credential_type": "bearer",
                "issuer": "local-agentmesh",
                "ttl_seconds": 600,
                "issued_for": "phase2-api-test",
                "scopes": [
                    {
                        "scope": "claims:read",
                        "resource_type": "claim",
                        "resource_id": "claim/*",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["token"])
        self.assertEqual(payload["bearer_token"], f"Bearer {payload['token']}")
        credential = payload["credential"]
        self.assertEqual(credential["status"], "active")
        self.assertEqual(credential["scopes"][0]["scope"], "claims:read")
        self.assertNotIn("token_hash", credential)

        listed = self.client.get(
            "/api/v1/agents/agent_issuer_demo/credentials",
            headers=self._headers(self.viewer_token),
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item["id"] for item in listed.json()], [credential["id"]])
        self.assertNotIn("token", listed.json()[0])
        self.assertNotIn("token_hash", listed.json()[0])

    def test_api_invalid_scope_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/agents/agent_issuer_demo/credentials",
            headers=self._headers(),
            json={
                "credential_type": "bearer",
                "issuer": "local-agentmesh",
                "ttl_seconds": 600,
                "scopes": [{"scope": "claims:write", "resource_type": "claim"}],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("not approved", response.json()["message"])

    def test_integration_issue_credential_emits_audit_event(self) -> None:
        response = self.client.post(
            "/api/v1/agents/agent_issuer_demo/credentials",
            headers=self._headers(),
            json={
                "credential_type": "bearer",
                "issuer": "local-agentmesh",
                "ttl_seconds": 600,
                "scopes": [{"scope": "claims:read", "resource_type": "claim"}],
            },
        )
        self.assertEqual(response.status_code, 201)
        credential_id = response.json()["credential"]["id"]

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                event_type="agent.credential.issued",
                agent_id="agent_issuer_demo",
            )
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].resource_type, "agent_credential")
        self.assertEqual(events[0].resource_id, credential_id)
        self.assertEqual(events[0].payload_json["scope_count"], 1)
        self.assertEqual(events[0].payload_json["issuer"], "local-agentmesh")


if __name__ == "__main__":
    unittest.main()
