from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.api.rbac import Permission, has_permission, permissions_for_roles
from product_platform.api.settings import Settings


class RoleMatrixTests(unittest.TestCase):
    def test_role_to_permission_matrix(self) -> None:
        self.assertIn(Permission.POLICY_READ, permissions_for_roles(["Viewer"]))
        self.assertNotIn(Permission.POLICY_WRITE, permissions_for_roles(["Viewer"]))
        self.assertIn(Permission.POLICY_WRITE, permissions_for_roles(["Policy Admin"]))
        self.assertIn(Permission.API_KEYS_MANAGE, permissions_for_roles(["Platform Admin"]))


class _Principal:
    def __init__(self, roles: list[str]) -> None:
        self.roles = roles


class PermissionHelperTests(unittest.TestCase):
    def test_has_permission_uses_union_of_roles(self) -> None:
        principal = _Principal(["Viewer", "Policy Admin"])

        self.assertTrue(has_permission(principal, Permission.POLICY_WRITE))
        self.assertTrue(has_permission(principal, Permission.AUDIT_READ))
        self.assertFalse(has_permission(principal, Permission.API_KEYS_MANAGE))


class AuthPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=["viewer@example.com", "policy@example.com"],
                session_secret="test-secret",
            )
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def _token_for(self, email: str, roles: list[str]) -> str:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def test_viewer_cannot_create_policy(self) -> None:
        token = self._token_for("viewer@example.com", ["Viewer"])
        response = self.client.post(
            "/api/v1/policies",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Environment-ID": "env_default",
                "X-Request-ID": "req-rbac-denied",
            },
        )

        self.assertEqual(response.status_code, 403)
        payload = response.json()
        self.assertEqual(payload["code"], "HTTP_ERROR")
        self.assertEqual(payload["request_id"], "req-rbac-denied")
        denied_events = self.app.state.denied_audit_events
        self.assertEqual(len(denied_events), 1)
        self.assertEqual(denied_events[0]["permission"], Permission.POLICY_WRITE)
        self.assertEqual(denied_events[0]["event_type"], "auth.permission_denied")
        audit_events = AuditEventRepository(self.app.state.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                event_type="auth.permission_denied",
            )
        )
        self.assertEqual(len(audit_events), 1)
        self.assertEqual(audit_events[0].decision, "deny")
        self.assertEqual(audit_events[0].payload_json["permission"], Permission.POLICY_WRITE)

    def test_policy_admin_can_create_policy_placeholder(self) -> None:
        token = self._token_for("policy@example.com", ["Policy Admin"])
        response = self.client.post(
            "/api/v1/policies",
            headers={"Authorization": f"Bearer {token}", "X-Environment-ID": "env_default"},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["id"], "policy_placeholder")
        self.assertEqual(payload["status"], "created")
        self.assertTrue(payload["created_by"])
        self.assertEqual(payload["environment_id"], "env_default")


if __name__ == "__main__":
    unittest.main()
