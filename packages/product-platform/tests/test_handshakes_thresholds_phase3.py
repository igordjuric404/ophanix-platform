from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.trust.cards import TrustCardIssuer, TrustCardRepository
from product_platform.trust.models import TrustCardIssueRequest
from product_platform.trust.repository import TrustRepository


class HandshakesThresholdsPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "source_high", "Source High", 820)
            self._insert_agent(connection, "source_low", "Source Low", 420)
            self._insert_agent(connection, "target_high", "Target High", 780, ["claims:read"])
            self._insert_agent(connection, "target_no_cap", "Target No Capability", 780)
            self._insert_agent(
                connection,
                "target_expired",
                "Target Expired",
                780,
                ["claims:read"],
                credential_status="expired",
                credential_expires_at="2020-01-01T00:00:00+00:00",
            )
            self._insert_agent(connection, "target_revoked", "Target Revoked", 780, ["claims:read"])
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
            "X-Correlation-ID": "corr-handshake",
        }

    def _insert_agent(
        self,
        connection,
        agent_id: str,
        name: str,
        score: int,
        capabilities: list[str] | None = None,
        *,
        credential_status: str = "active",
        credential_expires_at: str = "2030-01-01T00:00:00+00:00",
    ) -> None:
        now = "2026-05-01T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, owner_user_id, sponsor_user_id, status, trust_score,
                trust_tier, credential_status, credential_expires_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                "org_default",
                "env_default",
                name,
                "Handshake test agent",
                "langgraph",
                "service",
                "owner",
                "sponsor",
                "active",
                score,
                "trusted" if score >= 700 else "probationary",
                credential_status,
                credential_expires_at,
                now,
                now,
            ),
        )
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
                f"did:mesh:{agent_id}",
                f"fingerprint_{agent_id}",
                "ed25519",
                "active",
                None,
                now,
                now,
            ),
        )
        for capability in capabilities or []:
            connection.execute(
                """
                INSERT INTO agent_capabilities (
                    id, agent_id, capability_name, resource_type, status,
                    requested_by, approved_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"cap_{agent_id}_{capability.replace(':', '_')}",
                    agent_id,
                    capability,
                    "claim",
                    "approved",
                    "owner",
                    "approver",
                    now,
                ),
            )
        connection.execute(
            """
            INSERT INTO agent_credentials (
                id, agent_id, credential_type, token_hash, issuer, status,
                issued_at, expires_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"cred_{agent_id}",
                agent_id,
                "api_key",
                f"hash_{agent_id}",
                "ophanix-test",
                credential_status,
                now,
                credential_expires_at,
                "{}",
            ),
        )
        TrustRepository(connection, "org_default", "env_default").upsert_score(
            agent_id=agent_id,
            score=score,
            dimensions={"policy_compliance": {"score": score, "signal_count": 1}},
        )

    def _handshake_payload(self, source: str, target: str, **overrides) -> dict:
        payload = {
            "source_agent_id": source,
            "target_agent_id": target,
            "purpose": "handoff",
            "threshold_type": "handoff",
            "required_capabilities": ["claims:read"],
        }
        payload.update(overrides)
        return payload

    def test_api_successful_simulated_handshake(self) -> None:
        response = self.client.post(
            "/api/v1/trust/handshakes/simulate",
            headers=self._headers(),
            json=self._handshake_payload("source_high", "target_high"),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["result"], "allowed")
        self.assertEqual(response.json()["reason"], "trust_threshold_satisfied")
        self.assertEqual(response.json()["source_score"], 820)
        self.assertEqual(response.json()["target_score"], 780)

        listed = self.client.get("/api/v1/trust/handshakes", headers=self._headers())
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], response.json()["id"])

    def test_api_low_trust_fails_with_reason(self) -> None:
        response = self.client.post(
            "/api/v1/trust/handshakes/simulate",
            headers=self._headers(),
            json=self._handshake_payload("source_low", "target_high"),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["result"], "denied")
        self.assertEqual(response.json()["reason"], "low_trust")

    def test_api_missing_capability_fails_with_reason(self) -> None:
        response = self.client.post(
            "/api/v1/trust/handshakes/simulate",
            headers=self._headers(),
            json=self._handshake_payload("source_high", "target_no_cap"),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["result"], "denied")
        self.assertEqual(response.json()["reason"], "missing_capability")

    def test_api_expired_credential_fails_when_required(self) -> None:
        response = self.client.post(
            "/api/v1/trust/handshakes/simulate",
            headers=self._headers(),
            json=self._handshake_payload(
                "source_high",
                "target_expired",
                require_active_credential=True,
            ),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["result"], "denied")
        self.assertEqual(response.json()["reason"], "expired_credential")

    def test_api_revoked_trust_card_fails_when_required(self) -> None:
        with self.database.transaction() as connection:
            card = TrustCardIssuer(connection, "org_default", "env_default").issue(
                TrustCardIssueRequest(agent_id="target_revoked")
            )
            TrustCardRepository(connection, "org_default", "env_default").revoke_card(
                card["id"],
                reason="retired",
                revoked_by="admin",
            )

        response = self.client.post(
            "/api/v1/trust/handshakes/simulate",
            headers=self._headers(),
            json=self._handshake_payload(
                "source_high",
                "target_revoked",
                require_trust_card=True,
            ),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["result"], "denied")
        self.assertEqual(response.json()["reason"], "revoked_trust_card")

    def test_integration_handshake_writes_audit_event(self) -> None:
        response = self.client.post(
            "/api/v1/trust/handshakes/record",
            headers=self._headers(),
            json=self._handshake_payload("source_high", "target_high"),
        )
        self.assertEqual(response.status_code, 201)

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="handshake",
            )
        )

        self.assertEqual(events[0].event_type, "trust.handshake")
        self.assertEqual(events[0].resource_id, response.json()["id"])
        self.assertEqual(events[0].decision, "allow")
        self.assertEqual(events[0].correlation_id, "corr-handshake")


if __name__ == "__main__":
    unittest.main()
