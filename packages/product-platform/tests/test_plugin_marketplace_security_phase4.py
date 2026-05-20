from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.models import CredentialScopeRequest
from product_platform.api.settings import Settings
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.marketplace.samples import sample_plugin_manifests
from product_platform.tool_gateway.auth import GatewayTokenVerifier
from product_platform.tool_gateway.decision import ToolPolicyDecisionService
from product_platform.tool_gateway.models import ToolDefinitionCreateRequest
from product_platform.tool_gateway.repository import ToolRegistryRepository
from marketplace_security_helpers import ed25519_key_pair, signed_manifest


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
}


class PluginMarketplaceSecurityPhase4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
            registry = ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            self.lookup_tool_id = self._create_active_tool(registry, name="claims.lookup")
            self.refund_tool_id = self._create_active_tool(registry, name="claims.issue_refund")
            AgentCredentialRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_metadata(
                agent_id="agent_marketplace_runtime",
                credential_type="bearer",
                raw_token="marketplace-runtime-token",
                issuer="marketplace-runtime-test",
                expires_at="2030-01-01T00:00:00+00:00",
                scopes=[
                    CredentialScopeRequest(
                        scope="claims.lookup:read",
                        resource_type="tool",
                        resource_id="claims.lookup",
                    ),
                    CredentialScopeRequest(
                        scope="claims.issue_refund:read",
                        resource_type="tool",
                        resource_id="claims.issue_refund",
                    ),
                ],
                status="active",
            )
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-20T00:00:00Z",
                dev_login_allowed_emails=["plugin-runtime@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "plugin-runtime@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]
        self.private_key, self.public_key = ed25519_key_pair()
        signing_key = self.client.post(
            "/api/v1/marketplace/signing-keys",
            headers=self._headers(),
            json={"name": "Runtime Grant Root", "public_key": self.public_key},
        )
        self.assertEqual(signing_key.status_code, 201, signing_key.text)

    def _headers(self, correlation_id: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": DEMO_ENV_ID,
        }
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        return headers

    def _insert_agent(self, connection) -> None:
        now = "2026-05-20T00:00:00+00:00"
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
                "agent_marketplace_runtime",
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                "agent_marketplace_runtime",
                "Marketplace runtime grant fixture.",
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

    def _create_active_tool(self, registry: ToolRegistryRepository, *, name: str) -> str:
        tool = registry.create_tool(
            ToolDefinitionCreateRequest(
                name=name,
                display_name=name.replace(".", " ").title(),
                owner_team="claims-platform",
                required_scope=f"{name}:read",
                input_schema_json=VALID_INPUT_SCHEMA,
            ),
            created_by=DEMO_ADMIN_USER_ID,
        )
        registry.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
        return tool["id"]

    def _runtime_decision(self, tool_name: str) -> str:
        with self.database.transaction() as connection:
            principal = GatewayTokenVerifier(connection).verify_token(
                "marketplace-runtime-token",
                request_id=f"req-{tool_name}",
            )
            decision = ToolPolicyDecisionService(
                connection,
                DEMO_ORG_ID,
                DEMO_ENV_ID,
            ).evaluate_tool_call(
                principal,
                tool_name,
                {"claim_id": "claim_123"},
                request_id=f"req-{tool_name}",
                correlation_id=f"corr-{tool_name}",
            )
        return decision.decision

    def _import_and_install_runtime_plugin(self, *, name: str) -> tuple[dict, str]:
        manifest = signed_manifest(
            sample_plugin_manifests()[0],
            self.private_key,
            name=name,
            capabilities=["claims.lookup"],
            permissions=["claims.lookup:read"],
            tools=[
                {
                    "name": "claims.lookup",
                    "scope": "claims.lookup:read",
                    "permission": "claims.lookup:read",
                    "capability": "claims.lookup",
                    "risk_class": "low",
                }
            ],
        )
        imported = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(imported.status_code, 201, imported.text)
        version_id = imported.json()["versions"][0]["id"]
        policy = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={
                "require_signature": True,
                "require_artifact_evidence": True,
                "allowed_plugin_types": ["agent"],
                "allowed_capabilities": ["claims.lookup"],
            },
        )
        self.assertEqual(policy.status_code, 201, policy.text)
        self.assertEqual(policy.json()["result"], "allow")
        installed = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers("corr-runtime-grant-install"),
            json={
                "plugin_version_id": version_id,
                "environment_id": DEMO_ENV_ID,
                "target_agent_id": "agent_marketplace_runtime",
            },
        )
        self.assertEqual(installed.status_code, 201, installed.text)
        return manifest, installed.json()["id"]

    def test_plugin_install_generates_runtime_tool_policy_and_uninstall_revokes_it(self) -> None:
        _manifest, installation_id = self._import_and_install_runtime_plugin(name="runtime-grant-plugin")
        with self.database.transaction() as connection:
            grants = connection.execute(
                """
                SELECT *
                FROM plugin_runtime_tool_grants
                WHERE installation_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (installation_id,),
            ).fetchall()
            permission = connection.execute(
                "SELECT * FROM agent_tool_permissions WHERE id = ?",
                (grants[0]["agent_tool_permission_id"],),
            ).fetchone()
            created_audit = connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE event_type = ?
                  AND resource_id = ?
                  AND correlation_id = ?
                """,
                (
                    "marketplace.plugin.runtime_grants.created",
                    installation_id,
                    "corr-runtime-grant-install",
                ),
            ).fetchone()
        self.assertEqual(len(grants), 1)
        self.assertEqual(grants[0]["tool_name"], "claims.lookup")
        self.assertEqual(grants[0]["agent_id"], "agent_marketplace_runtime")
        self.assertEqual(grants[0]["status"], "active")
        self.assertEqual(permission["status"], "active")
        self.assertIsNotNone(created_audit)

        self.assertEqual(self._runtime_decision("claims.lookup"), "allow")
        self.assertEqual(self._runtime_decision("claims.issue_refund"), "deny")

        uninstalled = self.client.post(
            f"/api/v1/marketplace/installations/{installation_id}/uninstall",
            headers=self._headers("corr-runtime-grant-uninstall"),
        )

        self.assertEqual(uninstalled.status_code, 200, uninstalled.text)
        with self.database.transaction() as connection:
            revoked_grant = connection.execute(
                "SELECT * FROM plugin_runtime_tool_grants WHERE installation_id = ?",
                (installation_id,),
            ).fetchone()
            revoked_permission = connection.execute(
                "SELECT * FROM agent_tool_permissions WHERE id = ?",
                (revoked_grant["agent_tool_permission_id"],),
            ).fetchone()
            revoked_audit = connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE event_type = ?
                  AND resource_id = ?
                  AND correlation_id = ?
                """,
                (
                    "marketplace.plugin.runtime_grants.revoked",
                    installation_id,
                    "corr-runtime-grant-uninstall",
                ),
            ).fetchone()
        self.assertEqual(revoked_grant["status"], "revoked")
        self.assertEqual(revoked_permission["status"], "revoked")
        self.assertIsNotNone(revoked_audit)
        self.assertEqual(self._runtime_decision("claims.lookup"), "deny")

    def test_plugin_disable_revokes_runtime_tool_policy(self) -> None:
        manifest, installation_id = self._import_and_install_runtime_plugin(name="runtime-disable-plugin")
        self.assertEqual(self._runtime_decision("claims.lookup"), "allow")

        disabled = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers("corr-runtime-grant-disable"),
            json={"manifest": manifest, "status": "disabled"},
        )

        self.assertEqual(disabled.status_code, 201, disabled.text)
        with self.database.transaction() as connection:
            installation = connection.execute(
                "SELECT * FROM plugin_installations WHERE id = ?",
                (installation_id,),
            ).fetchone()
            grant = connection.execute(
                "SELECT * FROM plugin_runtime_tool_grants WHERE installation_id = ?",
                (installation_id,),
            ).fetchone()
            permission = connection.execute(
                "SELECT * FROM agent_tool_permissions WHERE id = ?",
                (grant["agent_tool_permission_id"],),
            ).fetchone()
            disabled_audit = connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE event_type = ?
                  AND correlation_id = ?
                  AND resource_id = ?
                """,
                (
                    "marketplace.plugin.runtime_grants.revoked",
                    "corr-runtime-grant-disable",
                    disabled.json()["id"],
                ),
            ).fetchone()
        self.assertEqual(installation["status"], "disabled")
        self.assertEqual(grant["status"], "revoked")
        self.assertEqual(permission["status"], "revoked")
        self.assertIsNotNone(disabled_audit)
        self.assertEqual(self._runtime_decision("claims.lookup"), "deny")


if __name__ == "__main__":
    unittest.main()
