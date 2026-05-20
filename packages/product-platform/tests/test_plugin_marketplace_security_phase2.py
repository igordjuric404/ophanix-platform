from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.marketplace.samples import sample_plugin_manifests
from marketplace_security_helpers import ed25519_key_pair, passing_artifact_evidence, signed_manifest


class PluginMarketplaceSecurityPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-20T00:00:00Z",
                dev_login_allowed_emails=["plugin-artifacts@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "plugin-artifacts@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]
        self.private_key, self.public_key = ed25519_key_pair()
        signing_key = self.client.post(
            "/api/v1/marketplace/signing-keys",
            headers=self._headers(),
            json={"name": "Artifact Test Root", "public_key": self.public_key},
        )
        self.assertEqual(signing_key.status_code, 201, signing_key.text)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def test_plugin_install_requires_artifact_scans(self) -> None:
        manifest = signed_manifest(
            sample_plugin_manifests()[0],
            self.private_key,
            include_artifact_evidence=False,
            name="missing-artifact-evidence-plugin",
        )
        imported = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(imported.status_code, 201, imported.text)
        version_id = imported.json()["versions"][0]["id"]
        allowed = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={
                "require_signature": True,
                "require_artifact_evidence": True,
                "allowed_plugin_types": ["agent"],
            },
        )
        self.assertEqual(allowed.status_code, 201, allowed.text)
        self.assertEqual(allowed.json()["result"], "deny")

        installed = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers(),
            json={"plugin_version_id": version_id, "environment_id": "env_default"},
        )

        self.assertEqual(installed.status_code, 409)
        self.assertIn("policy result denies", installed.json()["message"])

    def test_plugin_install_rejects_blocking_artifact_scan_findings(self) -> None:
        evidence = passing_artifact_evidence("vulnerable-plugin", "1.0.0")
        evidence["vulnerability_scan"] = {
            "status": "failed",
            "critical": 1,
            "high": 0,
            "findings": [{"id": "CVE-TEST-1", "severity": "critical"}],
        }
        manifest = signed_manifest(
            sample_plugin_manifests()[0],
            self.private_key,
            artifact_evidence=evidence,
            name="vulnerable-plugin",
        )
        imported = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(imported.status_code, 201, imported.text)
        version_id = imported.json()["versions"][0]["id"]

        policy = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={"require_signature": True, "require_artifact_evidence": True},
        )

        self.assertEqual(policy.status_code, 201, policy.text)
        self.assertEqual(policy.json()["result"], "deny")
        codes = {finding["code"] for finding in policy.json()["findings"]}
        self.assertIn("vulnerability_scan_blocked", codes)

        installed = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers(),
            json={"plugin_version_id": version_id, "environment_id": "env_default"},
        )
        self.assertEqual(installed.status_code, 409)

    def test_complete_artifact_evidence_allows_install_and_surfaces_evidence(self) -> None:
        manifest = signed_manifest(
            sample_plugin_manifests()[0],
            self.private_key,
            name="complete-artifact-evidence-plugin",
        )
        imported = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(imported.status_code, 201, imported.text)
        plugin = imported.json()
        version = plugin["versions"][0]
        version_id = version["id"]
        self.assertEqual(version["artifact_evidence"]["status"], "passed")
        self.assertEqual(version["artifact_evidence"]["artifact_digest"], manifest["package_digest"])

        policy = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={
                "require_signature": True,
                "require_artifact_evidence": True,
                "allowed_plugin_types": ["agent"],
            },
        )
        self.assertEqual(policy.status_code, 201, policy.text)
        self.assertEqual(policy.json()["result"], "allow")

        installed = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers(),
            json={"plugin_version_id": version_id, "environment_id": "env_default"},
        )
        self.assertEqual(installed.status_code, 201, installed.text)
        self.assertEqual(installed.json()["status"], "installed")

        detail = self.client.get(
            f"/api/v1/marketplace/plugins/{plugin['id']}",
            headers=self._headers(),
        )
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["versions"][0]["artifact_evidence"]["status"], "passed")

    def test_artifact_evidence_submission_records_audit_and_enables_install(self) -> None:
        evidence = passing_artifact_evidence("submitted-artifact-evidence-plugin", "1.0.0")
        manifest = signed_manifest(
            sample_plugin_manifests()[0],
            self.private_key,
            include_artifact_evidence=False,
            name="submitted-artifact-evidence-plugin",
            package_digest=evidence["artifact_digest"],
        )
        imported = self.client.post(
            "/api/v1/marketplace/plugins/import",
            headers=self._headers(),
            json={"manifest": manifest},
        )
        self.assertEqual(imported.status_code, 201, imported.text)
        version_id = imported.json()["versions"][0]["id"]

        submitted = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/artifact-evidence",
            headers={**self._headers(), "X-Correlation-ID": "corr-plugin-artifact-evidence"},
            json={"artifact_evidence": evidence},
        )
        self.assertEqual(submitted.status_code, 201, submitted.text)
        self.assertEqual(submitted.json()["status"], "passed")
        self.assertEqual(submitted.json()["artifact_digest"], evidence["artifact_digest"])

        policy = self.client.post(
            f"/api/v1/marketplace/plugins/{version_id}/check-policy",
            headers=self._headers(),
            json={"require_signature": True, "require_artifact_evidence": True},
        )
        self.assertEqual(policy.status_code, 201, policy.text)
        self.assertEqual(policy.json()["result"], "allow")

        installed = self.client.post(
            "/api/v1/marketplace/installations",
            headers=self._headers(),
            json={"plugin_version_id": version_id, "environment_id": "env_default"},
        )
        self.assertEqual(installed.status_code, 201, installed.text)

        with self.database.transaction() as connection:
            audit = connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE event_type = ?
                  AND resource_id = ?
                  AND correlation_id = ?
                """,
                (
                    "marketplace.plugin.artifact_evidence.recorded",
                    submitted.json()["id"],
                    "corr-plugin-artifact-evidence",
                ),
            ).fetchone()
        self.assertIsNotNone(audit)


if __name__ == "__main__":
    unittest.main()
