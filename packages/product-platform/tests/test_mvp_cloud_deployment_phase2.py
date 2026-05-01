from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.deployment.artifacts import LocalArtifactStore


class MVPCloudDeploymentPhase2Tests(unittest.TestCase):
    def test_api_readiness_fails_when_required_cloud_services_missing(self) -> None:
        app = create_app(
            Settings(
                environment="staging",
                deployment_mode="cloud",
                database_url="sqlite:///local.db",
                redis_url=None,
                object_storage_bucket=None,
                secret_manager_ref=None,
                session_secret="test-secret",
            )
        )
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/ready")

        self.assertEqual(response.status_code, 503)
        dependencies = {item["name"]: item for item in response.json()["dependencies"]}
        self.assertEqual(dependencies["database"]["status"], "unhealthy")
        self.assertEqual(dependencies["redis"]["status"], "unhealthy")
        self.assertEqual(dependencies["object_storage"]["status"], "unhealthy")
        self.assertEqual(dependencies["secret_manager"]["status"], "unhealthy")

    def test_api_readiness_passes_when_cloud_services_configured(self) -> None:
        app = create_app(
            Settings(
                environment="staging",
                deployment_mode="cloud",
                database_url="postgresql://ophanix:secret@db.example.com:5432/ophanix",
                redis_url="redis://redis.example.com:6379/0",
                object_storage_bucket="ophanix-product-artifacts",
                secret_manager_ref="projects/ophanix/secrets/product-platform",
                session_secret="test-secret",
            )
        )
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/ready")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "ready")

    def test_artifact_upload_download_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = LocalArtifactStore(Path(temp_dir))
            key = store.upload("pilots/demo/report.json", b'{"ok": true}')
            downloaded = store.download(key)

        self.assertEqual(key, "pilots/demo/report.json")
        self.assertEqual(downloaded, b'{"ok": true}')


if __name__ == "__main__":
    unittest.main()
