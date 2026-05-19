from __future__ import annotations

import unittest

import httpx

from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.health import ToolUpstreamHealthChecker
from product_platform.tool_gateway.models import (
    ToolDefinitionCreateRequest,
    ToolUpstreamTargetCreateRequest,
)
from product_platform.tool_gateway.repository import ToolRegistryRepository
from tool_gateway_dns import patch_public_dns_resolution


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
}


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class FakeHTTPClient:
    def __init__(self, *, status_code: int | None = None, exception: Exception | None = None) -> None:
        self.status_code = status_code
        self.exception = exception
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, *, timeout: float) -> FakeResponse:
        self.calls.append({"url": url, "timeout": timeout})
        if self.exception is not None:
            raise self.exception
        return FakeResponse(self.status_code or 200)


class FakeStreamingHTTPClient:
    def __init__(self, *, status_code: int) -> None:
        self.status_code = status_code
        self.calls: list[dict[str, object]] = []

    def stream(self, method: str, url: str, *, timeout: float):
        self.calls.append({"method": method, "url": url, "timeout": timeout})
        return _FakeStreamContext(FakeStreamingResponse(self.status_code))

    def get(self, *_args, **_kwargs):
        raise AssertionError("health checker should use stream() without reading the body")


class FakeStreamingResponse(FakeResponse):
    def iter_bytes(self):
        raise AssertionError("health checker should not read health response bodies")


class _FakeStreamContext:
    def __init__(self, response: FakeStreamingResponse) -> None:
        self.response = response

    def __enter__(self) -> FakeStreamingResponse:
        return self.response

    def __exit__(self, *_exc_info: object) -> None:
        return None


class AsyncFakeHTTPClient(FakeHTTPClient):
    async def get(self, url: str, *, timeout: float) -> FakeResponse:
        self.calls.append({"url": url, "timeout": timeout})
        if self.exception is not None:
            raise self.exception
        return FakeResponse(self.status_code or 200)


class ToolGatewayUpstreamPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        dns_patch = patch_public_dns_resolution()
        dns_patch.start()
        self.addCleanup(dns_patch.stop)
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.connection = self.database.connect()
        self.repository = ToolRegistryRepository(self.connection, DEMO_ORG_ID, DEMO_ENV_ID)

    def _create_target(self, *, expected_status: int = 200, timeout_ms: int = 1_500) -> str:
        tool = self.repository.create_tool(
            ToolDefinitionCreateRequest(
                name="claims.lookup",
                display_name="Claims Lookup",
                owner_team="claims-platform",
                required_scope="claims.lookup:read",
                input_schema_json=VALID_INPUT_SCHEMA,
            ),
            created_by=DEMO_ADMIN_USER_ID,
        )
        self.repository.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
        target = self.repository.create_upstream_target(
            tool["id"],
            ToolUpstreamTargetCreateRequest(
                base_url="https://claims.internal.example",
                path_template="/v1/claims/{claim_id}",
                timeout_ms=timeout_ms,
                health_url="https://claims.internal.example/ready",
                expected_status=expected_status,
            ),
        )
        return target["id"]

    def test_unit_healthy_response_marks_target_healthy(self) -> None:
        with self.database.transaction():
            target_id = self._create_target(expected_status=204)
            client = FakeHTTPClient(status_code=204)
            health = ToolUpstreamHealthChecker(
                self.repository,
                http_client=client,
            ).check_target(target_id)

        self.assertEqual(health.last_status, "healthy")
        self.assertIsNone(health.last_error)
        self.assertEqual(client.calls[0]["url"], "https://claims.internal.example/ready")
        self.assertEqual(client.calls[0]["timeout"], 1.5)
        self.assertEqual(self.repository.get_upstream_target(target_id)["status"], "healthy")

    def test_unit_health_checker_uses_stream_without_reading_response_body(self) -> None:
        with self.database.transaction():
            target_id = self._create_target(expected_status=204)
            client = FakeStreamingHTTPClient(status_code=204)
            health = ToolUpstreamHealthChecker(
                self.repository,
                http_client=client,
            ).check_target(target_id)

        self.assertEqual(health.last_status, "healthy")
        self.assertEqual(client.calls[0]["method"], "GET")

    def test_unit_unexpected_status_marks_target_degraded(self) -> None:
        with self.database.transaction():
            target_id = self._create_target(expected_status=204)
            health = ToolUpstreamHealthChecker(
                self.repository,
                http_client=FakeHTTPClient(status_code=500),
            ).check_target(target_id)

        self.assertEqual(health.last_status, "degraded")
        self.assertIn("Expected status 204, received 500", health.last_error)
        self.assertEqual(self.repository.get_upstream_target(target_id)["status"], "degraded")

    def test_unit_timeout_marks_target_unhealthy(self) -> None:
        with self.database.transaction():
            target_id = self._create_target()
            health = ToolUpstreamHealthChecker(
                self.repository,
                http_client=FakeHTTPClient(exception=httpx.TimeoutException("too slow")),
            ).check_target(target_id)

        self.assertEqual(health.last_status, "unhealthy")
        self.assertEqual(health.last_error, "Health check timed out.")
        self.assertEqual(self.repository.get_upstream_target(target_id)["status"], "unhealthy")

    def test_unit_exception_stores_useful_error_summary(self) -> None:
        with self.database.transaction():
            target_id = self._create_target()
            health = ToolUpstreamHealthChecker(
                self.repository,
                http_client=FakeHTTPClient(exception=RuntimeError("connection reset")),
            ).check_target(target_id)

        self.assertEqual(health.last_status, "unhealthy")
        self.assertIn("RuntimeError: connection reset", health.last_error)
        self.assertEqual(self.repository.get_upstream_target(target_id)["status"], "unhealthy")

    def test_unit_exception_summary_redacts_url_paths_and_credentials(self) -> None:
        with self.database.transaction():
            target_id = self._create_target()
            health = ToolUpstreamHealthChecker(
                self.repository,
                http_client=FakeHTTPClient(
                    exception=RuntimeError(
                        "failed at https://user:password@claims.example.com/private/token"
                    )
                ),
            ).check_target(target_id)

        self.assertEqual(health.last_status, "unhealthy")
        self.assertIn("https://claims.example.com/[redacted-path]", health.last_error)
        self.assertNotIn("password", health.last_error)
        self.assertNotIn("private/token", health.last_error)


class ToolGatewayUpstreamPhase2AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        dns_patch = patch_public_dns_resolution()
        dns_patch.start()
        self.addCleanup(dns_patch.stop)
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.connection = self.database.connect()
        self.repository = ToolRegistryRepository(self.connection, DEMO_ORG_ID, DEMO_ENV_ID)

    def _create_target(self, *, expected_status: int = 200, timeout_ms: int = 1_500) -> str:
        tool = self.repository.create_tool(
            ToolDefinitionCreateRequest(
                name="claims.lookup",
                display_name="Claims Lookup",
                owner_team="claims-platform",
                required_scope="claims.lookup:read",
                input_schema_json=VALID_INPUT_SCHEMA,
            ),
            created_by=DEMO_ADMIN_USER_ID,
        )
        self.repository.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
        target = self.repository.create_upstream_target(
            tool["id"],
            ToolUpstreamTargetCreateRequest(
                base_url="https://claims.internal.example",
                path_template="/v1/claims/{claim_id}",
                timeout_ms=timeout_ms,
                health_url="https://claims.internal.example/ready",
                expected_status=expected_status,
            ),
        )
        return target["id"]

    async def test_unit_async_health_checker_awaits_async_client(self) -> None:
        with self.database.transaction():
            target_id = self._create_target(expected_status=204)
            client = AsyncFakeHTTPClient(status_code=204)
            health = await ToolUpstreamHealthChecker(
                self.repository,
                http_client=client,
            ).check_target_async(target_id)

        self.assertEqual(health.last_status, "healthy")
        self.assertIsNone(health.last_error)
        self.assertEqual(client.calls[0]["url"], "https://claims.internal.example/ready")
        self.assertEqual(self.repository.get_upstream_target(target_id)["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
