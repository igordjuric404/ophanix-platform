from __future__ import annotations

import unittest

from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.store import AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.trust.models import TrustRulePatchRequest
from product_platform.trust.pipeline import TrustSignalMapper
from product_platform.trust.repository import TrustRepository


class TrustScorePipelinePhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_signal")
            TrustRepository(connection, "org_default", "env_default").seed_default_rules()

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
                "Signal Agent",
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

    def _insert_event(self, connection, event: AuditEventEnvelope) -> AuditEventEnvelope:
        return AuditEventRepository(connection).insert(event)

    def test_policy_allow_creates_positive_compliance_delta(self) -> None:
        with self.database.transaction() as connection:
            event = self._insert_event(
                connection,
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="policy.decision",
                    source_component="policy-engine",
                    actor_type="agent",
                    agent_id="agent_signal",
                    decision="allow",
                    resource_type="policy",
                    resource_id="policy_1",
                    payload_json={"reason": "allowed"},
                ),
            )
            row = TrustSignalMapper(
                TrustRepository(connection, "org_default", "env_default")
            ).map_audit_event(event)

            self.assertIsNotNone(row)
            self.assertEqual(row["dimension"], "policy_compliance")
            self.assertGreater(row["delta"], 0)
            self.assertEqual(row["source_event_id"], event.id)
            self.assertEqual(row["score_before"], 500)
            self.assertEqual(row["score_after"], 508)

    def test_policy_deny_creates_negative_compliance_delta(self) -> None:
        with self.database.transaction() as connection:
            event = self._insert_event(
                connection,
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="policy.decision",
                    source_component="policy-engine",
                    actor_type="agent",
                    agent_id="agent_signal",
                    decision="deny",
                    resource_type="policy",
                    resource_id="policy_1",
                    payload_json={"reason": "denied"},
                ),
            )
            row = TrustSignalMapper(
                TrustRepository(connection, "org_default", "env_default")
            ).map_audit_event(event)

            self.assertIsNotNone(row)
            self.assertEqual(row["dimension"], "policy_compliance")
            self.assertLess(row["delta"], 0)
            self.assertEqual(row["score_after"], 465)

    def test_credential_rotation_creates_positive_security_delta(self) -> None:
        with self.database.transaction() as connection:
            event = self._insert_event(
                connection,
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="agent.credential.rotated",
                    source_component="agent-credentials",
                    actor_type="user",
                    actor_id="user_admin",
                    agent_id="agent_signal",
                    resource_type="agent_credential",
                    resource_id="cred_1",
                    payload_json={"reason": "scheduled rotation"},
                ),
            )
            row = TrustSignalMapper(
                TrustRepository(connection, "org_default", "env_default")
            ).map_audit_event(event)

            self.assertIsNotNone(row)
            self.assertEqual(row["dimension"], "security_posture")
            self.assertGreater(row["delta"], 0)
            self.assertEqual(row["score_after"], 518)

    def test_disabled_rule_creates_no_event(self) -> None:
        with self.database.transaction() as connection:
            repository = TrustRepository(connection, "org_default", "env_default")
            rule = [
                row
                for row in repository.list_rules()
                if row["event_type"] == "policy.decision.allow"
            ][0]
            repository.update_rule(rule["id"], TrustRulePatchRequest(enabled=False))
            event = self._insert_event(
                connection,
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="policy.decision",
                    source_component="policy-engine",
                    actor_type="agent",
                    agent_id="agent_signal",
                    decision="allow",
                    resource_type="policy",
                    resource_id="policy_1",
                    payload_json={},
                ),
            )

            row = TrustSignalMapper(repository).map_audit_event(event)

            self.assertIsNone(row)
            self.assertEqual(repository.list_events(), [])

    def test_pending_query_ignores_events_without_agent_id(self) -> None:
        with self.database.transaction() as connection:
            self._insert_event(
                connection,
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="policy.decision",
                    source_component="policy-engine",
                    actor_type="system",
                    decision="allow",
                    resource_type="policy",
                    resource_id="policy_1",
                    payload_json={},
                ),
            )

            mapped = TrustSignalMapper(
                TrustRepository(connection, "org_default", "env_default")
            ).map_pending_audit_events()

            self.assertEqual(mapped, [])


if __name__ == "__main__":
    unittest.main()
