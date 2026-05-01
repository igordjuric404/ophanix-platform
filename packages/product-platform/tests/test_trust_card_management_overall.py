from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.trust.repository import TrustRepository


class TrustCardManagementOverallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent_identity_capability(connection)
            TrustRepository(connection, "org_default", "env_default").upsert_score(
                agent_id="agent_card_overall",
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
            "X-Correlation-ID": "corr-trust-card-overall",
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
                "agent_card_overall",
                "org_default",
                "env_default",
                "Overall Card Agent",
                "Exercises the full trust-card lifecycle",
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
                "ident_card_overall",
                "agent_card_overall",
                "did:mesh:cardoverall",
                "fingerprint_card_overall",
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
                "cap_card_overall",
                "agent_card_overall",
                "claims:read",
                "claim",
                "approved",
                "owner",
                "approver",
                now,
            ),
        )

    def test_issue_verify_revoke_and_current_card_flow(self) -> None:
        issued = self.client.post(
            "/api/v1/trust/cards",
            headers=self._headers(),
            json={"agent_id": "agent_card_overall", "issuer": "ophanix-demo"},
        )
        self.assertEqual(issued.status_code, 201)
        card = issued.json()
        self.assertEqual(card["card"]["agent_did"], "did:mesh:cardoverall")
        self.assertEqual(card["card"]["metadata"]["trust_score"], 735)

        verified = self.client.post(
            f"/api/v1/trust/cards/{card['id']}/verify",
            headers=self._headers(),
        )
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.json()["verified"], True)
        self.assertEqual(verified.json()["reason"], "signature_valid")

        current = self.client.get(
            "/api/v1/agents/agent_card_overall/trust-card",
            headers=self._headers(),
        )
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json()["card"]["id"], card["id"])
        self.assertIsNone(current.json()["warning"])

        revoked = self.client.post(
            f"/api/v1/trust/cards/{card['id']}/revoke",
            headers=self._headers(),
            json={"reason": "retired"},
        )
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(revoked.json()["status"], "revoked")
        self.assertEqual(revoked.json()["revocation_reason"], "retired")

        verified_after_revoke = self.client.post(
            f"/api/v1/trust/cards/{card['id']}/verify",
            headers=self._headers(),
        )
        self.assertEqual(verified_after_revoke.status_code, 200)
        self.assertEqual(verified_after_revoke.json()["verified"], False)
        self.assertEqual(verified_after_revoke.json()["reason"], "revoked")

        current_after_revoke = self.client.get(
            "/api/v1/agents/agent_card_overall/trust-card",
            headers=self._headers(),
        )
        self.assertEqual(current_after_revoke.status_code, 200)
        self.assertIsNone(current_after_revoke.json()["card"])
        self.assertIn("No valid trust card", current_after_revoke.json()["warning"])


if __name__ == "__main__":
    unittest.main()
