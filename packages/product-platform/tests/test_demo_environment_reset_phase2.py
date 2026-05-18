from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.auth import AuthService, DevLoginRequest
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.api.settings import Settings
from product_platform.db.seed import DEMO_ADMIN_USER_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.demo.catalog import CUSTOMER_SUPPORT_REFUND_SCENARIO
from product_platform.demo.models import DemoResetStatus
from product_platform.demo.repository import DemoScenarioRepository
from product_platform.demo.reset import (
    DemoEnvironmentResetService,
    DemoResetRepository,
    demo_reset_run_response,
    query_demo_markers,
)
from product_platform.demo.runner import demo_run_audit_event


class DemoEnvironmentResetPhase2Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["reset@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "reset@example.com", "roles": ["Operator"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self, correlation_id: str = "corr-reset-api") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": correlation_id,
        }

    def test_integration_reset_preserves_demo_audit_events_and_admin(self) -> None:
        with self.database.transaction() as connection:
            scenario_repository = DemoScenarioRepository(
                connection,
                "org_default",
                "env_default",
            )
            run = scenario_repository.create_run(
                CUSTOMER_SUPPORT_REFUND_SCENARIO["id"],
                started_by=DEMO_ADMIN_USER_ID,
            )
            AuditEventRepository(connection).insert(
                demo_run_audit_event(
                    event_type="demo.run.started",
                    organization_id="org_default",
                    environment_id="env_default",
                    actor_id=DEMO_ADMIN_USER_ID,
                    run_id=run["id"],
                    scenario_id=run["scenario_id"],
                    status=run["status"],
                    summary_json=run["summary_json"],
                    correlation_id="corr-reset-service",
                )
            )

            reset = DemoEnvironmentResetService(
                connection,
                "org_default",
                "env_default",
            ).reset(
                requested_by=DEMO_ADMIN_USER_ID,
                correlation_id="corr-reset-service",
            )
            response = demo_reset_run_response(reset)

        connection = self.database.connect()
        counts = query_demo_markers(
            connection,
            organization_id="org_default",
            environment_id="env_default",
        )
        admin_count = connection.execute(
            "SELECT COUNT(*) AS count FROM users WHERE id = ?",
            (DEMO_ADMIN_USER_ID,),
        ).fetchone()["count"]
        old_demo_events = AuditEventRepository(connection).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                event_type="demo.run.started",
            )
        )
        reset_events = AuditEventRepository(connection).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                event_type="demo.reset.completed",
                resource_id=response.id,
            )
        )

        self.assertEqual(response.status, DemoResetStatus.SUCCEEDED)
        self.assertEqual(response.summary["cleared"]["demo_runs"], 1)
        self.assertEqual(
            response.summary["cleared"]["demo_step_runs"],
            len(CUSTOMER_SUPPORT_REFUND_SCENARIO["steps"]),
        )
        self.assertEqual(counts, {"demo_runs": 0, "demo_step_runs": 0})
        self.assertEqual(admin_count, 1)
        self.assertEqual(response.summary["cleared"]["demo_lab_audit_events"], 0)
        self.assertEqual(len(old_demo_events), 1)
        self.assertEqual(len(reset_events), 1)
        self.assertTrue(AuditEventRepository(connection).verify_range("org_default").valid)

    def test_integration_reset_reloads_seed_scenario_and_policies(self) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                "DELETE FROM demo_steps WHERE scenario_id = ?",
                (CUSTOMER_SUPPORT_REFUND_SCENARIO["id"],),
            )
            connection.execute(
                """
                DELETE FROM demo_scenarios
                WHERE organization_id = ? AND environment_id = ?
                """,
                ("org_default", "env_default"),
            )
            connection.execute(
                """
                DELETE FROM policy_placeholders
                WHERE organization_id = ? AND environment_id = ?
                """,
                ("org_default", "env_default"),
            )

            reset = DemoEnvironmentResetService(
                connection,
                "org_default",
                "env_default",
            ).reset(requested_by=DEMO_ADMIN_USER_ID)
            response = demo_reset_run_response(reset)

        self.assertEqual(response.status, DemoResetStatus.SUCCEEDED)
        self.assertEqual(response.summary["seeded"]["demo_scenarios"], 1)
        self.assertEqual(
            response.summary["seeded"]["demo_steps"],
            len(CUSTOMER_SUPPORT_REFUND_SCENARIO["steps"]),
        )
        self.assertEqual(response.summary["seeded"]["policy_placeholders"], 2)

    def test_integration_reset_is_idempotent(self) -> None:
        with self.database.transaction() as connection:
            service = DemoEnvironmentResetService(connection, "org_default", "env_default")
            first = demo_reset_run_response(
                service.reset(requested_by=DEMO_ADMIN_USER_ID)
            )
            second = demo_reset_run_response(
                service.reset(requested_by=DEMO_ADMIN_USER_ID)
            )
            runs = DemoResetRepository(
                connection,
                "org_default",
                "env_default",
            ).list_runs(limit=10)

        connection = self.database.connect()
        reset_events = AuditEventRepository(connection).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                event_type="demo.reset.completed",
            )
        )
        counts = query_demo_markers(
            connection,
            organization_id="org_default",
            environment_id="env_default",
        )

        self.assertEqual(first.status, DemoResetStatus.SUCCEEDED)
        self.assertEqual(second.status, DemoResetStatus.SUCCEEDED)
        self.assertEqual(second.summary["cleared"]["demo_runs"], 0)
        self.assertEqual(second.summary["cleared"]["demo_step_runs"], 0)
        self.assertEqual(second.summary["cleared"]["demo_lab_audit_events"], 0)
        self.assertEqual(len(runs), 2)
        self.assertEqual(len(reset_events), 2)
        self.assertEqual(counts, {"demo_runs": 0, "demo_step_runs": 0})

    def test_api_reset_failure_rolls_back_clears_and_records_failed_run(self) -> None:
        started = self.client.post(
            "/api/v1/demo/scenarios/customer-support-refund/runs",
            headers=self._headers("corr-reset-api-failure"),
        )
        self.assertEqual(started.status_code, 201, started.text)

        with patch(
            "product_platform.demo.reset.seed_demo_data",
            side_effect=RuntimeError("seed failed"),
        ):
            reset = self.client.post(
                "/api/v1/demo/reset",
                headers=self._headers("corr-reset-api-failure"),
                json={"confirmation": "RESET"},
            )

        connection = self.database.connect()
        counts = query_demo_markers(
            connection,
            organization_id="org_default",
            environment_id="env_default",
        )
        failed_runs = DemoResetRepository(
            connection,
            "org_default",
            "env_default",
        ).list_runs(limit=10)
        failed_events = AuditEventRepository(connection).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                event_type="demo.reset.failed",
            )
        )

        self.assertEqual(reset.status_code, 500, reset.text)
        self.assertEqual(counts["demo_runs"], 1)
        self.assertEqual(counts["demo_step_runs"], len(CUSTOMER_SUPPORT_REFUND_SCENARIO["steps"]))
        self.assertEqual(len(failed_runs), 1)
        self.assertEqual(failed_runs[0]["status"], DemoResetStatus.FAILED)
        self.assertEqual(len(failed_events), 1)
        self.assertTrue(AuditEventRepository(connection).verify_range("org_default").valid)

    def test_api_reset_requires_typed_confirmation(self) -> None:
        response = self.client.post(
            "/api/v1/demo/reset",
            headers=self._headers(),
            json={"confirmation": "reset"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Type RESET", response.text)

    def test_api_reset_and_fetch_history(self) -> None:
        started = self.client.post(
            "/api/v1/demo/scenarios/customer-support-refund/runs",
            headers=self._headers("corr-reset-api-flow"),
        )
        self.assertEqual(started.status_code, 201, started.text)

        reset = self.client.post(
            "/api/v1/demo/reset",
            headers=self._headers("corr-reset-api-flow"),
            json={"confirmation": "RESET"},
        )
        self.assertEqual(reset.status_code, 201, reset.text)
        reset_payload = reset.json()

        listed = self.client.get(
            "/api/v1/demo/reset-runs",
            headers=self._headers("corr-reset-api-flow"),
        )
        fetched = self.client.get(
            f"/api/v1/demo/reset-runs/{reset_payload['id']}",
            headers=self._headers("corr-reset-api-flow"),
        )

        self.assertEqual(reset_payload["status"], DemoResetStatus.SUCCEEDED)
        self.assertEqual(reset_payload["summary"]["cleared"]["demo_runs"], 1)
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(fetched.status_code, 200, fetched.text)
        self.assertEqual(listed.json()[0]["id"], reset_payload["id"])
        self.assertEqual(fetched.json()["id"], reset_payload["id"])

    def test_api_reset_is_not_available_outside_local_environments(self) -> None:
        settings = Settings(
            app_name="Ophanix Test Platform",
            environment="staging",
            build_sha="test-sha",
            build_time="2026-05-01T00:00:00Z",
            database_url=self.database.database_url,
            dev_login_allowed_emails=["reset@example.com"],
            enable_dev_login=False,
            session_secret="staging-secret",
            gateway_token_hash_pepper="test-pepper",
            tool_gateway_upstream_host_allowlist=["api.example.com"],
        )
        token = AuthService(settings).login(
            DevLoginRequest(email="reset@example.com", roles=["Operator"])
        ).access_token
        app = create_app(settings, database=self.database)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/v1/demo/reset",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Environment-ID": "env_default",
            },
            json={"confirmation": "RESET"},
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
