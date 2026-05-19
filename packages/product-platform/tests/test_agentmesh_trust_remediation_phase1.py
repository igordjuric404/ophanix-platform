from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.trust.repository import TrustRepository


MESH_POLICY_BODY = """version: "1.0"
name: mesh-governance-guard
rules:
  - name: deny_handoff_request
    condition:
      field: action
      operator: eq
      value: handoff.request
    action: deny
    message: Mesh handoff is blocked by policy.
defaults:
  action: allow
"""


class AgentMeshTrustRemediationPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            for agent_id, name, status, score in [
                ("mesh_source", "Mesh Source", "active", 840),
                ("mesh_target", "Mesh Target", "active", 830),
                ("trust_card_agent", "Trust Card Agent", "active", 735),
                ("handshake_source", "Handshake Source", "active", 820),
                ("handshake_quarantined", "Handshake Quarantined", "quarantined", 820),
            ]:
                self._insert_agent(connection, agent_id, name, status, score)
                self._insert_identity(connection, agent_id)
                self._insert_capability(connection, agent_id)
                TrustRepository(connection, "org_default", "env_default").upsert_score(
                    agent_id=agent_id,
                    score=score,
                    dimensions={"policy_compliance": {"score": score, "signal_count": 1}},
                )
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

    def _headers(self, *, correlation_id: str = "corr-amt-phase1") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": correlation_id,
        }

    def _insert_agent(self, connection, agent_id: str, name: str, status: str, score: int) -> None:
        now = "2026-05-19T00:00:00+00:00"
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
                "AgentMesh trust remediation test agent.",
                "langgraph",
                "service",
                "user_admin",
                "user_admin",
                status,
                score,
                "trusted",
                now,
                now,
            ),
        )

    def _insert_identity(self, connection, agent_id: str) -> None:
        now = "2026-05-19T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agent_identities (
                id, agent_id, did, public_key_fingerprint, key_type,
                identity_status, bootstrap_material_json, bootstrap_retrieved_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"ident_{agent_id}",
                agent_id,
                f"did:mesh:{agent_id.replace('_', '-')}",
                f"fingerprint-{agent_id}",
                "ed25519",
                "active" if agent_id != "handshake_quarantined" else "quarantined",
                None,
                now,
                now,
            ),
        )

    def _insert_capability(self, connection, agent_id: str) -> None:
        now = "2026-05-19T00:00:00+00:00"
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

    def _create_mesh_deny_policy(self) -> tuple[str, str]:
        policy = self.client.post(
            "/api/v1/policies",
            headers=self._headers(correlation_id="corr-mesh-policy-create"),
            json={"name": "Mesh Governance Guard", "scope": "environment", "status": "active"},
        )
        self.assertEqual(policy.status_code, 201, policy.text)
        version = self.client.post(
            f"/api/v1/policies/{policy.json()['id']}/versions",
            headers=self._headers(correlation_id="corr-mesh-policy-version"),
            json={
                "body_text": MESH_POLICY_BODY,
                "body_format": "yaml",
                "backend": "native",
                "status": "active",
            },
        )
        self.assertEqual(version.status_code, 201, version.text)
        binding = self.client.post(
            "/api/v1/policy-bindings",
            headers=self._headers(correlation_id="corr-mesh-policy-binding"),
            json={
                "policy_id": policy.json()["id"],
                "policy_version_id": version.json()["id"],
                "target_type": "environment",
                "target_id": "env_default",
                "mode": "enforce",
                "rollout_percentage": 100,
                "priority": 50,
            },
        )
        self.assertEqual(binding.status_code, 201, binding.text)
        return policy.json()["id"], version.json()["id"]

    def test_lifecycle_revocation_invalidates_trust_card_and_audits_revocation(self) -> None:
        issued = self.client.post(
            "/api/v1/trust/cards",
            headers=self._headers(correlation_id="corr-card-issue"),
            json={"agent_id": "trust_card_agent", "issuer": "ophanix-demo"},
        )
        self.assertEqual(issued.status_code, 201, issued.text)
        card_id = issued.json()["id"]

        revoked_agent = self.client.post(
            "/api/v1/agents/trust_card_agent/revoke",
            headers=self._headers(correlation_id="corr-agent-revoke"),
            json={"reason": "confirmed compromise"},
        )
        self.assertEqual(revoked_agent.status_code, 200, revoked_agent.text)

        card = self.client.get(
            f"/api/v1/trust/cards/{card_id}",
            headers=self._headers(correlation_id="corr-card-detail"),
        )
        self.assertEqual(card.status_code, 200, card.text)
        self.assertEqual(card.json()["status"], "revoked")
        self.assertEqual(card.json()["revocation_reason"], "confirmed compromise")

        verified = self.client.post(
            f"/api/v1/trust/cards/{card_id}/verify",
            headers=self._headers(correlation_id="corr-card-verify"),
        )
        self.assertEqual(verified.status_code, 200, verified.text)
        self.assertFalse(verified.json()["verified"])

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                event_type="trust.card.revoked",
                resource_id=card_id,
            )
        )
        self.assertTrue(events)
        self.assertEqual(events[0].payload_json["trigger"], "agent_lifecycle")
        self.assertEqual(events[0].decision, "deny")

    def test_quarantined_agent_cannot_record_handshake_and_attempt_is_audited(self) -> None:
        response = self.client.post(
            "/api/v1/trust/handshakes/record",
            headers=self._headers(correlation_id="corr-handshake-quarantine"),
            json={
                "source_agent_id": "handshake_source",
                "target_agent_id": "handshake_quarantined",
                "purpose": "handoff",
                "threshold_type": "handoff",
                "required_capabilities": ["claims:read"],
                "require_trust_card": False,
            },
        )

        self.assertEqual(response.status_code, 409, response.text)
        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                event_type="trust.handshake.blocked",
                correlation_id="corr-handshake-quarantine",
            )
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].decision, "deny")
        self.assertEqual(events[0].agent_id, "handshake_source")
        self.assertEqual(events[0].payload_json["target_agent_id"], "handshake_quarantined")
        self.assertEqual(events[0].payload_json["reason_code"], "agent_quarantined")

    def test_client_supplied_mesh_message_allow_is_overridden_by_server_policy(self) -> None:
        policy_id, version_id = self._create_mesh_deny_policy()

        response = self.client.post(
            "/api/v1/mesh/messages",
            headers=self._headers(correlation_id="corr-mesh-message-deny"),
            json={
                "source_agent_id": "mesh_source",
                "target_agent_id": "mesh_target",
                "protocol": "a2a",
                "action": "handoff.request",
                "decision": "allow",
                "latency_ms": 9,
                "payload_summary": {"client_decision": "allow"},
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertEqual(payload["decision"], "deny")
        self.assertEqual(payload["payload_summary"]["client_decision"], "allow")
        evidence = payload["payload_summary"]["server_decision"]
        self.assertEqual(evidence["policy_id"], policy_id)
        self.assertEqual(evidence["policy_version_id"], version_id)
        self.assertEqual(evidence["source_trust_snapshot"]["score"], 840)
        self.assertEqual(evidence["target_trust_snapshot"]["score"], 830)

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                event_type="mesh.message.blocked",
                resource_id=payload["id"],
            )
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].decision, "deny")

    def test_client_supplied_handoff_allow_is_overridden_by_server_policy(self) -> None:
        policy_id, version_id = self._create_mesh_deny_policy()

        response = self.client.post(
            "/api/v1/mesh/handoffs",
            headers=self._headers(correlation_id="corr-mesh-handoff-deny"),
            json={
                "source_agent_id": "mesh_source",
                "target_agent_id": "mesh_target",
                "task_type": "handoff.request",
                "required_capabilities": ["claims:read"],
                "trust_result": "allowed",
                "policy_result": "allow",
                "status": "accepted",
                "reason": "client supplied allow",
                "metadata": {"client_decision": "allow"},
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertEqual(payload["trust_result"], "allowed")
        self.assertEqual(payload["policy_result"], "deny")
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["reason"], "Mesh handoff is blocked by policy.")
        evidence = payload["metadata"]["server_decision"]
        self.assertEqual(evidence["policy_id"], policy_id)
        self.assertEqual(evidence["policy_version_id"], version_id)
        self.assertEqual(evidence["client_supplied"]["policy_result"], "allow")
        self.assertEqual(evidence["target_trust_snapshot"]["score"], 830)

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                event_type="mesh.handoff.blocked",
                resource_id=payload["id"],
            )
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].decision, "deny")


if __name__ == "__main__":
    unittest.main()
