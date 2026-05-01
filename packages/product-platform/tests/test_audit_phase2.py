from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.audit.events import AuditEventEnvelope, policy_decision_event
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class AuditPhase2RepositoryTests(unittest.TestCase):
    def test_integration_inserts_and_reads_event(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                event = policy_decision_event(
                    organization_id="org_default",
                    environment_id="env_default",
                    actor_id="user_admin",
                    policy_id="policy_1",
                    decision="allow",
                    matched_rule="allow-read",
                    reason="Read-only action.",
                    correlation_id="corr-1",
                )
                AuditEventRepository(connection).insert(event)

            stored = AuditEventRepository(database.connect()).get(event.id, "org_default")

            self.assertIsNotNone(stored)
            self.assertEqual(stored.event_type, "policy.decision")
            self.assertEqual(stored.payload_json["reason"], "Read-only action.")
        finally:
            database.close()

    def test_pagination_is_stable_by_created_time_and_id(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                repository = AuditEventRepository(connection)
                for event_id in ["evt_a", "evt_b", "evt_c"]:
                    repository.insert(
                        AuditEventEnvelope(
                            id=event_id,
                            organization_id="org_default",
                            environment_id="env_default",
                            event_type="test.pagination",
                            source_component="tests",
                            actor_type="system",
                            created_at="2026-04-30T00:00:00+00:00",
                        )
                    )

            repository = AuditEventRepository(database.connect())
            first_page = repository.query(
                AuditEventQuery(organization_id="org_default", limit=2, offset=0)
            )
            second_page = repository.query(
                AuditEventQuery(organization_id="org_default", limit=2, offset=2)
            )

            self.assertEqual([event.id for event in first_page], ["evt_c", "evt_b"])
            self.assertEqual([event.id for event in second_page], ["evt_a"])
        finally:
            database.close()


class AuditPhase2ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            )
        )
        self.client = TestClient(
            self.app,
            raise_server_exceptions=False,
        )
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Platform Admin"]},
        )
        self.headers = {
            "Authorization": f"Bearer {login.json()['access_token']}",
            "X-Environment-ID": "env_default",
        }

    def tearDown(self) -> None:
        database = getattr(self.app.state, "database", None)
        if database is not None:
            database.close()

    def test_api_filters_by_correlation_id(self) -> None:
        event_a = policy_decision_event(
            organization_id="org_default",
            environment_id="env_default",
            actor_id="user_admin",
            policy_id="policy_1",
            decision="allow",
            matched_rule="allow-read",
            reason="Read-only action.",
            correlation_id="corr-match",
        )
        event_b = policy_decision_event(
            organization_id="org_default",
            environment_id="env_default",
            actor_id="user_admin",
            policy_id="policy_2",
            decision="deny",
            matched_rule="deny-delete",
            reason="Dangerous action.",
            correlation_id="corr-other",
        )

        create_a = self.client.post(
            "/api/v1/audit/events",
            json=event_a.model_dump(),
            headers=self.headers,
        )
        create_b = self.client.post(
            "/api/v1/audit/events",
            json=event_b.model_dump(),
            headers=self.headers,
        )
        listed = self.client.get(
            "/api/v1/audit/events?correlation_id=corr-match",
            headers=self.headers,
        )

        self.assertEqual(create_a.status_code, 201)
        self.assertEqual(create_b.status_code, 201)
        self.assertEqual(listed.status_code, 200)
        payload = listed.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["correlation_id"], "corr-match")


if __name__ == "__main__":
    unittest.main()
