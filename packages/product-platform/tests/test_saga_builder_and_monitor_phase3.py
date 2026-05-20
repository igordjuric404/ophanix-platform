from __future__ import annotations

import json
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.runtime.sagas import SagaRepository


class SagaBuilderPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_claims", "Claims Agent")
            self._insert_capability(connection, "agent_claims", "claims.lookup")
            self._insert_capability(connection, "agent_claims", "claims.refund")
            self._insert_capability(connection, "agent_claims", "notifications.email")
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["operator@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "operator@example.com", "roles": ["Operator"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": "corr-saga-api",
        }

    def _insert_agent(self, connection, agent_id: str, name: str) -> None:
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
                "Saga test agent",
                "langgraph",
                "service",
                "user_admin",
                "user_admin",
                "active",
                850,
                "trusted",
                now,
                now,
            ),
        )

    def _insert_capability(self, connection, agent_id: str, capability: str) -> None:
        now = "2026-05-01T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agent_capabilities (
                id, agent_id, capability_name, resource_type, status,
                requested_by, approved_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"cap_{agent_id}_{capability.replace('.', '_')}",
                agent_id,
                capability,
                "runtime-action",
                "approved",
                "user_admin",
                "user_admin",
                now,
            ),
        )

    def _create_saga(self, name: str = "Refund Saga") -> dict:
        created = self.client.post(
            "/api/v1/runtime/sagas",
            headers=self._headers(),
            json={"name": name, "correlation_id": "order-demo-001"},
        )
        self.assertEqual(created.status_code, 201, created.text)
        return created.json()

    def _add_step(
        self,
        saga_id: str,
        *,
        step_order: int,
        name: str,
        action_name: str,
        required_capability: str,
        compensation_action: str | None = None,
    ) -> dict:
        added = self.client.post(
            f"/api/v1/runtime/sagas/{saga_id}/steps",
            headers=self._headers(),
            json={
                "step_order": step_order,
                "name": name,
                "action_name": action_name,
                "target_agent_id": "agent_claims",
                "required_capability": required_capability,
                "compensation_action": compensation_action,
            },
        )
        self.assertEqual(added.status_code, 201, added.text)
        return added.json()

    def _build_refund_saga(self) -> dict:
        saga = self._create_saga()
        self._add_step(
            saga["id"],
            step_order=1,
            name="Lookup order",
            action_name="claims.lookup_order",
            required_capability="claims.lookup",
            compensation_action="claims.release_lookup_hold",
        )
        self._add_step(
            saga["id"],
            step_order=2,
            name="Issue refund",
            action_name="claims.issue_refund",
            required_capability="claims.refund",
            compensation_action="claims.reverse_refund",
        )
        self._add_step(
            saga["id"],
            step_order=3,
            name="Send email",
            action_name="notifications.send_email",
            required_capability="notifications.email",
        )
        return saga

    def _audit_events(self) -> list:
        with self.database.connect() as connection:
            return connection.execute(
                """
                SELECT event_type, decision, resource_type, resource_id, payload_json
                FROM audit_events
                WHERE organization_id = 'org_default'
                  AND environment_id = 'env_default'
                ORDER BY created_at ASC, id ASC
                """
            ).fetchall()

    def test_execute_simple_saga_creates_runtime_session_and_audit(self) -> None:
        saga = self._build_refund_saga()

        executed = self.client.post(
            f"/api/v1/runtime/sagas/{saga['id']}/execute",
            headers=self._headers(),
            json={},
        )

        self.assertEqual(executed.status_code, 200, executed.text)
        payload = executed.json()
        self.assertEqual(payload["status"], "completed")
        self.assertIsNotNone(payload["runtime_session_id"])
        self.assertEqual(payload["saga"]["status"], "completed")
        self.assertEqual([step["status"] for step in payload["saga"]["steps"]], ["committed"] * 3)

        with self.database.connect() as connection:
            sessions = connection.execute("SELECT * FROM runtime_sessions").fetchall()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["state"], "archived")
        self.assertIsNotNone(sessions[0]["ended_at"])

        event_types = [row["event_type"] for row in self._audit_events()]
        self.assertIn("runtime.session.started", event_types)
        self.assertIn("runtime.session.ended", event_types)
        self.assertIn("saga.started", event_types)
        self.assertIn("saga.step.committed", event_types)
        self.assertIn("saga.completed", event_types)
        self.assertIn("runtime.action", event_types)
        self.assertLess(event_types.index("saga.started"), event_types.index("runtime.action"))

    def test_saga_step_executes_through_worker_activity(self) -> None:
        """Selected audit regression: saga steps execute through persistent worker jobs."""

        saga = self._build_refund_saga()

        executed = self.client.post(
            f"/api/v1/runtime/sagas/{saga['id']}/execute",
            headers=self._headers(),
            json={},
        )

        self.assertEqual(executed.status_code, 200, executed.text)
        with self.database.connect() as connection:
            jobs = connection.execute(
                """
                SELECT id, job_type, status, attempts, payload_json
                FROM background_jobs
                WHERE job_type = 'saga.activity'
                ORDER BY created_at ASC, id ASC
                """
            ).fetchall()
            job_runs = connection.execute(
                """
                SELECT jr.job_id, jr.status, jr.result_json
                FROM job_runs jr
                JOIN background_jobs bj ON bj.id = jr.job_id
                WHERE bj.job_type = 'saga.activity'
                ORDER BY jr.created_at ASC, jr.id ASC
                """
            ).fetchall()
            activity_results = connection.execute(
                """
                SELECT worker_job_id, idempotency_key, external_operation_id, result_json
                FROM saga_activity_results
                WHERE saga_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (saga["id"],),
            ).fetchall()
            run_steps = connection.execute(
                """
                SELECT metadata_json
                FROM runtime_run_steps
                WHERE saga_id = ?
                ORDER BY step_order ASC, id ASC
                """,
                (saga["id"],),
            ).fetchall()

        self.assertEqual(len(jobs), 3)
        self.assertEqual({job["status"] for job in jobs}, {"succeeded"})
        self.assertEqual({job["attempts"] for job in jobs}, {1})
        self.assertEqual(len(job_runs), 3)
        self.assertEqual({run["status"] for run in job_runs}, {"succeeded"})
        self.assertEqual(
            {row["worker_job_id"] for row in activity_results},
            {job["id"] for job in jobs},
        )
        for row in activity_results:
            result = json.loads(row["result_json"])
            self.assertTrue(result["worker"])
            self.assertEqual(result["worker_job_id"], row["worker_job_id"])
            self.assertEqual(result["idempotency_key"], row["idempotency_key"])
            self.assertEqual(result["external_operation_id"], row["external_operation_id"])
        self.assertEqual(len(run_steps), 3)
        run_step_metadata = [json.loads(row["metadata_json"]) for row in run_steps]
        self.assertEqual(
            {item["worker_job_id"] for item in run_step_metadata},
            {job["id"] for job in jobs},
        )
        runtime_action_audits = [
            json.loads(row["payload_json"])
            for row in self._audit_events()
            if row["event_type"] == "runtime.action" and row["decision"] == "allow"
        ]
        worker_payloads = [
            payload for payload in runtime_action_audits
            if payload.get("saga_id") == saga["id"] and payload.get("worker_job_id")
        ]
        self.assertEqual(len(worker_payloads), 3)
        self.assertEqual(
            {payload["worker_job_id"] for payload in worker_payloads},
            {job["id"] for job in jobs},
        )
        self.assertTrue(all(payload["idempotency_key"].startswith("saga:") for payload in worker_payloads))
        self.assertTrue(
            all(payload["external_operation_id"].startswith("saga-op-") for payload in worker_payloads)
        )

    def test_completed_saga_cannot_be_reexecuted(self) -> None:
        saga = self._build_refund_saga()
        executed = self.client.post(
            f"/api/v1/runtime/sagas/{saga['id']}/execute",
            headers=self._headers(),
            json={},
        )
        self.assertEqual(executed.status_code, 200, executed.text)

        replayed = self.client.post(
            f"/api/v1/runtime/sagas/{saga['id']}/execute",
            headers=self._headers(),
            json={},
        )

        self.assertEqual(replayed.status_code, 400, replayed.text)
        self.assertIn("completed", replayed.json()["message"])

    def test_running_saga_recovers_replayed_activity_and_audits_recovery(self) -> None:
        saga = self._build_refund_saga()
        with self.database.transaction() as connection:
            repository = SagaRepository(connection, "org_default", "env_default")
            steps = repository.list_steps(saga["id"])
            first_step = steps[0]
            repository.update_saga_status(
                saga["id"],
                "running",
                mark_started=True,
                expected_statuses={"draft"},
            )
            repository.update_step_status(
                first_step["id"],
                "executing",
                result={"action_name": first_step["action_name"]},
            )
            durable_result = {
                "action_name": first_step["action_name"],
                "mode": "execute",
                "saga_id": saga["id"],
                "step_id": first_step["id"],
                "correlation_id": "order-demo-001",
                "target_agent_id": "agent_claims",
                "demo_safe": True,
            }
            repository.complete_activity_result(
                saga_id=saga["id"],
                step_id=first_step["id"],
                mode="execute",
                action_name=first_step["action_name"],
                result=durable_result,
            )
            repository.create_checkpoint(
                saga_id=saga["id"],
                step_id=first_step["id"],
                mode="execute",
                payload={
                    "result": durable_result,
                    "side_effect_boundary": "after_activity_before_step_commit",
                },
                policy_snapshot={"required_capability": first_step["required_capability"]},
                tool_calls=[{"action_name": first_step["action_name"], "mode": "execute"}],
            )

        recovered = self.client.post(
            f"/api/v1/runtime/sagas/{saga['id']}/execute",
            headers=self._headers(),
            json={},
        )

        self.assertEqual(recovered.status_code, 200, recovered.text)
        payload = recovered.json()
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["replayed_step_ids"], [first_step["id"]])
        self.assertEqual([step["status"] for step in payload["saga"]["steps"]], ["committed"] * 3)
        saga_event_types = [event["event_type"] for event in payload["saga"]["events"]]
        self.assertIn("saga.recovered", saga_event_types)
        self.assertIn("saga.activity.replayed", saga_event_types)
        self.assertIn("saga.checkpoint.restored", saga_event_types)
        self.assertIn("saga.checkpoint.created", saga_event_types)

        audit_rows = self._audit_events()
        event_types = [row["event_type"] for row in audit_rows]
        self.assertIn("saga.recovered", event_types)
        self.assertIn("saga.activity.replayed", event_types)
        self.assertIn("saga.checkpoint.restored", event_types)
        self.assertIn("saga.checkpoint.created", event_types)
        recovered_audit = next(row for row in audit_rows if row["event_type"] == "saga.recovered")
        replayed_audit = next(row for row in audit_rows if row["event_type"] == "saga.activity.replayed")
        checkpoint_audit = next(row for row in audit_rows if row["event_type"] == "saga.checkpoint.restored")
        self.assertEqual(recovered_audit["decision"], "allow")
        self.assertEqual(replayed_audit["decision"], "allow")
        self.assertEqual(checkpoint_audit["decision"], "allow")
        self.assertEqual(json.loads(replayed_audit["payload_json"])["step_id"], first_step["id"])
        self.assertTrue(
            json.loads(checkpoint_audit["payload_json"])["payload_hash"].startswith("sha256:")
        )

    def test_execute_with_caller_supplied_runtime_session_leaves_session_active(self) -> None:
        saga = self._build_refund_saga()
        session = self.client.post(
            "/api/v1/runtime/sessions",
            headers=self._headers(),
            json={"agent_id": "agent_claims", "ring": 2, "sponsor_user_id": "user_admin"},
        )
        self.assertEqual(session.status_code, 201, session.text)

        executed = self.client.post(
            f"/api/v1/runtime/sagas/{saga['id']}/execute",
            headers=self._headers(),
            json={"runtime_session_id": session.json()["id"]},
        )

        self.assertEqual(executed.status_code, 200, executed.text)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT state FROM runtime_sessions WHERE id = ?",
                (session.json()["id"],),
            ).fetchone()
        self.assertEqual(row["state"], "active")

    def test_unknown_saga_action_is_rejected_at_step_creation(self) -> None:
        saga = self._create_saga()

        added = self.client.post(
            f"/api/v1/runtime/sagas/{saga['id']}/steps",
            headers=self._headers(),
            json={
                "step_order": 1,
                "name": "Unknown action",
                "action_name": "claims.transfer_cash",
                "target_agent_id": "agent_claims",
                "required_capability": "claims.lookup",
            },
        )

        self.assertEqual(added.status_code, 400, added.text)
        self.assertIn("supported saga actions", added.json()["message"])

    def test_failed_step_emits_compensation_and_runtime_audit(self) -> None:
        saga = self._build_refund_saga()

        executed = self.client.post(
            f"/api/v1/runtime/sagas/{saga['id']}/execute",
            headers=self._headers(),
            json={"failure_actions": ["notifications.send_email"]},
        )

        self.assertEqual(executed.status_code, 200, executed.text)
        payload = executed.json()
        self.assertEqual(payload["status"], "compensated")
        self.assertEqual([step["status"] for step in payload["saga"]["steps"]], ["compensated", "compensated", "failed"])
        saga_event_types = {event["event_type"] for event in payload["saga"]["events"]}
        self.assertIn("saga.step.failed", saga_event_types)
        self.assertIn("saga.step.compensated", saga_event_types)
        self.assertIn("saga.compensated", saga_event_types)

        audit_rows = self._audit_events()
        event_types = [row["event_type"] for row in audit_rows]
        self.assertIn("saga.step.failed", event_types)
        self.assertIn("saga.step.compensated", event_types)
        self.assertIn("saga.compensated", event_types)
        denied_runtime_actions = [
            row for row in audit_rows
            if row["event_type"] == "runtime.action" and row["decision"] == "deny"
        ]
        self.assertEqual(len(denied_runtime_actions), 1)
        denied_payload = json.loads(denied_runtime_actions[0]["payload_json"])
        self.assertEqual(denied_payload["action"], "notifications.send_email")
        self.assertEqual(denied_payload["status"], "failed")
        with self.database.connect() as connection:
            session = connection.execute("SELECT * FROM runtime_sessions").fetchone()
        self.assertEqual(session["state"], "archived")

    def test_completed_saga_has_final_status_on_detail(self) -> None:
        saga = self._build_refund_saga()

        executed = self.client.post(
            f"/api/v1/runtime/sagas/{saga['id']}/execute",
            headers=self._headers(),
            json={},
        )
        self.assertEqual(executed.status_code, 200, executed.text)

        detail = self.client.get(f"/api/v1/runtime/sagas/{saga['id']}", headers=self._headers())
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["status"], "completed")
        self.assertIsNotNone(detail.json()["started_at"])
        self.assertIsNotNone(detail.json()["finished_at"])

    def test_cancel_non_terminal_saga(self) -> None:
        saga = self._create_saga("Cancel me")

        cancelled = self.client.post(
            f"/api/v1/runtime/sagas/{saga['id']}/cancel",
            headers=self._headers(),
            json={"reason": "operator cancelled"},
        )

        self.assertEqual(cancelled.status_code, 200, cancelled.text)
        self.assertEqual(cancelled.json()["status"], "cancelled")
        self.assertIn("saga.cancelled", {event["event_type"] for event in cancelled.json()["events"]})
        self.assertIn("saga.cancelled", [row["event_type"] for row in self._audit_events()])


if __name__ == "__main__":
    unittest.main()
