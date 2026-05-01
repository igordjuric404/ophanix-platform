from __future__ import annotations

import unittest

from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.trust.repository import (
    DEFAULT_TRUST_RULES,
    TrustRepository,
    calculate_trust_tier,
    trust_score_response,
)


class TrustScorePipelinePhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_trust", "Trusted Helper")

    def _insert_agent(self, connection, agent_id: str, name: str) -> None:
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
                agent_id,
                "org_default",
                "env_default",
                name,
                "",
                "langgraph",
                "service",
                "owner",
                "sponsor",
                "active",
                now,
                now,
            ),
        )

    def test_seed_default_trust_rules_is_idempotent(self) -> None:
        with self.database.transaction() as connection:
            repository = TrustRepository(connection, "org_default", "env_default")
            first = repository.seed_default_rules()
            second = repository.seed_default_rules()

            self.assertEqual(len(first), len(DEFAULT_TRUST_RULES))
            self.assertEqual(len(second), len(DEFAULT_TRUST_RULES))
            self.assertEqual(
                sorted(row["event_type"] for row in second),
                sorted(rule.event_type for rule in DEFAULT_TRUST_RULES),
            )

    def test_create_and_retrieve_trust_score(self) -> None:
        with self.database.transaction() as connection:
            repository = TrustRepository(connection, "org_default", "env_default")
            row = repository.upsert_score(
                agent_id="agent_trust",
                score=735,
                dimensions={
                    "policy_compliance": {"score": 720, "signal_count": 3},
                    "security_posture": {"score": 750, "signal_count": 2},
                },
            )
            loaded = repository.get_score("agent_trust")
            agent = connection.execute(
                "SELECT trust_score, trust_tier FROM agents WHERE id = ?",
                ("agent_trust",),
            ).fetchone()

            self.assertIsNotNone(loaded)
            self.assertEqual(row["score"], 735)
            self.assertEqual(loaded["tier"], "trusted")
            self.assertEqual(agent["trust_score"], 735)
            self.assertEqual(agent["trust_tier"], "trusted")
            payload = trust_score_response(loaded)
            self.assertEqual(payload.agent_name, "Trusted Helper")
            self.assertEqual(payload.dimensions["security_posture"]["signal_count"], 2)

    def test_tier_calculation_maps_expected_boundaries(self) -> None:
        self.assertEqual(calculate_trust_tier(1000), "verified_partner")
        self.assertEqual(calculate_trust_tier(900), "verified_partner")
        self.assertEqual(calculate_trust_tier(899), "trusted")
        self.assertEqual(calculate_trust_tier(700), "trusted")
        self.assertEqual(calculate_trust_tier(699), "standard")
        self.assertEqual(calculate_trust_tier(500), "standard")
        self.assertEqual(calculate_trust_tier(499), "probationary")
        self.assertEqual(calculate_trust_tier(300), "probationary")
        self.assertEqual(calculate_trust_tier(299), "untrusted")
        self.assertEqual(calculate_trust_tier(-10), "untrusted")


if __name__ == "__main__":
    unittest.main()
