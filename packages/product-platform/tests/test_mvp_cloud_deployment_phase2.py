from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.dependencies import ReadinessProbes, create_default_dependency_registry
from product_platform.api.models import DependencyStatus
from product_platform.api.settings import Settings
from product_platform.db.migrator import MigrationRunner, is_supported_database_url
from product_platform.deployment.artifacts import LocalArtifactStore


PACKAGE_DIR = Path(__file__).resolve().parents[1]


def _healthy_probe(name: str):
    def probe(settings: Settings) -> DependencyStatus:
        return DependencyStatus(
            name=name,
            status="healthy",
            required=True,
            message=f"{name} fake probe healthy for tests.",
        )

    return probe


def _migrated_database_url(temp_dir: str) -> str:
    database_path = Path(temp_dir) / "cloud-preview.db"
    database_url = f"sqlite:///{database_path}"
    runner = MigrationRunner.from_settings(Settings(database_url=database_url))
    try:
        runner.apply_all()
    finally:
        runner.connection.close()
    return database_url


class MVPCloudDeploymentPhase2Tests(unittest.TestCase):
    def test_api_readiness_fails_when_required_cloud_services_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(
                Settings(
                    environment="staging",
                    deployment_mode="cloud",
                    database_url=_migrated_database_url(temp_dir),
                    redis_url=None,
                    object_storage_bucket=None,
                    secret_manager_ref=None,
                    session_secret="test-secret",
                    allow_sqlite_in_production=True,
                    gateway_token_hash_pepper="test-pepper",
                )
            )
            client = TestClient(app, raise_server_exceptions=False)

            response = client.get("/ready")

        self.assertEqual(response.status_code, 503)
        dependencies = {item["name"]: item for item in response.json()["dependencies"]}
        self.assertEqual(dependencies["database"]["status"], "healthy")
        self.assertEqual(dependencies["redis"]["status"], "unhealthy")
        self.assertEqual(dependencies["object_storage"]["status"], "unhealthy")
        self.assertEqual(dependencies["secret_manager"]["status"], "unhealthy")

    def test_api_readiness_reports_unreachable_postgres_runtime(self) -> None:
        app = create_app(
            Settings(
                environment="staging",
                deployment_mode="cloud",
                database_url="postgresql://ophanix:secret@db.example.com:5432/ophanix",
                redis_url="redis://redis.example.com:6379/0",
                object_storage_bucket="ophanix-product-artifacts",
                secret_manager_ref="projects/ophanix/secrets/product-platform",
                session_secret="test-secret",
                gateway_token_hash_pepper="test-pepper",
            )
        )
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/ready")

        self.assertEqual(response.status_code, 503)
        dependencies = {item["name"]: item for item in response.json()["dependencies"]}
        self.assertEqual(dependencies["database"]["status"], "unhealthy")
        self.assertIn("postgresql database is not ready or migrations are missing", dependencies["database"]["message"])

    def test_api_readiness_reports_unreachable_configured_redis(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(
                environment="staging",
                deployment_mode="cloud",
                database_url=_migrated_database_url(temp_dir),
                redis_url="redis://127.0.0.1:1/0",
                object_storage_bucket="ophanix-product-artifacts",
                object_storage_endpoint="https://object-storage.example.com",
                secret_manager_ref="projects/ophanix/secrets/product-platform",
                session_secret="test-secret",
                allow_sqlite_in_production=True,
                gateway_token_hash_pepper="test-pepper",
            )
            registry = create_default_dependency_registry(
                settings,
                probes=ReadinessProbes(
                    object_storage=_healthy_probe("object_storage"),
                    secret_manager=_healthy_probe("secret_manager"),
                ),
            )
            client = TestClient(
                create_app(settings, dependency_registry=registry),
                raise_server_exceptions=False,
            )

            response = client.get("/ready")

        dependencies = {item["name"]: item for item in response.json()["dependencies"]}
        self.assertEqual(response.status_code, 503)
        self.assertEqual(dependencies["redis"]["status"], "unhealthy")
        self.assertIn("not reachable", dependencies["redis"]["message"])

    def test_api_readiness_reports_configured_unchecked_secret_manager(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(
                environment="staging",
                deployment_mode="cloud",
                database_url=_migrated_database_url(temp_dir),
                redis_url="redis://redis.example.com:6379/0",
                object_storage_bucket="ophanix-product-artifacts",
                object_storage_endpoint="https://object-storage.example.com",
                secret_manager_ref="projects/ophanix/secrets/product-platform",
                session_secret="test-secret",
                allow_sqlite_in_production=True,
                gateway_token_hash_pepper="test-pepper",
            )
            registry = create_default_dependency_registry(
                settings,
                probes=ReadinessProbes(
                    redis=_healthy_probe("redis"),
                    object_storage=_healthy_probe("object_storage"),
                ),
            )
            client = TestClient(
                create_app(settings, dependency_registry=registry),
                raise_server_exceptions=False,
            )

            response = client.get("/ready")

        dependencies = {item["name"]: item for item in response.json()["dependencies"]}
        self.assertEqual(response.status_code, 503)
        self.assertEqual(dependencies["secret_manager"]["status"], "unchecked")
        self.assertIn("no probe adapter", dependencies["secret_manager"]["message"])

    def test_cloud_env_example_uses_supported_database_runtime(self) -> None:
        env_lines = (PACKAGE_DIR / "deploy/cloud/env.example").read_text().splitlines()
        database_url = next(
            line.split("=", 1)[1]
            for line in env_lines
            if line.startswith("OPHANIX_DATABASE_URL=")
        )

        self.assertTrue(is_supported_database_url(database_url))
        self.assertTrue(database_url.startswith("postgresql://"))

    def test_api_readiness_passes_when_cloud_services_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(
                environment="staging",
                deployment_mode="cloud",
                database_url=_migrated_database_url(temp_dir),
                redis_url="redis://redis.example.com:6379/0",
                object_storage_bucket="ophanix-product-artifacts",
                object_storage_endpoint="https://object-storage.example.com",
                secret_manager_ref="projects/ophanix/secrets/product-platform",
                session_secret="test-secret",
                allow_sqlite_in_production=True,
                gateway_token_hash_pepper="test-pepper",
            )
            registry = create_default_dependency_registry(
                settings,
                probes=ReadinessProbes(
                    redis=_healthy_probe("redis"),
                    object_storage=_healthy_probe("object_storage"),
                    secret_manager=_healthy_probe("secret_manager"),
                ),
            )
            client = TestClient(
                create_app(settings, dependency_registry=registry),
                raise_server_exceptions=False,
            )

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
