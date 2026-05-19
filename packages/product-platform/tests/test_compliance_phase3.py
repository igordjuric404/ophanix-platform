from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.runtime_audit import (
    ToolRuntimeActionCreate,
    ToolRuntimeActionRepository,
)


class CompliancePhase3ViolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
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
        return {"Authorization": f"Bearer {self.token}", "X-Environment-ID": "env_default"}

    def _insert_audit_event(self, event: AuditEventEnvelope) -> str:
        with self.database.transaction() as connection:
            return AuditEventRepository(connection).insert(event).id

    def _create_runtime_denial_violation(self) -> dict[str, object]:
        event_id = self._insert_audit_event(
            AuditEventEnvelope(
                organization_id="org_default",
                environment_id="env_default",
                event_type="runtime.action",
                source_component="runtime-control",
                actor_type="system",
                actor_id="runtime-worker",
                agent_id="agent_runtime",
                resource_type="runtime_action",
                resource_id="rtact_blocked",
                decision="deny",
                severity="critical",
                payload_json={"action": "billing.delete", "reason": "blocked by runtime policy"},
            )
        )
        recompute = self.client.post(
            "/api/v1/compliance/evidence/recompute",
            headers=self._headers(),
        )
        self.assertEqual(recompute.status_code, 201, recompute.text)
        listed = self.client.get(
            "/api/v1/compliance/violations",
            headers=self._headers(),
            params={"status": "open", "severity": "critical"},
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(1, len(listed.json()))
        violation = listed.json()[0]
        self.assertEqual(event_id, violation["source_event_id"])
        return violation

    def test_high_severity_denial_creates_open_violation(self) -> None:
        violation = self._create_runtime_denial_violation()

        self.assertEqual("LOG-1", violation["control_code"])
        self.assertEqual("agent_runtime", violation["agent_id"])
        self.assertEqual("critical", violation["severity"])
        self.assertEqual("open", violation["status"])
        self.assertEqual("audit_event", violation["source_type"])
        self.assertIn("blocked by runtime policy", violation["reason"])

    def test_tool_runtime_denial_creates_open_violation(self) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO agents (
                    id, organization_id, environment_id, name, description, framework,
                    runtime_type, owner_user_id, sponsor_user_id, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "agent_runtime",
                    "org_default",
                    "env_default",
                    "Runtime Test Agent",
                    "Runtime violation fixture.",
                    "custom",
                    "http",
                    "user_admin",
                    "user_admin",
                    "active",
                    "2026-05-01T00:00:00+00:00",
                    "2026-05-01T00:00:00+00:00",
                ),
            )
            action = ToolRuntimeActionRepository(
                connection,
                "org_default",
                "env_default",
            ).create_action(
                ToolRuntimeActionCreate(
                    request_id="req-runtime-denied",
                    correlation_id="corr-runtime-denied",
                    agent_id="agent_runtime",
                    action_status="denied",
                    reason_code="tool_policy_denied",
                    payload_summary={"tool_name": "danger.delete"},
                    error_code="tool_call_denied",
                ),
                created_at="2026-05-01T00:00:00+00:00",
            )

        recompute = self.client.post(
            "/api/v1/compliance/evidence/recompute",
            headers=self._headers(),
        )
        listed = self.client.get(
            "/api/v1/compliance/violations",
            headers=self._headers(),
            params={"status": "open"},
        )

        self.assertEqual(recompute.status_code, 201, recompute.text)
        runtime_violations = [
            violation
            for violation in listed.json()
            if violation["source_type"] == "tool_runtime_action"
            and violation["source_id"] == action["id"]
        ]
        self.assertEqual(1, len(runtime_violations))
        self.assertEqual("LOG-1", runtime_violations[0]["control_code"])
        self.assertEqual("agent_runtime", runtime_violations[0]["agent_id"])
        self.assertIn("tool_policy_denied", runtime_violations[0]["reason"])

    def test_lists_open_violations_including_missing_controls(self) -> None:
        self._create_runtime_denial_violation()

        listed = self.client.get(
            "/api/v1/compliance/violations",
            headers=self._headers(),
            params={"status": "open"},
        )

        self.assertEqual(listed.status_code, 200, listed.text)
        reasons = {violation["reason"] for violation in listed.json()}
        self.assertIn("blocked by runtime policy", reasons)
        self.assertTrue(any("has no fresh evidence" in reason for reason in reasons))

    def test_acknowledge_and_resolve_violation_emit_audit_events(self) -> None:
        violation = self._create_runtime_denial_violation()

        acknowledged = self.client.patch(
            f"/api/v1/compliance/violations/{violation['id']}",
            headers=self._headers(),
            json={"status": "acknowledged"},
        )
        missing_reason = self.client.patch(
            f"/api/v1/compliance/violations/{violation['id']}",
            headers=self._headers(),
            json={"status": "resolved"},
        )
        resolved = self.client.patch(
            f"/api/v1/compliance/violations/{violation['id']}",
            headers=self._headers(),
            json={"status": "resolved", "reason": "Reviewed and accepted compensating control."},
        )

        self.assertEqual(acknowledged.status_code, 200, acknowledged.text)
        self.assertEqual(acknowledged.json()["status"], "acknowledged")
        self.assertEqual(missing_reason.status_code, 422, missing_reason.text)
        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.assertEqual(resolved.json()["status"], "resolved")
        self.assertEqual(
            "Reviewed and accepted compensating control.",
            resolved.json()["resolution_reason"],
        )
        with self.database.connect() as connection:
            audit_events = AuditEventRepository(connection).query(
                AuditEventQuery(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="compliance.violation.resolved",
                    resource_id=violation["id"],
                    limit=10,
                )
            )
        self.assertEqual(1, len(audit_events))
        self.assertEqual("compliance", audit_events[0].source_component)
        self.assertEqual("resolved", audit_events[0].decision)

    def test_stale_evidence_creates_stale_violation(self) -> None:
        self._insert_audit_event(
            AuditEventEnvelope(
                organization_id="org_default",
                environment_id="env_default",
                event_type="agent.credential.rotated",
                source_component="agent-registry",
                actor_type="user",
                actor_id="user_admin",
                agent_id="agent_credential",
                resource_type="agent_credential",
                resource_id="cred_old",
                decision="allow",
                severity="info",
                payload_json={"reason": "historical rotation"},
                created_at="2020-01-01T00:00:00+00:00",
            )
        )

        recompute = self.client.post(
            "/api/v1/compliance/evidence/recompute",
            headers=self._headers(),
        )
        evidence = self.client.get(
            "/api/v1/compliance/evidence",
            headers=self._headers(),
            params={"status": "stale"},
        )
        violations = self.client.get(
            "/api/v1/compliance/violations",
            headers=self._headers(),
            params={"status": "open", "severity": "warning"},
        )

        self.assertEqual(recompute.status_code, 201, recompute.text)
        self.assertEqual(evidence.status_code, 200, evidence.text)
        self.assertEqual(1, len(evidence.json()))
        self.assertEqual("stale", evidence.json()[0]["status"])
        self.assertTrue(
            any("is stale" in violation["reason"] for violation in violations.json()),
            violations.text,
        )


if __name__ == "__main__":
    unittest.main()
