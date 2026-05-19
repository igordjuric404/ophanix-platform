from __future__ import annotations

import json
import unittest
from pathlib import Path

from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.store import AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.trust.pipeline import TrustScoreRecalculator
from product_platform.trust.repository import (
    DEFAULT_TRUST_THRESHOLDS,
    TrustRepository,
    trust_score_response,
)
from product_platform.trust.schema import TRUST_SCORE_SCHEMA_VERSION, trust_score_contract


class AgentMeshTrustRemediationPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "schema_agent", "Schema Agent")

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

    def _shared_contract(self) -> dict:
        root = Path(__file__).resolve().parents[3]
        return json.loads((root / "docs/contracts/trust-score-schema-v1.json").read_text())

    def test_product_contract_matches_shared_schema_snapshot(self) -> None:
        self.assertEqual(trust_score_contract(), self._shared_contract())
        self.assertEqual(TRUST_SCORE_SCHEMA_VERSION, "trust.score.v1")

    def test_default_thresholds_match_canonical_contract(self) -> None:
        expected = {
            item["threshold_type"]: item
            for item in self._shared_contract()["thresholds"]
        }
        actual = {
            item.threshold_type: {
                "threshold_type": item.threshold_type,
                "target_type": item.target_type,
                "target_id": None if item.target_id == "" else item.target_id,
                "min_score": item.min_score,
                "required_tier": item.required_tier,
            }
            for item in DEFAULT_TRUST_THRESHOLDS
        }

        self.assertEqual(actual, expected)

    def test_recalculated_score_has_canonical_schema_and_explanation(self) -> None:
        with self.database.transaction() as connection:
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="policy.decision",
                    source_component="policy-engine",
                    actor_type="agent",
                    agent_id="schema_agent",
                    decision="deny",
                    resource_type="policy",
                    resource_id="policy_1",
                    payload_json={"reason": "schema consistency regression"},
                )
            )
            repository = TrustRepository(connection, "org_default", "env_default")
            TrustScoreRecalculator(repository).recalculate(agent_id="schema_agent")
            payload = trust_score_response(repository.get_score("schema_agent"))

            contract = self._shared_contract()
            dimension_names = [item["name"] for item in contract["dimensions"]]
            self.assertEqual(payload.schema_version, contract["schema_version"])
            self.assertEqual(sorted(payload.dimensions), sorted(dimension_names))
            self.assertEqual(payload.explanation["schema_version"], contract["schema_version"])
            self.assertEqual(payload.explanation["input_event_count"], 1)
            self.assertEqual(
                payload.explanation["dimensions"]["policy_compliance"]["signal_count"],
                1,
            )
            self.assertEqual(payload.explanation["source_event_versions"], ["audit_events.v1"])


if __name__ == "__main__":
    unittest.main()
