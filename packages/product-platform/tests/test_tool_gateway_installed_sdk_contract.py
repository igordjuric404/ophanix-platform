from __future__ import annotations

import importlib
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.models import CredentialScopeRequest
from product_platform.api.settings import Settings
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.invocation import ToolExecutionResult
from product_platform.tool_gateway.models import (
    AgentToolPermissionGrantRequest,
    ToolDefinitionCreateRequest,
)
from product_platform.tool_gateway.repository import ToolRegistryRepository


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
    "additionalProperties": False,
}


class ToolGatewayInstalledSdkContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
            AgentCredentialRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID).create_metadata(
                agent_id="agent_installed_sdk_contract",
                credential_type="bearer",
                raw_token="wheel-contract-token",
                issuer="installed-sdk-contract",
                expires_at="2030-01-01T00:00:00+00:00",
                scopes=[
                    CredentialScopeRequest(
                        scope="claims.lookup:read",
                        resource_type="tool",
                        resource_id="claims.lookup",
                    )
                ],
                status="active",
            )
            registry = ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            lookup_tool = registry.create_tool(
                ToolDefinitionCreateRequest(
                    name="claims.lookup",
                    display_name="Claims Lookup",
                    owner_team="claims-platform",
                    required_scope="claims.lookup:read",
                    input_schema_json=VALID_INPUT_SCHEMA,
                ),
                created_by=DEMO_ADMIN_USER_ID,
            )
            registry.activate_tool(lookup_tool["id"], actor_id=DEMO_ADMIN_USER_ID)
            hidden_tool = registry.create_tool(
                ToolDefinitionCreateRequest(
                    name="claims.hidden",
                    display_name="Claims Hidden",
                    owner_team="claims-platform",
                    required_scope="claims.hidden:read",
                    input_schema_json=VALID_INPUT_SCHEMA,
                ),
                created_by=DEMO_ADMIN_USER_ID,
            )
            registry.activate_tool(hidden_tool["id"], actor_id=DEMO_ADMIN_USER_ID)
            registry.grant_agent_tool_permission(
                "agent_installed_sdk_contract",
                AgentToolPermissionGrantRequest(
                    tool_id=lookup_tool["id"],
                    scope="claims.lookup:read",
                    granted_reason="installed SDK contract fixture",
                ),
                granted_by=DEMO_ADMIN_USER_ID,
            )
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.app.state.tool_gateway_executor = _FakeToolExecutor()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.standalone_root = Path(__file__).resolve().parents[2] / "ophanix-tool-gateway-sdk"

    def _insert_agent(self, connection) -> None:
        now = "2026-05-01T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, endpoint_url, owner_user_id, sponsor_user_id, status,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "agent_installed_sdk_contract",
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                "agent_installed_sdk_contract",
                "Installed SDK contract fixture.",
                "langgraph",
                "service",
                None,
                DEMO_ADMIN_USER_ID,
                DEMO_ADMIN_USER_ID,
                "active",
                now,
                now,
            ),
        )

    def test_installed_wheel_sdk_exercises_live_gateway_contract(self) -> None:
        with _installed_sdk_module(self.standalone_root) as installed_sdk:
            sdk_client = installed_sdk.OphanixToolGatewayClient(
                base_url="http://testserver",
                token_provider=installed_sdk.StaticTokenProvider("wheel-contract-token"),
                http_client=_TestClientGatewayHTTPClient(self.client),
                allow_insecure_http=True,
            )

            compatibility = sdk_client.check_compatibility()
            tools = sdk_client.list_all_tools()
            result = sdk_client.call_tool("claims.lookup", {"claim_id": "claim_123"})

            self.assertTrue(compatibility.compatible)
            self.assertEqual([tool.name for tool in tools], ["claims.lookup"])
            self.assertEqual(result.result["body"], {"ok": True})
            with self.assertRaises(installed_sdk.ToolDeniedError) as raised:
                sdk_client.call_tool("claims.hidden", {"claim_id": "claim_123"})
            self.assertEqual(raised.exception.reason_code, "tool_call_denied")


class _FakeToolExecutor:
    def execute(self, *, tool, payload, decision, principal) -> ToolExecutionResult:
        return ToolExecutionResult(
            status="succeeded",
            body={"ok": True},
            latency_ms=1.0,
            upstream_status_code=200,
        )


class _TestClientGatewayHTTPClient:
    def __init__(self, client: TestClient) -> None:
        self.client = client

    def stream(self, method: str, url: str, **kwargs):
        return _ResponseContext(self._request(method, url, **kwargs))

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self._request("POST", url, **kwargs)

    def close(self) -> None:
        return None

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        parsed = urlparse(url)
        query_params = {
            key: values[-1]
            for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
        }
        params = kwargs.get("params") or {}
        if isinstance(params, dict):
            query_params.update({str(key): str(value) for key, value in params.items()})
        response = self.client.request(
            method,
            parsed.path,
            headers=kwargs.get("headers"),
            json=kwargs.get("json"),
            params=query_params,
        )
        return httpx.Response(
            response.status_code,
            headers=dict(response.headers),
            content=response.content,
            request=httpx.Request(method, url),
        )


class _ResponseContext:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response

    def __enter__(self) -> httpx.Response:
        return self.response

    def __exit__(self, *_exc_info: object) -> None:
        return None


@contextmanager
def _installed_sdk_module(package_root: Path):
    with tempfile.TemporaryDirectory(prefix="ophanix-sdk-contract-") as temp_dir:
        temp_path = Path(temp_dir)
        wheel_dir = temp_path / "wheel"
        wheel_dir.mkdir()
        target = temp_path / "install"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--wheel-dir",
                str(wheel_dir),
                str(package_root),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        wheels = sorted(wheel_dir.glob("*.whl"))
        if len(wheels) != 1:
            raise AssertionError(f"Expected one SDK wheel, found {len(wheels)}")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                str(target),
                str(wheels[0]),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        saved_path = list(sys.path)
        saved_modules: dict[str, ModuleType] = {}
        for name in list(sys.modules):
            if name == "ophanix_tool_gateway" or name.startswith("ophanix_tool_gateway."):
                saved_modules[name] = sys.modules.pop(name)
        sys.path.insert(0, str(target))
        try:
            yield importlib.import_module("ophanix_tool_gateway")
        finally:
            for name in list(sys.modules):
                if name == "ophanix_tool_gateway" or name.startswith("ophanix_tool_gateway."):
                    sys.modules.pop(name)
            sys.modules.update(saved_modules)
            sys.path = saved_path


if __name__ == "__main__":
    unittest.main()
