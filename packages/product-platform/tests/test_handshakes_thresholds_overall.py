from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.trust.repository import TrustRepository


class HandshakesThresholdsOverallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "handoff_high", "Handoff High", 820, ["claims:read"])
            self._insert_agent(connection, "handoff_low", "Handoff Low", 420, ["claims:read"])
            self._insert_agent(connection, "handoff_target", "Handoff Target", 780, ["claims:read"])
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
            "X-Correlation-ID": "corr-handshake-overall",
        }

    def _insert_agent(
        self,
        connection,
        agent_id: str,
        name: str,
        score: int,
        capabilities: list[str],
    ) -> None:
        now = "2026-05-01T00:00:00+00:00"
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
                "Overall handshake test agent",
                "langgraph",
                "service",
                "owner",
                "sponsor",
                "active",
                score,
                "trusted" if score >= 700 else "probationary",
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
        for capability in capabilities:
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
        TrustRepository(connection, "org_default", "env_default").upsert_score(
            agent_id=agent_id,
            score=score,
            dimensions={"policy_compliance": {"score": score, "signal_count": 1}},
        )

    def _simulate(self, source_agent_id: str) -> dict:
        response = self.client.post(
            "/api/v1/trust/handshakes/simulate",
            headers=self._headers(),
            json={
                "source_agent_id": source_agent_id,
                "target_agent_id": "handoff_target",
                "purpose": "handoff",
                "threshold_type": "handoff",
                "required_capabilities": ["claims:read"],
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_handoff_threshold_allows_high_trust_and_denies_low_trust(self) -> None:
        thresholds = self.client.get("/api/v1/trust/thresholds", headers=self._headers())
        self.assertEqual(thresholds.status_code, 200)
        handoff = next(
            item for item in thresholds.json() if item["threshold_type"] == "handoff"
        )
        patched = self.client.patch(
            f"/api/v1/trust/thresholds/{handoff['id']}",
            headers=self._headers(),
            json={"min_score": 700, "required_tier": "trusted"},
        )
        self.assertEqual(patched.status_code, 200)

        allowed = self._simulate("handoff_high")
        denied = self._simulate("handoff_low")
        listed = self.client.get(
            "/api/v1/trust/handshakes?source_agent_id=handoff_low",
            headers=self._headers(),
        )

        self.assertEqual(allowed["result"], "allowed")
        self.assertEqual(allowed["reason"], "trust_threshold_satisfied")
        self.assertEqual(denied["result"], "denied")
        self.assertEqual(denied["reason"], "low_trust")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], denied["id"])
        self.assertEqual(listed.json()[0]["reason"], "low_trust")


if __name__ == "__main__":
    unittest.main()
