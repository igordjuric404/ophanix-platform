from __future__ import annotations

import base64
import tempfile
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class WorkflowRunnerPhase4ArtifactAttestationTests(unittest.TestCase):
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
                dev_login_allowed_emails=["admin@example.com", "operator@example.com"],
                session_secret="test-secret",
                artifact_storage_path=self.artifact_root.name,
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        admin_login = self._login("admin@example.com", ["Platform Admin"])
        operator_login = self._login("operator@example.com", ["Operator"])
        self.admin_token = admin_login["access_token"]
        self.admin_user_id = admin_login["user"]["id"]
        self.operator_token = operator_login["access_token"]

    def _login(self, email: str, roles: list[str]) -> dict[str, object]:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _headers(self, token: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token or self.admin_token}",
            "X-Environment-ID": "env_default",
        }

    def _upload_artifact(self) -> dict[str, object]:
        response = self.client.post(
            "/api/v1/artifacts",
            headers=self._headers(),
            json={
                "artifact_type": "workflow.output",
                "name": "attestable-output.json",
                "content_type": "application/json",
                "content_base64": base64.b64encode(b'{"ok": true}\n').decode("ascii"),
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_attestation_requires_statement(self) -> None:
        artifact = self._upload_artifact()

        response = self.client.post(
            f"/api/v1/artifacts/{artifact['id']}/attest",
            headers=self._headers(),
            json={"statement": "   ", "signature_ref": "sig-empty"},
        )

        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["code"], "VALIDATION_ERROR")

    def test_operator_without_audit_write_cannot_attest(self) -> None:
        artifact = self._upload_artifact()

        response = self.client.post(
            f"/api/v1/artifacts/{artifact['id']}/attest",
            headers=self._headers(self.operator_token),
            json={"statement": "Operator reviewed this output."},
        )

        self.assertEqual(response.status_code, 403, response.text)
        self.assertIn("Missing permission: audit:write", response.json()["message"])

    def test_successful_attestation_persists_history_and_emits_audit_event(self) -> None:
        artifact = self._upload_artifact()

        response = self.client.post(
            f"/api/v1/artifacts/{artifact['id']}/attest",
            headers=self._headers(),
            json={
                "statement": "I attest this workflow artifact matches the recorded checksum.",
                "signature_ref": "sig-artifact-1",
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        attestation = response.json()
        self.assertEqual(attestation["artifact_id"], artifact["id"])
        self.assertEqual(attestation["signature_ref"], "sig-artifact-1")
        self.assertEqual(attestation["attested_by"], self.admin_user_id)

        detail = self.client.get(f"/api/v1/artifacts/{artifact['id']}", headers=self._headers())
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["attestations"][0]["id"], attestation["id"])

        downloaded = self.client.get(
            f"/api/v1/artifacts/{artifact['id']}/download",
            headers=self._headers(),
        )
        self.assertEqual(downloaded.status_code, 200, downloaded.text)
        self.assertEqual(downloaded.json()["artifact"]["attestations"][0]["id"], attestation["id"])

        with self.database.connect() as connection:
            events = AuditEventRepository(connection).query(
                AuditEventQuery(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="artifact.attested",
                    resource_id=artifact["id"],
                    limit=5,
                )
            )
        self.assertEqual(1, len(events))
        self.assertEqual("attested", events[0].decision)
        self.assertEqual(attestation["id"], events[0].payload_json["attestation_id"])
        self.assertEqual(artifact["checksum"], events[0].payload_json["checksum"])


if __name__ == "__main__":
    unittest.main()
