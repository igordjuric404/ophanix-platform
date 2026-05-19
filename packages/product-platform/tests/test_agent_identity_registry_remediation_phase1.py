from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.lifecycle import AgentLifecycleAdapter, AgentLifecycleTransitionError
from product_platform.agents.models import CredentialScopeRequest
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.marketplace.samples import sample_plugin_manifests
from product_platform.tool_gateway.auth import GatewayAuthenticationError, GatewayTokenVerifier


class AgentLifecycleRemediationPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_active", "active")
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-19T00:00:00Z",
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
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": "corr-air-phase1",
        }

    def _insert_agent(self, connection, agent_id: str, status: str) -> None:
        now = "2026-05-19T00:00:00+00:00"
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
                "env_default",
                agent_id,
                "F-AIR-002 remediation test agent.",
                "langgraph",
                "service",
                "user_admin",
                "user_admin",
                status,
                now,
                now,
            ),
        )

    def test_lifecycle_state_machine_supports_quarantine_and_revocation(self) -> None:
        adapter = AgentLifecycleAdapter()

        adapter.validate_transition("active", "quarantined")
        adapter.validate_transition("quarantined", "revoked")
        adapter.validate_transition("revoked", "archived")
        with self.assertRaises(AgentLifecycleTransitionError):
            adapter.validate_transition("revoked", "active")

    def test_quarantine_and_revoke_routes_persist_lifecycle_and_audit_events(self) -> None:
        quarantined = self.client.post(
            "/api/v1/agents/agent_active/quarantine",
            headers=self._headers(),
            json={"reason": "suspected credential compromise"},
        )
        self.assertEqual(quarantined.status_code, 200, quarantined.text)
        self.assertEqual(quarantined.json()["status"], "quarantined")

        revoked = self.client.post(
            "/api/v1/agents/agent_active/revoke",
            headers=self._headers(),
            json={"reason": "confirmed compromise"},
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertEqual(revoked.json()["status"], "revoked")

        lifecycle_states = [
            row["next_state"]
            for row in self.database.connect()
            .execute(
                """
                SELECT next_state
                FROM agent_lifecycle_events
                WHERE agent_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                ("agent_active",),
            )
            .fetchall()
        ]
        self.assertIn("quarantined", lifecycle_states)
        self.assertIn("revoked", lifecycle_states)

        audit_events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                event_type="agent.lifecycle",
                agent_id="agent_active",
            )
        )
        audit_states = {event.payload_json["lifecycle_state"] for event in audit_events}
        self.assertIn("quarantined", audit_states)
        self.assertIn("revoked", audit_states)


class AgentRuntimeBoundaryRemediationPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "gateway_quarantined", "quarantined")
            self._insert_agent(connection, "gateway_revoked", "revoked")
            repository = AgentCredentialRepository(connection, "org_default", "env_default")
            self.quarantined_token = "gateway-quarantined-token"
            self.revoked_token = "gateway-revoked-token"
            repository.create_metadata(
                agent_id="gateway_quarantined",
                credential_type="bearer",
                raw_token=self.quarantined_token,
                issuer="test",
                expires_at="2026-05-20T00:00:00+00:00",
                scopes=[
                    CredentialScopeRequest(
                        scope="claims:read",
                        resource_type="claim",
                    )
                ],
            )
            repository.create_metadata(
                agent_id="gateway_revoked",
                credential_type="bearer",
                raw_token=self.revoked_token,
                issuer="test",
                expires_at="2026-05-20T00:00:00+00:00",
                scopes=[
                    CredentialScopeRequest(
                        scope="claims:read",
                        resource_type="claim",
                    )
                ],
            )

    def _insert_agent(self, connection, agent_id: str, status: str) -> None:
        now = "2026-05-19T00:00:00+00:00"
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
                "env_default",
                agent_id,
                "Gateway remediation test agent.",
                "langgraph",
                "service",
                "user_admin",
                "user_admin",
                status,
                now,
                now,
            ),
        )

    def test_gateway_rejects_quarantined_and_revoked_agents_with_specific_reason(self) -> None:
        verifier = GatewayTokenVerifier(self.database.connect())

        with self.assertRaises(GatewayAuthenticationError) as quarantined:
            verifier.verify_token(self.quarantined_token, request_id="req_quarantine")
        self.assertEqual(quarantined.exception.reason_code, "agent_quarantined")

        with self.assertRaises(GatewayAuthenticationError) as revoked:
            verifier.verify_token(self.revoked_token, request_id="req_revoked")
        self.assertEqual(revoked.exception.reason_code, "agent_revoked")


class AgentMeshAndMarketplaceRemediationPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "mesh_source", "active")
            self._insert_agent(connection, "mesh_target_quarantined", "quarantined")
            self._insert_agent(connection, "plugin_target_revoked", "revoked")
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-19T00:00:00Z",
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
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _insert_agent(self, connection, agent_id: str, status: str) -> None:
        now = "2026-05-19T00:00:00+00:00"
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
                "env_default",
                agent_id,
                "Mesh and marketplace remediation test agent.",
                "langgraph",
                "service",
                "user_admin",
                "user_admin",
                status,
                now,
                now,
            ),
        )

    def _import_signed_plugin_version(self) -> str:
        manifest = next(
            item
            for item in sample_plugin_manifests()
            if item["name"] == "support-triage-assistant"
        )
        imported = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(imported.status_code, 201, imported.text)
        return imported.json()["versions"][0]["id"]

    def test_mesh_handoff_rejects_quarantined_target_agent(self) -> None:
        response = self.client.post(
            "/api/v1/mesh/handoffs",
            headers=self._headers(),
            json={
                "source_agent_id": "mesh_source",
                "target_agent_id": "mesh_target_quarantined",
                "task_type": "claim_review",
                "required_capabilities": ["claims:read"],
                "trust_result": "allowed",
                "policy_result": "allow",
                "status": "accepted",
                "reason": "should not reach quarantined target",
            },
        )

        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("quarantined", response.json()["message"])

    def test_runtime_session_rejects_quarantined_and_revoked_agents(self) -> None:
        for agent_id, expected_status in [
            ("mesh_target_quarantined", "quarantined"),
            ("plugin_target_revoked", "revoked"),
        ]:
            response = self.client.post(
                "/api/v1/runtime/sessions",
                headers=self._headers(),
                json={"agent_id": agent_id, "ring": 2},
            )

            self.assertEqual(response.status_code, 400, response.text)
            self.assertIn(expected_status, response.json()["message"])

    def test_marketplace_installation_rejects_revoked_target_agent(self) -> None:
        version_id = self._import_signed_plugin_version()

        installed = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers(),
            json={
                "plugin_version_id": version_id,
                "environment_id": "env_default",
                "target_agent_id": "plugin_target_revoked",
            },
        )

        self.assertEqual(installed.status_code, 409, installed.text)
        self.assertIn("revoked", installed.json()["message"])


if __name__ == "__main__":
    unittest.main()
