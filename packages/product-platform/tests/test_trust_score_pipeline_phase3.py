from __future__ import annotations

import unittest

from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.trust.pipeline import TrustScoreRecalculator, apply_trust_delta
from product_platform.trust.repository import TrustRepository, trust_recalculation_run_response


class TrustScorePipelinePhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_recalc")

    def _insert_agent(self, connection, agent_id: str) -> None:
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
                "Recalc Agent",
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

    def test_score_cannot_exceed_1000(self) -> None:
        self.assertEqual(apply_trust_delta(995, 50), 1000)

    def test_score_cannot_go_below_0(self) -> None:
        self.assertEqual(apply_trust_delta(10, -50), 0)

    def test_recalculation_updates_score_and_creates_trust_event(self) -> None:
        with self.database.transaction() as connection:
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="policy.decision",
                    source_component="policy-engine",
                    actor_type="agent",
                    agent_id="agent_recalc",
                    decision="allow",
                    resource_type="policy",
                    resource_id="policy_1",
                    payload_json={},
                )
            )
            repository = TrustRepository(connection, "org_default", "env_default")
            run = TrustScoreRecalculator(repository).recalculate(agent_id="agent_recalc")
            score = repository.get_score("agent_recalc")
            events = repository.list_events(agent_id="agent_recalc")
            payload = trust_recalculation_run_response(run)

            self.assertEqual(score["score"], 508)
            self.assertEqual(score["tier"], "standard")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["dimension"], "policy_compliance")
            self.assertEqual(payload.status, "completed")
            self.assertEqual(payload.summary["mapped_event_count"], 1)

    def test_recalculation_writes_trust_changed_audit_event(self) -> None:
        with self.database.transaction() as connection:
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="policy.decision",
                    source_component="policy-engine",
                    actor_type="agent",
                    agent_id="agent_recalc",
                    decision="deny",
                    resource_type="policy",
                    resource_id="policy_1",
                    payload_json={},
                )
            )
            TrustScoreRecalculator(
                TrustRepository(connection, "org_default", "env_default")
            ).recalculate(agent_id="agent_recalc")

            audit_events = AuditEventRepository(connection).query(
                AuditEventQuery(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="trust.change",
                    agent_id="agent_recalc",
                )
            )

            self.assertEqual(len(audit_events), 1)
            self.assertEqual(audit_events[0].trust_delta, -35)
            self.assertEqual(audit_events[0].payload_json["new_score"], 465)


if __name__ == "__main__":
    unittest.main()
