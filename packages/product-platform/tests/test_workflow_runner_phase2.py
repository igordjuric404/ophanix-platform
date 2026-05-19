from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.workflows.repository import WorkflowRepository
from product_platform.workflows.runner import WorkflowRunResult


VALID_POLICY = """version: "1.0"
name: workflow-lint-valid
rules:
  - name: block_shell
    condition:
      field: tool_name
      operator: eq
      value: run_shell
    action: deny
"""


class WorkflowRunnerPhase2ApiTests(unittest.TestCase):
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
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "X-Environment-ID": "env_default"}

    def test_policy_lint_run_stores_ordered_logs_and_audit_events(self) -> None:
        response = self.client.post(
            "/api/v1/workflows/policy_lint/runs",
            headers=self._headers(),
            json={
                "inputs": {"policy_body": VALID_POLICY, "policy_format": "yaml"},
                "run_immediately": True,
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        run = response.json()
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["exit_code"], 0)
        self.assertTrue(run["summary"]["passed"])
        self.assertEqual([log["line_number"] for log in run["logs"]], [1])
        self.assertIn("policy lint passed=True", run["logs"][0]["message"])
        detail = self.client.get(f"/api/v1/workflow-runs/{run['id']}", headers=self._headers())
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["logs"][0]["message"], run["logs"][0]["message"])
        with self.database.connect() as connection:
            events = AuditEventRepository(connection).query(
                AuditEventQuery(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="workflow.run",
                    resource_id=run["id"],
                    limit=10,
                )
            )
        self.assertEqual(
            ["succeeded", "running", "queued"],
            [event.payload_json["status"] for event in events],
        )

    def test_failed_workflow_stores_nonzero_exit_code_and_summary(self) -> None:
        response = self.client.post(
            "/api/v1/workflows/policy_lint/runs",
            headers=self._headers(),
            json={
                "inputs": {
                    "policy_body": 'version: "1.0"\nname: missing-rules\n',
                    "policy_format": "yaml",
                },
                "run_immediately": True,
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        run = response.json()
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["exit_code"], 1)
        self.assertFalse(run["summary"]["passed"])
        self.assertGreater(run["summary"]["error_count"], 0)
        self.assertTrue(any("schema.missing_required_field" in log["message"] for log in run["logs"]))

    def test_cancel_queued_run_and_reject_completed_run(self) -> None:
        queued = self.client.post(
            "/api/v1/workflows/policy_lint/runs",
            headers=self._headers(),
            json={
                "inputs": {"policy_body": VALID_POLICY, "policy_format": "yaml"},
                "run_immediately": False,
            },
        )
        completed = self.client.post(
            "/api/v1/workflows/policy_lint/runs",
            headers=self._headers(),
            json={
                "inputs": {"policy_body": VALID_POLICY, "policy_format": "yaml"},
                "run_immediately": True,
            },
        )

        canceled = self.client.post(
            f"/api/v1/workflow-runs/{queued.json()['id']}/cancel",
            headers=self._headers(),
        )
        rejected = self.client.post(
            f"/api/v1/workflow-runs/{completed.json()['id']}/cancel",
            headers=self._headers(),
        )

        self.assertEqual(queued.status_code, 201, queued.text)
        self.assertEqual(completed.status_code, 201, completed.text)
        self.assertEqual(canceled.status_code, 200, canceled.text)
        self.assertEqual(canceled.json()["status"], "canceled")
        self.assertEqual(rejected.status_code, 409, rejected.text)

    def test_worker_completion_cannot_overwrite_canceled_run(self) -> None:
        queued = self.client.post(
            "/api/v1/workflows/policy_lint/runs",
            headers=self._headers(),
            json={
                "inputs": {"policy_body": VALID_POLICY, "policy_format": "yaml"},
                "run_immediately": False,
            },
        )
        self.assertEqual(queued.status_code, 201, queued.text)
        run_id = queued.json()["id"]

        with self.database.transaction() as connection:
            repository = WorkflowRepository(connection, "org_default")
            started = repository.start_run(run_id, environment_id="env_default")
            self.assertEqual(started["status"], "running")
            canceled = repository.cancel_run(run_id, environment_id="env_default")
            self.assertEqual(canceled["status"], "canceled")

            with self.assertRaisesRegex(RuntimeError, "not running"):
                repository.complete_run(
                    run_id,
                    environment_id="env_default",
                    result=WorkflowRunResult(
                        status="succeeded",
                        exit_code=0,
                        summary={"ok": True},
                        logs=[],
                    ),
                )

            current = repository.get_run(run_id, environment_id="env_default")
            self.assertIsNotNone(current)
            self.assertEqual(current["status"], "canceled")

    def test_missing_required_input_returns_400(self) -> None:
        response = self.client.post(
            "/api/v1/workflows/policy_lint/runs",
            headers=self._headers(),
            json={"inputs": {"policy_format": "yaml"}, "run_immediately": True},
        )

        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("policy_body", response.json()["message"])


if __name__ == "__main__":
    unittest.main()
