from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class AgentIdentityRegistrationRemediationPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_active_agent_with_identity(connection, "agent_identity_runtime", "revoked")
            self._insert_active_agent_with_identity(connection, "agent_identity_rotate", "active")
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
            "X-Correlation-ID": "corr-air-phase3",
        }

    def _insert_active_agent_with_identity(
        self,
        connection,
        agent_id: str,
        identity_status: str,
    ) -> None:
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
                "F-AIR-004 remediation test agent.",
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
                identity_status,
                None,
                now,
                now,
            ),
        )

    def _create_draft(self, name: str) -> dict:
        response = self.client.post(
            "/api/v1/agents/registration-drafts",
            headers=self._headers(),
            json={
                "name": name,
                "description": "Phase 3 remediation draft",
                "framework": "langgraph",
                "runtime_type": "service",
                "owner_user_id": "user_admin",
                "sponsor_user_id": "user_admin",
                "capabilities": [{"capability_name": "claims:read", "resource_type": "claim"}],
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_identity_proof_is_verified_against_trusted_root(self) -> None:
        draft = self._create_draft("Trusted Identity")

        created = self.client.post(
            f"/api/v1/agents/registration-drafts/{draft['id']}/identity",
            headers=self._headers(),
            json={
                "proof_type": "agentmesh-local",
                "issuer": "local-agentmesh",
                "audience": "env_default",
                "subject": "spiffe://ophanix/env_default/trusted-identity",
                "trusted_root_id": "local-agentmesh",
                "trusted_root_version": "2026.05",
                "key_reference": "kms://ophanix/env_default/agents/trusted-identity",
                "proof_metadata": {"attestation": "unit-test"},
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        identity = created.json()["identity"]
        self.assertEqual(identity["issuer"], "local-agentmesh")
        self.assertEqual(identity["audience"], "env_default")
        self.assertEqual(identity["trusted_root_id"], "local-agentmesh")
        self.assertEqual(identity["trusted_root_version"], "2026.05")
        self.assertEqual(identity["proof_metadata"]["attestation"], "unit-test")
        self.assertIsNotNone(identity["verified_at"])

        rejected_draft = self._create_draft("Rejected Identity")
        rejected = self.client.post(
            f"/api/v1/agents/registration-drafts/{rejected_draft['id']}/identity",
            headers=self._headers(),
            json={
                "proof_type": "agentmesh-local",
                "issuer": "untrusted-idp",
                "audience": "env_default",
                "trusted_root_id": "local-agentmesh",
            },
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("issuer", rejected.json()["message"].lower())

    def test_api_registration_can_complete_from_draft_to_active(self) -> None:
        draft = self._create_draft("Complete Registration")
        self.assertEqual(draft["capabilities"][0]["capability_name"], "claims:read")

        identity = self.client.post(
            f"/api/v1/agents/registration-drafts/{draft['id']}/identity",
            headers=self._headers(),
            json={
                "proof_type": "agentmesh-local",
                "issuer": "local-agentmesh",
                "audience": "env_default",
                "trusted_root_id": "local-agentmesh",
            },
        )
        self.assertEqual(identity.status_code, 200, identity.text)

        submitted = self.client.post(
            f"/api/v1/agents/registration-drafts/{draft['id']}/submit",
            headers=self._headers(),
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertEqual(submitted.json()["status"], "pending_approval")

        approved = self.client.post(
            f"/api/v1/agents/{draft['id']}/approve",
            headers=self._headers(),
            json={"reason": "phase3 approval"},
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["status"], "provisioned")

        activated = self.client.post(
            f"/api/v1/agents/{draft['id']}/activate",
            headers=self._headers(),
            json={"reason": "phase3 activation"},
        )
        self.assertEqual(activated.status_code, 200, activated.text)
        self.assertEqual(activated.json()["status"], "active")

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                agent_id=draft["id"],
                limit=20,
            )
        )
        event_types = {event.event_type for event in events}
        self.assertIn("agent.registration_submitted", event_types)
        self.assertTrue(any(event.payload_json.get("lifecycle_state") == "active" for event in events))

    def test_identity_rotation_records_historical_evidence(self) -> None:
        rotated = self.client.post(
            "/api/v1/agents/agent_identity_rotate/identity/rotate",
            headers=self._headers(),
            json={
                "reason": "scheduled identity rotation",
                "proof": {
                    "proof_type": "agentmesh-local",
                    "issuer": "local-agentmesh",
                    "audience": "env_default",
                    "trusted_root_id": "local-agentmesh",
                    "trusted_root_version": "2026.06",
                },
            },
        )
        self.assertEqual(rotated.status_code, 200, rotated.text)
        identity = rotated.json()["identity"]
        self.assertEqual(identity["trusted_root_version"], "2026.06")
        self.assertEqual(identity["rotation_count"], 1)

        lifecycle = self.database.connect().execute(
            """
            SELECT metadata_json
            FROM agent_lifecycle_events
            WHERE agent_id = ? AND reason = ?
            """,
            ("agent_identity_rotate", "identity rotated"),
        ).fetchone()
        self.assertIsNotNone(lifecycle)
        self.assertIn("previous_did", lifecycle["metadata_json"])

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                event_type="agent.identity.rotated",
                agent_id="agent_identity_rotate",
            )
        )
        self.assertEqual(len(events), 1)

    def test_runtime_session_rejects_non_active_identity(self) -> None:
        response = self.client.post(
            "/api/v1/runtime/sessions",
            headers=self._headers(),
            json={
                "agent_id": "agent_identity_runtime",
                "ring": 2,
                "metadata": {"purpose": "identity-status"},
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("identity", response.json()["message"].lower())


if __name__ == "__main__":
    unittest.main()
