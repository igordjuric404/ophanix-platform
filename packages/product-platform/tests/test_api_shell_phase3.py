from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.dependencies import (
    DependencyRegistry,
    create_default_dependency_registry,
    static_dependency,
)
from product_platform.api.settings import Settings
from product_platform.db.migrator import MigrationRunner


def _settings() -> Settings:
    return Settings(
        app_name="Ophanix Test Platform",
        environment="test",
        build_sha="test-sha",
        build_time="2026-04-30T00:00:00Z",
    )


class DependencyRegistryTests(unittest.TestCase):
    def test_dependency_checker_handles_healthy_and_unhealthy_dependencies(self) -> None:
        registry = DependencyRegistry()
        registry.register("healthy", static_dependency("healthy", status="healthy"), required=True)
        registry.register("unhealthy", static_dependency("unhealthy", status="unhealthy"), required=True)

        ready, statuses = registry.readiness_status()

        self.assertFalse(ready)
        self.assertEqual([status.name for status in statuses], ["healthy", "unhealthy"])
        self.assertEqual(statuses[1].status, "unhealthy")
        self.assertTrue(statuses[1].required)

    def test_dependency_checker_turns_exceptions_into_unhealthy_status(self) -> None:
        registry = DependencyRegistry()

        def failing_check():
            raise RuntimeError("connection failed")

        registry.register("database", failing_check, required=True)

        ready, statuses = registry.readiness_status()

        self.assertFalse(ready)
        self.assertEqual(statuses[0].name, "database")
        self.assertEqual(statuses[0].status, "unhealthy")
        self.assertIn("connection failed", statuses[0].message or "")


class ProductApiShellPhase3Tests(unittest.TestCase):
    def _auth_headers(self, client: TestClient) -> dict[str, str]:
        login = client.post("/api/v1/auth/dev-login", json={"email": "admin@example.com"})
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_ready_changes_to_unhealthy_when_required_dependency_fails(self) -> None:
        registry = DependencyRegistry()
        registry.register("database", static_dependency("database", status="unhealthy"), required=True)
        registry.register("redis", static_dependency("redis", status="healthy"), required=False)
        client = TestClient(create_app(_settings(), dependency_registry=registry))

        response = client.get("/ready")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "unhealthy")
        self.assertEqual(payload["dependencies"][0]["name"], "database")
        self.assertTrue(payload["dependencies"][0]["required"])

    def test_optional_dependency_does_not_fail_readiness(self) -> None:
        registry = DependencyRegistry()
        registry.register("redis", static_dependency("redis", status="unhealthy"), required=False)
        client = TestClient(create_app(_settings(), dependency_registry=registry))

        response = client.get("/ready")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["dependencies"][0]["status"], "unhealthy")
        self.assertFalse(payload["dependencies"][0]["required"])

    def test_system_dependencies_return_registered_statuses(self) -> None:
        registry = DependencyRegistry()
        registry.register("database", static_dependency("database", status="healthy"), required=True)
        registry.register("redis", static_dependency("redis", status="unhealthy"), required=False)
        settings = _settings()
        settings.dev_login_allowed_emails.append("admin@example.com")
        client = TestClient(create_app(settings, dependency_registry=registry))

        response = client.get("/api/v1/system/dependencies", headers=self._auth_headers(client))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([dependency["name"] for dependency in payload], ["database", "redis"])
        self.assertEqual(payload[1]["status"], "unhealthy")

    def test_local_dependency_registry_reports_unconfigured_optional_services(self) -> None:
        with TemporaryDirectory() as directory:
            settings = Settings(
                database_url=f"sqlite:///{directory}/ophanix.db",
                deployment_mode="local",
            )
            MigrationRunner.from_settings(settings).apply_all()
            registry = create_default_dependency_registry(settings)

            ready, statuses = registry.readiness_status()
            by_name = {status.name: status for status in statuses}

            self.assertTrue(ready)
            self.assertEqual(by_name["database"].status, "healthy")
            self.assertEqual(by_name["event_store"].status, "healthy")
            self.assertEqual(by_name["redis"].status, "not_configured")
            self.assertEqual(by_name["model_provider"].status, "not_configured")
            self.assertFalse(by_name["model_provider"].required)

    def test_local_dependency_breaks_force_named_services_unhealthy(self) -> None:
        with TemporaryDirectory() as directory:
            settings = Settings(
                database_url=f"sqlite:///{directory}/ophanix.db",
                deployment_mode="local",
                system_dependency_breaks=["database", "model_provider"],
            )
            MigrationRunner.from_settings(settings).apply_all()
            registry = create_default_dependency_registry(settings)

            ready, statuses = registry.readiness_status()
            by_name = {status.name: status for status in statuses}

            self.assertFalse(ready)
            self.assertEqual(by_name["database"].status, "unhealthy")
            self.assertTrue(by_name["database"].required)
            self.assertEqual(by_name["model_provider"].status, "unhealthy")
            self.assertFalse(by_name["model_provider"].required)


if __name__ == "__main__":
    unittest.main()
