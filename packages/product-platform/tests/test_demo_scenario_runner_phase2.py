from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.demo.catalog import CUSTOMER_SUPPORT_REFUND_SCENARIO
from product_platform.demo.models import DemoRunStatus, DemoStepRunStatus
from product_platform.demo.repository import DemoScenarioRepository, demo_run_response
from product_platform.demo.runner import DemoScenarioRunner, DemoStepExecutor


class DemoScenarioRunnerPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.connection = self.database.connect()
        self.repository = DemoScenarioRepository(
            self.connection,
            "org_default",
            "env_default",
        )
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["runner@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "runner@example.com", "roles": ["Operator"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self, correlation_id: str = "corr-demo-run") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": correlation_id,
        }

    def test_integration_run_creates_pending_step_runs(self) -> None:
        with self.database.transaction() as connection:
            repository = DemoScenarioRepository(connection, "org_default", "env_default")
            run = repository.create_run(
                CUSTOMER_SUPPORT_REFUND_SCENARIO["id"],
                started_by="user_admin",
            )

        payload = demo_run_response(self.repository, run)

        self.assertTrue(payload.id.startswith("demo_run_"))
        self.assertEqual(payload.status, DemoRunStatus.RUNNING)
        self.assertEqual(payload.summary["total_steps"], 9)
        self.assertEqual(len(payload.step_runs), 9)
        self.assertEqual(
            [step_run.status for step_run in payload.step_runs],
            [DemoStepRunStatus.PENDING] * 9,
        )
        self.assertEqual(payload.step_runs[0].step.action_type, "register_agents")
        self.assertEqual(payload.step_runs[-1].step.action_type, "generate_report")

    def test_integration_run_status_refresh_counts_completed_steps(self) -> None:
        with self.database.transaction() as connection:
            repository = DemoScenarioRepository(connection, "org_default", "env_default")
            run = repository.create_run(
                "customer-support-refund",
                started_by="user_admin",
            )
            next_step = repository.next_pending_step_run(run["id"])
            repository.mark_step_running(next_step["id"])
            repository.mark_step_succeeded(next_step["id"], {"ok": True})
            refreshed = repository.refresh_run_status(run["id"])

        payload = demo_run_response(self.repository, refreshed)

        self.assertEqual(payload.status, DemoRunStatus.RUNNING)
        self.assertEqual(payload.summary["completed_steps"], 1)
        self.assertEqual(payload.step_runs[0].status, DemoStepRunStatus.SUCCEEDED)
        self.assertEqual(payload.step_runs[0].result, {"ok": True})

    def test_unit_step_executor_dispatches_by_action_type(self) -> None:
        detail = self.repository.get_detail("customer-support-refund")
        self.assertIsNotNone(detail)
        executor = DemoStepExecutor()

        results = [
            executor.execute(step, run_id="demo_run_test", correlation_id="corr-demo")
            for step in detail.steps
        ]

        self.assertEqual(
            [result["action_type"] for result in results],
            [
                "register_agents",
                "import_policies",
                "register_mcp_server",
                "run_agent_prompt",
                "request_approval",
                "rotate_credential",
                "run_discovery",
                "run_saga",
                "generate_report",
            ],
        )
        self.assertEqual(results[0]["resource_ids"]["agent_ids"][0], "agent_demo_support")
        self.assertEqual(results[2]["resource_ids"]["mcp_server_id"], "mcp_demo_refund")
        self.assertEqual(results[-1]["correlation_id"], "corr-demo")

    def test_integration_failed_step_marks_run_failed(self) -> None:
        with self.database.transaction() as connection:
            repository = DemoScenarioRepository(connection, "org_default", "env_default")
            run = repository.create_run(
                "customer-support-refund",
                started_by="user_admin",
            )
            failed = DemoScenarioRunner(
                repository,
                executor=DemoStepExecutor(failure_action_types={"register_agents"}),
            ).continue_run(run["id"], correlation_id="corr-fail")

        payload = demo_run_response(self.repository, failed)

        self.assertEqual(payload.status, DemoRunStatus.FAILED)
        self.assertEqual(payload.summary["failed_steps"], 1)
        self.assertEqual(payload.step_runs[0].status, DemoStepRunStatus.FAILED)
        self.assertIn("Configured demo failure", payload.step_runs[0].result["error"])

    def test_integration_runner_completes_all_steps(self) -> None:
        with self.database.transaction() as connection:
            repository = DemoScenarioRepository(connection, "org_default", "env_default")
            run = repository.create_run(
                "customer-support-refund",
                started_by="user_admin",
            )
            runner = DemoScenarioRunner(repository)
            for _ in CUSTOMER_SUPPORT_REFUND_SCENARIO["steps"]:
                run = runner.continue_run(run["id"], correlation_id="corr-complete")

        payload = demo_run_response(self.repository, run)

        self.assertEqual(payload.status, DemoRunStatus.SUCCEEDED)
        self.assertEqual(payload.summary["completed_steps"], 9)
        self.assertEqual(
            {step_run.status for step_run in payload.step_runs},
            {DemoStepRunStatus.SUCCEEDED},
        )

    def test_api_start_get_continue_and_cancel_run(self) -> None:
        started = self.client.post(
            "/api/v1/demo/scenarios/customer-support-refund/runs",
            headers=self._headers("corr-api-flow"),
        )
        self.assertEqual(started.status_code, 201, started.text)
        run_id = started.json()["id"]

        loaded = self.client.get(f"/api/v1/demo/runs/{run_id}", headers=self._headers("corr-api-flow"))
        continued = self.client.post(
            f"/api/v1/demo/runs/{run_id}/continue",
            headers=self._headers("corr-api-flow"),
        )
        canceled = self.client.post(
            f"/api/v1/demo/runs/{run_id}/cancel",
            headers=self._headers("corr-api-flow"),
        )

        self.assertEqual(loaded.status_code, 200, loaded.text)
        self.assertEqual(continued.status_code, 200, continued.text)
        self.assertEqual(canceled.status_code, 200, canceled.text)
        self.assertEqual(continued.json()["step_runs"][0]["status"], DemoStepRunStatus.SUCCEEDED)
        self.assertEqual(
            continued.json()["step_runs"][0]["result"]["correlation_id"],
            "corr-api-flow",
        )
        self.assertEqual(canceled.json()["status"], DemoRunStatus.CANCELED)

    def test_integration_run_emits_audit_events(self) -> None:
        started = self.client.post(
            "/api/v1/demo/scenarios/customer-support-refund/runs",
            headers=self._headers("corr-audit-run"),
        )
        self.assertEqual(started.status_code, 201, started.text)
        run_id = started.json()["id"]
        latest = started.json()
        for _ in CUSTOMER_SUPPORT_REFUND_SCENARIO["steps"]:
            response = self.client.post(
                f"/api/v1/demo/runs/{run_id}/continue",
                headers=self._headers("corr-audit-run"),
            )
            self.assertEqual(response.status_code, 200, response.text)
            latest = response.json()

        self.assertEqual(latest["status"], DemoRunStatus.SUCCEEDED)
        audit = AuditEventRepository(self.database.connect())
        run_events = audit.query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="demo_run",
                resource_id=run_id,
                correlation_id="corr-audit-run",
                limit=20,
            )
        )
        step_events = audit.query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="demo_step_run",
                correlation_id="corr-audit-run",
                limit=20,
            )
        )

        self.assertIn("demo.run.started", {event.event_type for event in run_events})
        self.assertIn("demo.run.completed", {event.event_type for event in run_events})
        self.assertEqual(
            sum(1 for event in step_events if event.event_type == "demo.step.completed"),
            9,
        )


if __name__ == "__main__":
    unittest.main()
