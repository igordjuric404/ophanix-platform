from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.trust.repository import TrustRepository


class TrustCardManagementPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent_identity_capability(connection)
            TrustRepository(connection, "org_default", "env_default").upsert_score(
                agent_id="agent_card_api",
                score=735,
                dimensions={"policy_compliance": {"score": 735, "signal_count": 1}},
            )
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
            "X-Correlation-ID": "corr-trust-card",
        }

    def _insert_agent_identity_capability(self, connection) -> None:
        now = "2026-05-01T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, owner_user_id, sponsor_user_id, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "agent_card_api",
                "org_default",
                "env_default",
                "Card API Agent",
                "Handles card API tests",
                "langgraph",
                "service",
                "owner",
                "sponsor",
                "active",
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
                "ident_card_api",
                "agent_card_api",
                "did:mesh:cardapi",
                "fingerprint_card_api",
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
                "cap_card_api",
                "agent_card_api",
                "claims:read",
                "claim",
                "approved",
                "owner",
                "approver",
                now,
            ),
        )

    def _issue_card(self) -> dict:
        issued = self.client.post(
            "/api/v1/trust/cards",
            headers=self._headers(),
            json={"agent_id": "agent_card_api", "issuer": "ophanix-demo"},
        )
        self.assertEqual(issued.status_code, 201)
        return issued.json()

    def test_api_verify_valid_card(self) -> None:
        card = self._issue_card()

        verified = self.client.post(
            f"/api/v1/trust/cards/{card['id']}/verify",
            headers=self._headers(),
        )

        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.json()["verified"], True)
        self.assertEqual(verified.json()["reason"], "signature_valid")

    def test_api_revoked_card_reports_revoked(self) -> None:
        card = self._issue_card()
        revoked = self.client.post(
            f"/api/v1/trust/cards/{card['id']}/revoke",
            headers=self._headers(),
            json={"reason": "key rotation"},
        )
        verified = self.client.post(
            f"/api/v1/trust/cards/{card['id']}/verify",
            headers=self._headers(),
        )

        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(revoked.json()["status"], "revoked")
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.json()["verified"], False)
        self.assertEqual(verified.json()["reason"], "revoked")

    def test_api_revocation_requires_reason(self) -> None:
        card = self._issue_card()

        response = self.client.post(
            f"/api/v1/trust/cards/{card['id']}/revoke",
            headers=self._headers(),
            json={"reason": ""},
        )

        self.assertEqual(response.status_code, 422)

    def test_integration_audit_events_emitted(self) -> None:
        card = self._issue_card()
        revoked = self.client.post(
            f"/api/v1/trust/cards/{card['id']}/revoke",
            headers=self._headers(),
            json={"reason": "no longer current"},
        )
        self.assertEqual(revoked.status_code, 200)

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="trust_card",
            )
        )

        self.assertEqual([event.event_type for event in events], ["trust.card.revoked", "trust.card.issued"])
        self.assertEqual(events[0].resource_id, card["id"])
        self.assertEqual(events[0].payload_json["reason"], "no longer current")
        self.assertEqual(events[0].correlation_id, "corr-trust-card")


if __name__ == "__main__":
    unittest.main()
