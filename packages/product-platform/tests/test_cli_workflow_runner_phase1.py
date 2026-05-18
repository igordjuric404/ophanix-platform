from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.workflows.catalog import WORKFLOW_CATALOG, seed_workflow_catalog
from product_platform.workflows.models import (
    WorkflowInputValidationError,
    validate_workflow_inputs,
)


class WorkflowCatalogPhase1Tests(unittest.TestCase):
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
                dev_login_allowed_emails=["workflows@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "workflows@example.com", "roles": ["Operator"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def test_workflow_seed_is_idempotent(self) -> None:
        with self.database.transaction() as connection:
            seed_workflow_catalog(connection, "org_default")
            seed_workflow_catalog(connection, "org_default")
            count = connection.execute(
                "SELECT COUNT(*) AS count FROM workflow_definitions WHERE organization_id = ?",
                ("org_default",),
            ).fetchone()["count"]

        self.assertEqual(count, len(WORKFLOW_CATALOG))

    def test_api_lists_expected_workflows(self) -> None:
        response = self.client.get("/api/v1/workflows", headers=self._headers())

        self.assertEqual(response.status_code, 200, response.text)
        workflows = response.json()
        workflow_ids = {workflow["id"] for workflow in workflows}
        self.assertEqual(len(workflows), len(WORKFLOW_CATALOG))
        self.assertIn("governance_verify", workflow_ids)
        self.assertIn("policy_lint", workflow_ids)
        self.assertIn("security_scan", workflow_ids)
        self.assertIn("sbom_generation", workflow_ids)
        self.assertIn("dependency_confusion", workflow_ids)
        self.assertIn("marketplace_evaluate", workflow_ids)
        policy_lint = next(workflow for workflow in workflows if workflow["id"] == "policy_lint")
        self.assertEqual(policy_lint["command_ref"], "python:policy.lint")
        self.assertIn("policy_body", policy_lint["input_schema"]["required"])

    def test_input_schema_validates_required_fields(self) -> None:
        schema = next(item["input_schema"] for item in WORKFLOW_CATALOG if item["id"] == "policy_lint")

        validate_workflow_inputs(schema, {"policy_body": "package rules"})
        with self.assertRaisesRegex(WorkflowInputValidationError, "policy_body"):
            validate_workflow_inputs(schema, {"policy_format": "yaml"})
        with self.assertRaisesRegex(WorkflowInputValidationError, "is not of type 'string'"):
            validate_workflow_inputs(schema, {"policy_body": {"rego": "package rules"}})
        with self.assertRaisesRegex(WorkflowInputValidationError, "Additional properties"):
            validate_workflow_inputs(
                schema,
                {"policy_body": "package rules", "unexpected": "value"},
            )


if __name__ == "__main__":
    unittest.main()
