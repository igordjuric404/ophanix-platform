from __future__ import annotations

import unittest

from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.trust.pipeline import TrustScoreRecalculator
from product_platform.trust.repository import TrustRepository, trust_score_response


class TrustScorePipelineOverallTests(unittest.TestCase):
    def test_allowed_and_denied_actions_recalculate_and_link_to_audit_events(self) -> None:
        database = create_migrated_test_database()
        with database.transaction() as connection:
            seed_demo_data(connection)
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
                    "agent_overall",
                    "org_default",
                    "env_default",
                    "Overall Agent",
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
            audit_repository = AuditEventRepository(connection)
            allowed = audit_repository.insert(
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="policy.decision",
                    source_component="policy-engine",
                    actor_type="agent",
                    agent_id="agent_overall",
                    decision="allow",
                    resource_type="policy",
                    resource_id="policy_allow",
                    payload_json={"reason": "demo allowed action"},
                )
            )
            denied = audit_repository.insert(
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="policy.decision",
                    source_component="policy-engine",
                    actor_type="agent",
                    agent_id="agent_overall",
                    decision="deny",
                    resource_type="policy",
                    resource_id="policy_deny",
                    payload_json={"reason": "demo denied action"},
                )
            )
            repository = TrustRepository(connection, "org_default", "env_default")

            TrustScoreRecalculator(repository).recalculate(agent_id="agent_overall")
            score = trust_score_response(repository.get_score("agent_overall"))
            events = repository.list_events(agent_id="agent_overall")
            trust_changes = audit_repository.query(
                AuditEventQuery(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="trust.change",
                    agent_id="agent_overall",
                )
            )

            self.assertEqual(score.score, 473)
            self.assertEqual(score.dimensions["policy_compliance"]["signal_count"], 2)
            self.assertEqual({event["source_event_id"] for event in events}, {allowed.id, denied.id})
            self.assertEqual(len(trust_changes), 1)
            self.assertEqual(trust_changes[0].payload_json["new_score"], 473)


if __name__ == "__main__":
    unittest.main()
