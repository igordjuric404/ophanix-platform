from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.workflows.runner import build_default_workflow_runner_registry

try:
    from product_platform.workflows.worker import WorkflowRunWorker
except ImportError:  # pragma: no cover - exercised by the initial red test state.
    WorkflowRunWorker = None


VALID_POLICY_BODY = """version: "1.0"
name: workflow-second-pass-valid
rules: []
defaults:
  action: allow
"""


class WorkflowRunnerSecondPassTests(unittest.TestCase):
    def setUp(self) -> None:
        self.artifact_root = tempfile.TemporaryDirectory()
        self.addCleanup(self.artifact_root.cleanup)
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["workflow-second-pass@example.com"],
                session_secret="test-secret",
                artifact_storage_path=self.artifact_root.name,
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "workflow-second-pass@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def test_queued_workflow_run_is_executed_by_worker_job_and_emits_artifact(self) -> None:
        created = self.client.post(
            "/api/v1/workflows/policy_lint/runs",
            headers=self._headers(),
            json={
                "run_immediately": False,
                "inputs": {"policy_body": VALID_POLICY_BODY, "policy_format": "yaml"},
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        run = created.json()
        self.assertEqual(run["status"], "queued")
        self.assertEqual(run["logs"], [])

        job = self.client.get(f"/api/v1/jobs/{run['id']}", headers=self._headers())
        self.assertEqual(job.status_code, 200, job.text)
        self.assertEqual(job.json()["status"], "queued")
        self.assertEqual(job.json()["job_type"], "workflow.run")
        self.assertIsNotNone(WorkflowRunWorker)

        execution = WorkflowRunWorker(self.database).run_once()
        self.assertIsNotNone(execution)
        self.assertEqual(execution.workflow_run_id, run["id"])
        self.assertEqual(execution.status, "succeeded")

        completed = self.client.get(f"/api/v1/workflow-runs/{run['id']}", headers=self._headers())
        self.assertEqual(completed.status_code, 200, completed.text)
        self.assertEqual(completed.json()["status"], "succeeded")
        self.assertGreater(len(completed.json()["logs"]), 0)
        job_after = self.client.get(f"/api/v1/jobs/{run['id']}", headers=self._headers())
        self.assertEqual(job_after.json()["status"], "succeeded")

        artifacts = self.client.get(
            "/api/v1/artifacts",
            headers=self._headers(),
            params={"artifact_type": "workflow.output"},
        )
        self.assertEqual(artifacts.status_code, 200, artifacts.text)
        linked = [
            artifact
            for artifact in artifacts.json()
            if any(
                link["target_type"] == "workflow_run" and link["target_id"] == run["id"]
                for link in artifact["links"]
            )
        ]
        self.assertEqual(len(linked), 1)

    def test_seeded_non_policy_workflow_adapters_are_not_placeholders(self) -> None:
        registry = build_default_workflow_runner_registry(repo_root=Path(__file__).resolve().parents[1])

        governance = registry.run("python:governance.verify", {"scope": "controls"})
        self.assertEqual(governance.status, "failed")
        self.assertEqual(governance.summary["error"], "missing_evidence_ref")

        integrity = registry.run("python:integrity.check", {"target": "missing-target.txt"})
        self.assertEqual(integrity.status, "failed")
        self.assertEqual(integrity.summary["error"], "target_not_found")

        marketplace = registry.run("python:marketplace.evaluate", {"plugin_id": "unknown-plugin"})
        self.assertEqual(marketplace.status, "failed")
        self.assertEqual(marketplace.summary["error"], "plugin_not_found")

        security = registry.run("shell:security.scan", {"target_path": "src/product_platform/workflows/catalog.py"})
        self.assertEqual(security.status, "succeeded")
        self.assertIn("target_path", security.summary)
        self.assertNotEqual(security.logs[0].message, "security scan completed")

        sbom = registry.run("shell:sbom.generate", {"target_path": "src/product_platform/workflows"})
        self.assertEqual(sbom.status, "succeeded")
        self.assertGreaterEqual(sbom.summary["component_count"], 1)

        dependency = registry.run("shell:dependency_confusion.check", {"manifest_path": "missing-package.json"})
        self.assertEqual(dependency.status, "failed")
        self.assertEqual(dependency.summary["error"], "manifest_not_found")

    def test_audit_export_and_compliance_report_generation_create_linked_artifacts(self) -> None:
        export = self.client.post(
            "/api/v1/audit/export",
            headers=self._headers(),
            json={"format": "json", "filters": {"event_type": "policy.decision"}},
        )
        self.assertEqual(export.status_code, 201, export.text)
        export_artifacts = self.client.get(
            "/api/v1/artifacts",
            headers=self._headers(),
            params={"artifact_type": "audit.export"},
        )
        self.assertEqual(export_artifacts.status_code, 200, export_artifacts.text)
        self.assertEqual(len(export_artifacts.json()), 1)
        self.assertEqual(export_artifacts.json()[0]["links"][0]["target_type"], "audit_export")
        self.assertEqual(export_artifacts.json()[0]["links"][0]["target_id"], export.json()["id"])

        frameworks = self.client.get("/api/v1/compliance/frameworks", headers=self._headers())
        self.assertEqual(frameworks.status_code, 200, frameworks.text)
        framework_id = next(row["id"] for row in frameworks.json() if row["name"] == "SOC 2")
        report = self.client.post(
            "/api/v1/compliance/reports",
            headers=self._headers(),
            json={
                "framework_id": framework_id,
                "name": "Second Pass Compliance Report",
                "date_from": "2026-01-01",
                "date_to": "2026-12-31",
            },
        )
        self.assertEqual(report.status_code, 201, report.text)
        generated = self.client.post(
            f"/api/v1/compliance/reports/{report.json()['id']}/generate",
            headers=self._headers(),
        )
        self.assertEqual(generated.status_code, 200, generated.text)
        report_artifacts = self.client.get(
            "/api/v1/artifacts",
            headers=self._headers(),
            params={"artifact_type": "compliance.report"},
        )
        self.assertEqual(report_artifacts.status_code, 200, report_artifacts.text)
        self.assertEqual(len(report_artifacts.json()), 1)
        self.assertEqual(report_artifacts.json()[0]["links"][0]["target_type"], "compliance_report")
        self.assertEqual(report_artifacts.json()[0]["links"][0]["target_id"], report.json()["id"])


if __name__ == "__main__":
    unittest.main()
