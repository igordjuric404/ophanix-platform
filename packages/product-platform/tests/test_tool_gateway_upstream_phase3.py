from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
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
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, *, timeout: float) -> FakeResponse:
        self.calls.append({"url": url, "timeout": timeout})
        return FakeResponse(self.status_code)


class ToolGatewayUpstreamPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        dns_patch = patch_public_dns_resolution()
        dns_patch.start()
        self.addCleanup(dns_patch.stop)
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com", "viewer@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        admin_login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Security Admin"]},
        )
        self.assertEqual(admin_login.status_code, 200, admin_login.text)
        self.admin_token = admin_login.json()["access_token"]
        viewer_login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "viewer@example.com", "roles": ["Viewer"]},
        )
        self.assertEqual(viewer_login.status_code, 200, viewer_login.text)
        self.viewer_token = viewer_login.json()["access_token"]

    def _headers(self, *, token: str | None = None, correlation_id: str = "corr-target") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token or self.admin_token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": correlation_id,
        }

    def _create_tool(self, *, name: str = "claims.lookup") -> dict:
        created = self.client.post(
            "/api/v1/tools",
            headers=self._headers(),
            json={
                "name": name,
                "display_name": "Claims Lookup",
                "owner_team": "claims-platform",
                "required_scope": f"{name}:read",
                "input_schema_json": VALID_INPUT_SCHEMA,
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        activated = self.client.post(
            f"/api/v1/tools/{created.json()['id']}/activate",
            headers=self._headers(),
            json={"reason": "ready"},
        )
        self.assertEqual(activated.status_code, 200, activated.text)
        return activated.json()

    def _target_body(self) -> dict:
        return {
            "base_url": "https://claims.internal.example",
            "path_template": "/v1/claims/{claim_id}",
            "method": "POST",
            "auth_mode": "none",
            "timeout_ms": 1200,
            "health_url": "https://claims.internal.example/ready",
            "expected_status": 204,
        }

    def test_api_creates_target_for_existing_tool_and_gets_health(self) -> None:
        tool = self._create_tool()

        created = self.client.post(
            f"/api/v1/tools/{tool['id']}/upstream-target",
            headers=self._headers(),
            json=self._target_body(),
        )

        self.assertEqual(created.status_code, 201, created.text)
        payload = created.json()
        self.assertTrue(payload["id"].startswith("target_"))
        self.assertEqual(payload["tool_id"], tool["id"])
        self.assertEqual(payload["tool_name"], "claims.lookup")
        self.assertEqual(payload["health"]["health_url"], "https://claims.internal.example/ready")

        fetched = self.client.get(
            f"/api/v1/tools/{tool['id']}/upstream-target",
            headers=self._headers(),
        )
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["id"], payload["id"])

        health = self.client.get(
            f"/api/v1/tool-upstream-targets/{payload['id']}/health",
            headers=self._headers(),
        )
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["expected_status"], 204)

    def test_api_creates_secret_reference_auth_target_without_returning_secret_ref(self) -> None:
        tool = self._create_tool(name="claims.authenticated")
        body = {
            **self._target_body(),
            "auth_mode": "api_key",
            "auth_config_json": {
                "secret_ref": "secref_partner_claims",
                "header_name": "X-Partner-Key",
            },
            "query_parameter_allowlist": ["include_notes"],
        }

        created = self.client.post(
            f"/api/v1/tools/{tool['id']}/upstream-target",
            headers=self._headers(),
            json=body,
        )

        self.assertEqual(created.status_code, 201, created.text)
        payload = created.json()
        self.assertEqual(payload["auth_mode"], "api_key")
        self.assertEqual(payload["query_parameter_allowlist"], ["include_notes"])
        self.assertNotIn("secret_ref", created.text)

    def test_api_rejects_upstream_target_outside_configured_host_allowlist(self) -> None:
        app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
                tool_gateway_upstream_host_allowlist=["*.approved.example"],
            ),
            database=self.database,
        )
        client = TestClient(app, raise_server_exceptions=False)
        login = client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Security Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        tool = self._create_tool(name="claims.allowlist")

        response = client.post(
            f"/api/v1/tools/{tool['id']}/upstream-target",
            headers={
                "Authorization": f"Bearer {login.json()['access_token']}",
                "X-Environment-ID": "env_default",
            },
            json=self._target_body(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("allowlist", response.json()["message"])

    def test_api_cannot_create_target_for_disabled_tool(self) -> None:
        tool = self._create_tool(name="claims.disabled")
        disabled = self.client.post(
            f"/api/v1/tools/{tool['id']}/disable",
            headers=self._headers(),
            json={"reason": "stop routing"},
        )
        self.assertEqual(disabled.status_code, 200)

        response = self.client.post(
            f"/api/v1/tools/{tool['id']}/upstream-target",
            headers=self._headers(),
            json=self._target_body(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("disabled or retired", response.json()["message"])

    def test_api_manual_health_check_persists_result(self) -> None:
        tool = self._create_tool()
        created = self.client.post(
            f"/api/v1/tools/{tool['id']}/upstream-target",
            headers=self._headers(),
            json=self._target_body(),
        )
        self.assertEqual(created.status_code, 201)
        fake_client = FakeHTTPClient(status_code=204)
        self.app.state.tool_gateway_http_client = fake_client

        checked = self.client.post(
            f"/api/v1/tool-upstream-targets/{created.json()['id']}/check-health",
            headers=self._headers(),
        )

        self.assertEqual(checked.status_code, 200, checked.text)
        self.assertEqual(checked.json()["last_status"], "healthy")
        self.assertIsNone(checked.json()["last_error"])
        self.assertEqual(fake_client.calls[0]["timeout"], 1.2)

        health = self.client.get(
            f"/api/v1/tool-upstream-targets/{created.json()['id']}/health",
            headers=self._headers(),
        )
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["last_status"], "healthy")

    def test_api_target_writes_require_security_manage_permission(self) -> None:
        tool = self._create_tool()

        response = self.client.post(
            f"/api/v1/tools/{tool['id']}/upstream-target",
            headers=self._headers(token=self.viewer_token),
            json=self._target_body(),
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("security:manage", response.json()["message"])

    def test_integration_target_writes_emit_audit_events(self) -> None:
        tool = self._create_tool()
        created = self.client.post(
            f"/api/v1/tools/{tool['id']}/upstream-target",
            headers=self._headers(correlation_id="corr-target-audit"),
            json=self._target_body(),
        )
        self.assertEqual(created.status_code, 201, created.text)
        patched = self.client.patch(
            f"/api/v1/tool-upstream-targets/{created.json()['id']}",
            headers=self._headers(correlation_id="corr-target-audit"),
            json={"timeout_ms": 2400, "expected_status": 200},
        )
        self.assertEqual(patched.status_code, 200, patched.text)

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="tool_upstream_target",
                resource_id=created.json()["id"],
            )
        )

        self.assertEqual(
            [event.event_type for event in events],
            ["tool.upstream_target.updated", "tool.upstream_target.created"],
        )
        self.assertEqual(events[0].payload_json["timeout_ms"], 2400)
        self.assertEqual(events[0].payload_json["health"]["expected_status"], 200)
        self.assertEqual(events[0].correlation_id, "corr-target-audit")


if __name__ == "__main__":
    unittest.main()
