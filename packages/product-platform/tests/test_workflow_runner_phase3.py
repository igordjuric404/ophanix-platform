from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.artifacts.storage import ArtifactStorageError, LocalArtifactProvider, calculate_sha256
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


VALID_POLICY = """version: "1.0"
name: workflow-artifact-valid
rules:
  - name: block_shell
    condition:
      field: tool_name
      operator: eq
      value: run_shell
    action: deny
"""

ARTIFACT_CONTENT = b'{"passed": true, "warnings": []}\n'


class WorkflowRunnerPhase3ArtifactTests(unittest.TestCase):
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
                dev_login_allowed_emails=["operator@example.com"],
                session_secret="test-secret",
                artifact_storage_path=self.artifact_root.name,
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

    def _upload_artifact(self, *, name: str = "policy-lint-output.json") -> dict[str, object]:
        response = self.client.post(
            "/api/v1/artifacts",
            headers=self._headers(),
            json={
                "artifact_type": "workflow.output",
                "name": name,
                "content_type": "application/json",
                "content_base64": base64.b64encode(ARTIFACT_CONTENT).decode("ascii"),
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _create_queued_workflow_run(self) -> str:
        response = self.client.post(
            "/api/v1/workflows/policy_lint/runs",
            headers=self._headers(),
            json={
                "inputs": {"policy_body": VALID_POLICY, "policy_format": "yaml"},
                "run_immediately": False,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def test_checksum_is_calculated_deterministically(self) -> None:
        self.assertEqual(
            calculate_sha256(b"hello"),
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
        )
        self.assertEqual(calculate_sha256(b"same"), calculate_sha256(b"same"))
        self.assertNotEqual(calculate_sha256(b"same"), calculate_sha256(b"different"))

    def test_artifact_is_stored_listed_downloadable_and_linked_to_workflow_run(self) -> None:
        run_id = self._create_queued_workflow_run()
        artifact = self._upload_artifact()

        self.assertEqual(artifact["checksum"], calculate_sha256(ARTIFACT_CONTENT))
        self.assertEqual(artifact["size_bytes"], len(ARTIFACT_CONTENT))
        self.assertTrue(artifact["storage_uri"].startswith("local-artifact://org_default/env_default/"))
        stored_relative_path = artifact["storage_uri"].removeprefix("local-artifact://")
        self.assertTrue((Path(self.artifact_root.name) / stored_relative_path).exists())

        listed = self.client.get(
            "/api/v1/artifacts",
            headers=self._headers(),
            params={"artifact_type": "workflow.output"},
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual([item["id"] for item in listed.json()], [artifact["id"]])

        downloaded = self.client.get(
            f"/api/v1/artifacts/{artifact['id']}/download",
            headers=self._headers(),
        )
        self.assertEqual(downloaded.status_code, 200, downloaded.text)
        payload = downloaded.json()
        self.assertEqual(base64.b64decode(payload["content_base64"]), ARTIFACT_CONTENT)
        self.assertTrue(payload["metadata"]["checksum_verified"])

        linked = self.client.post(
            f"/api/v1/artifacts/{artifact['id']}/links",
            headers=self._headers(),
            json={"target_type": "workflow_run", "target_id": run_id, "link_type": "output"},
        )
        self.assertEqual(linked.status_code, 201, linked.text)
        self.assertEqual(linked.json()["target_id"], run_id)

        detail = self.client.get(f"/api/v1/artifacts/{artifact['id']}", headers=self._headers())
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["links"][0]["target_type"], "workflow_run")
        self.assertEqual(detail.json()["links"][0]["link_type"], "output")

    def test_path_traversal_is_rejected_by_storage_and_api(self) -> None:
        with self.assertRaises(ArtifactStorageError):
            LocalArtifactProvider(Path(self.artifact_root.name)).upload("../escape.txt", b"x")

        response = self.client.post(
            "/api/v1/artifacts",
            headers=self._headers(),
            json={
                "artifact_type": "workflow.output",
                "name": "../secret.txt",
                "content_type": "text/plain",
                "content_base64": base64.b64encode(b"secret").decode("ascii"),
            },
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("path separators", response.json()["message"])

    def test_artifact_links_validate_target_type_and_target_existence(self) -> None:
        artifact = self._upload_artifact()

        invalid_type = self.client.post(
            f"/api/v1/artifacts/{artifact['id']}/links",
            headers=self._headers(),
            json={"target_type": "shell_command", "target_id": "run_1", "link_type": "output"},
        )
        self.assertEqual(invalid_type.status_code, 400, invalid_type.text)
        self.assertIn("target_type must be one of", invalid_type.json()["message"])

        missing_target = self.client.post(
            f"/api/v1/artifacts/{artifact['id']}/links",
            headers=self._headers(),
            json={"target_type": "workflow_run", "target_id": "run_missing", "link_type": "output"},
        )
        self.assertEqual(missing_target.status_code, 400, missing_target.text)
        self.assertIn("target was not found", missing_target.json()["message"])


if __name__ == "__main__":
    unittest.main()
