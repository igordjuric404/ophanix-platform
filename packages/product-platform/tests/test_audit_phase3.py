from __future__ import annotations

import json
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.hash_chain import canonical_event_hash_input
from product_platform.audit.store import AuditEventRepository
from product_platform.api.settings import Settings
from product_platform.db.postgres import IntegrityError
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class AuditPhase3Tests(unittest.TestCase):
    def test_canonical_hash_input_is_stable(self) -> None:
        event = AuditEventEnvelope(
            id="evt_stable",
            organization_id="org_default",
            environment_id="env_default",
            event_type="test.hash",
            source_component="tests",
            actor_type="system",
            payload_json={"b": 2, "a": 1},
            created_at="2026-04-30T00:00:00+00:00",
        )

        first = canonical_event_hash_input(event, "previous")
        second = canonical_event_hash_input(event, "previous")

        self.assertEqual(first, second)
        self.assertIn('"previous_hash":"previous"', first)

    def test_hash_chain_verifies_after_inserts(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                repository = AuditEventRepository(connection)
                repository.insert(_event("evt_hash_a"))
                repository.insert(_event("evt_hash_b"))

            repository = AuditEventRepository(database.connect())
            single = repository.verify_event("evt_hash_a", "org_default")
            chain = repository.verify_range("org_default")

            self.assertTrue(single.valid)
            self.assertTrue(chain.valid)
            self.assertEqual(chain.checked_count, 2)
        finally:
            database.close()

    def test_hash_range_verification_is_environment_scoped(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                connection.execute(
                    """
                    INSERT INTO environments
                        (id, organization_id, name, slug, type, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "env_other",
                        "org_default",
                        "Other",
                        "other",
                        "development",
                        "2026-04-30T00:00:00+00:00",
                        "2026-04-30T00:00:00+00:00",
                    ),
                )
                repository = AuditEventRepository(connection)
                repository.insert(_event("evt_default_a"))
                repository.insert(_event("evt_other", environment_id="env_other"))
                repository.insert(_event("evt_default_b"))
                _tamper_event_payload_for_test(connection, "evt_other")

            repository = AuditEventRepository(database.connect())
            scoped = repository.verify_range("org_default", environment_id="env_default")
            organization_wide = repository.verify_range("org_default")

            self.assertTrue(scoped.valid)
            self.assertEqual(scoped.checked_count, 2)
            self.assertFalse(organization_wide.valid)
            self.assertEqual(organization_wide.failed_event_id, "evt_other")
        finally:
            database.close()

    def test_audit_event_and_hash_rows_are_append_only(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                AuditEventRepository(connection).insert(_event("evt_append_only"))

            with self.assertRaises(IntegrityError):
                with database.transaction() as connection:
                    connection.execute(
                        "UPDATE audit_events SET payload_json = ? WHERE id = ?",
                        (json.dumps({"tampered": True}), "evt_append_only"),
                    )

            with self.assertRaises(IntegrityError):
                with database.transaction() as connection:
                    connection.execute(
                        "DELETE FROM audit_event_hashes WHERE event_id = ?",
                        ("evt_append_only",),
                    )
        finally:
            database.close()

    def test_checkpoint_detects_missing_audit_row(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                repository = AuditEventRepository(connection)
                repository.insert(_event("evt_checkpoint_a"))
                repository.insert(_event("evt_checkpoint_b"))
                checkpoint = repository.create_checkpoint(
                    "org_default",
                    environment_id="env_default",
                    created_by="test",
                )
                self.assertEqual(checkpoint["event_count"], 2)
                self.assertIsNotNone(checkpoint["signature"])
                _delete_event_for_test(connection, "evt_checkpoint_b")

            verification = AuditEventRepository(database.connect()).verify_range(
                "org_default",
                environment_id="env_default",
            )

            self.assertFalse(verification.valid)
            self.assertEqual(verification.failed_event_id, "evt_checkpoint_b")
            self.assertEqual(verification.reason, "checkpoint_event_missing")
            self.assertEqual(verification.checkpoint_id, checkpoint["id"])
        finally:
            database.close()

    def test_stream_cursor_from_other_environment_does_not_advance_selected_environment(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                connection.execute(
                    """
                    INSERT INTO environments
                        (id, organization_id, name, slug, type, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "env_other",
                        "org_default",
                        "Other",
                        "other",
                        "development",
                        "2026-04-30T00:00:00+00:00",
                        "2026-04-30T00:00:00+00:00",
                    ),
                )
                repository = AuditEventRepository(connection)
                repository.insert(_event("evt_default_cursor_a"))
                repository.insert(_event("evt_other_cursor", environment_id="env_other"))
                repository.insert(_event("evt_default_cursor_b"))

            streamed = AuditEventRepository(database.connect()).stream_events(
                organization_id="org_default",
                environment_id="env_default",
                last_event_id="evt_other_cursor",
            )

            self.assertEqual(
                [event.id for event in streamed],
                ["evt_default_cursor_a", "evt_default_cursor_b"],
            )
        finally:
            database.close()


class AuditPhase3ApiTests(unittest.TestCase):
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
        self.client = TestClient(self.app, raise_server_exceptions=False)
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

    def test_api_verifies_single_event_and_range(self) -> None:
        event = _event("evt_api_hash")
        created = self.client.post(
            "/api/v1/audit/events",
            json=event.model_dump(),
            headers=self.headers,
        )
        verify_event = self.client.post(
            f"/api/v1/audit/events/{created.json()['id']}/verify",
            headers=self.headers,
        )
        verify_range = self.client.post("/api/v1/audit/verify-range", headers=self.headers)

        self.assertEqual(created.status_code, 201)
        self.assertEqual(verify_event.status_code, 200)
        self.assertEqual(verify_range.status_code, 200)
        self.assertTrue(verify_event.json()["valid"])
        self.assertTrue(verify_range.json()["valid"])

    def test_tampered_payload_fails_verification(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                AuditEventRepository(connection).insert(_event("evt_hash_tamper"))
                _tamper_event_payload_for_test(connection, "evt_hash_tamper")

            verification = AuditEventRepository(database.connect()).verify_range("org_default")

            self.assertFalse(verification.valid)
            self.assertEqual(verification.failed_event_id, "evt_hash_tamper")
            self.assertEqual(verification.reason, "hash_mismatch")
        finally:
            database.close()


def _event(event_id: str, *, environment_id: str = "env_default") -> AuditEventEnvelope:
    return AuditEventEnvelope(
        id=event_id,
        organization_id="org_default",
        environment_id=environment_id,
        event_type="test.hash",
        source_component="tests",
        actor_type="system",
        payload_json={"event_id": event_id},
        created_at=f"2026-04-30T00:00:0{event_id[-1] if event_id[-1].isdigit() else 0}+00:00",
    )


def _tamper_event_payload_for_test(connection, event_id: str) -> None:
    """Bypass append-only guards to simulate privileged storage tampering."""

    connection.execute("ALTER TABLE audit_events DISABLE TRIGGER trg_audit_events_append_only")
    try:
        connection.execute(
            "UPDATE audit_events SET payload_json = ? WHERE id = ?",
            (json.dumps({"tampered": True}), event_id),
        )
    finally:
        connection.execute("ALTER TABLE audit_events ENABLE TRIGGER trg_audit_events_append_only")


def _delete_event_for_test(connection, event_id: str) -> None:
    """Bypass append-only guards to simulate a missing row beneath a checkpoint."""

    connection.execute(
        "ALTER TABLE audit_event_hashes DISABLE TRIGGER trg_audit_event_hashes_append_only"
    )
    connection.execute("ALTER TABLE audit_events DISABLE TRIGGER trg_audit_events_append_only")
    try:
        connection.execute("DELETE FROM audit_event_hashes WHERE event_id = ?", (event_id,))
        connection.execute("DELETE FROM audit_events WHERE id = ?", (event_id,))
    finally:
        connection.execute("ALTER TABLE audit_events ENABLE TRIGGER trg_audit_events_append_only")
        connection.execute(
            "ALTER TABLE audit_event_hashes ENABLE TRIGGER trg_audit_event_hashes_append_only"
        )


if __name__ == "__main__":
    unittest.main()
