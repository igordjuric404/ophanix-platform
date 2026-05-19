from __future__ import annotations

import json
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.models import CredentialScopeRequest
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.auth import GatewayAuthenticationError, GatewayTokenVerifier


class AgentCredentialCascadeRemediationPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            for agent_id in (
                "agent_suspend",
                "agent_quarantine",
                "agent_revoke",
                "agent_decommission",
                "agent_bypass",
            ):
                self._insert_agent_with_identity(connection, agent_id)
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
            "X-Correlation-ID": "corr-air-phase2",
        }

    def _insert_agent_with_identity(self, connection, agent_id: str) -> None:
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
                "F-AIR-003 remediation test agent.",
                "langgraph",
                "service",
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
                f"ident_{agent_id}",
                agent_id,
                f"did:agentmesh:test:{agent_id}",
                f"fingerprint-{agent_id}",
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
                f"cap_{agent_id}",
                agent_id,
                "claims:read",
                "claim",
                "approved",
                "user_admin",
                "user_admin",
                now,
            ),
        )

    def _issue_credential(self, agent_id: str) -> tuple[dict, str]:
        response = self.client.post(
            f"/api/v1/agents/{agent_id}/credentials",
            headers=self._headers(),
            json={
                "credential_type": "bearer",
                "issuer": "local-agentmesh",
                "ttl_seconds": 600,
                "issued_for": f"phase2-{agent_id}",
                "scopes": [{"scope": "claims:read", "resource_type": "claim"}],
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        return payload["credential"], payload["token"]

    def test_suspend_cascades_to_credentials_identity_and_audit(self) -> None:
        credential, token = self._issue_credential("agent_suspend")

        valid_before = self.client.post(
            f"/api/v1/credentials/{credential['id']}/verify",
            headers=self._headers(),
            json={"token": token},
        )
        self.assertEqual(valid_before.status_code, 200)
        self.assertTrue(valid_before.json()["valid"])

        suspended = self.client.post(
            "/api/v1/agents/agent_suspend/suspend",
            headers=self._headers(),
            json={"reason": "incident response"},
        )
        self.assertEqual(suspended.status_code, 200, suspended.text)
        self.assertEqual(suspended.json()["status"], "suspended")

        row = self.database.connect().execute(
            "SELECT status, revoked_at, metadata_json FROM agent_credentials WHERE id = ?",
            (credential["id"],),
        ).fetchone()
        self.assertEqual(row["status"], "revoked")
        self.assertIsNotNone(row["revoked_at"])
        metadata = json.loads(row["metadata_json"])
        self.assertEqual(metadata["revocation"]["trigger"], "agent_lifecycle")
        self.assertEqual(metadata["revocation"]["lifecycle_state"], "suspended")

        identity = self.database.connect().execute(
            "SELECT identity_status FROM agent_identities WHERE agent_id = ?",
            ("agent_suspend",),
        ).fetchone()
        self.assertEqual(identity["identity_status"], "suspended")

        rejected = self.client.post(
            f"/api/v1/credentials/{credential['id']}/verify",
            headers=self._headers(),
            json={"token": token},
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertFalse(rejected.json()["valid"])
        self.assertEqual(rejected.json()["status"], "revoked")

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                agent_id="agent_suspend",
                limit=20,
            )
        )
        event_types = {event.event_type for event in events}
        self.assertIn("agent.credential.revoked", event_types)
        self.assertIn("agent.credential.revocation_published", event_types)
        revoked_events = [event for event in events if event.event_type == "agent.credential.revoked"]
        self.assertTrue(
            any(event.payload_json.get("lifecycle_state") == "suspended" for event in revoked_events)
        )

    def test_quarantine_revoke_and_decommission_cascade_credentials_and_identity(self) -> None:
        cases = [
            ("agent_quarantine", "quarantine", "quarantined"),
            ("agent_revoke", "revoke", "revoked"),
            ("agent_decommission", "decommission", "decommissioned"),
        ]

        for agent_id, action, expected_identity_status in cases:
            with self.subTest(action=action):
                credential, _token = self._issue_credential(agent_id)
                response = self.client.post(
                    f"/api/v1/agents/{agent_id}/{action}",
                    headers=self._headers(),
                    json={"reason": f"{action} cascade"},
                )
                self.assertEqual(response.status_code, 200, response.text)

                row = self.database.connect().execute(
                    "SELECT status FROM agent_credentials WHERE id = ?",
                    (credential["id"],),
                ).fetchone()
                self.assertEqual(row["status"], "revoked")

                identity = self.database.connect().execute(
                    "SELECT identity_status FROM agent_identities WHERE agent_id = ?",
                    (agent_id,),
                ).fetchone()
                self.assertEqual(identity["identity_status"], expected_identity_status)

    def test_token_verification_rechecks_latest_agent_lifecycle(self) -> None:
        raw_token = "phase2-bypass-token"
        with self.database.transaction() as connection:
            credential = AgentCredentialRepository(
                connection,
                "org_default",
                "env_default",
            ).create_metadata(
                agent_id="agent_bypass",
                credential_type="bearer",
                raw_token=raw_token,
                issuer="local-agentmesh",
                expires_at="2026-05-20T00:00:00+00:00",
                scopes=[CredentialScopeRequest(scope="claims:read", resource_type="claim")],
            )
            connection.execute(
                "UPDATE agents SET status = ? WHERE id = ?",
                ("suspended", "agent_bypass"),
            )

        result = AgentCredentialRepository(
            self.database.connect(),
            "org_default",
            "env_default",
        ).verify_token(credential["id"], raw_token=raw_token, now="2026-05-19T01:00:00+00:00")
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "active")
        self.assertIn("suspended", result["reason"])

        with self.assertRaises(GatewayAuthenticationError) as gateway_error:
            GatewayTokenVerifier(self.database.connect()).verify_token(
                raw_token,
                request_id="req_phase2_lifecycle_recheck",
                now="2026-05-19T01:00:00+00:00",
            )
        self.assertEqual(gateway_error.exception.reason_code, "agent_inactive")


if __name__ == "__main__":
    unittest.main()
