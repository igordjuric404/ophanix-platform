from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
    "additionalProperties": False,
}


class ToolGatewayRegistryPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Security Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self, *, correlation_id: str = "corr-tool-registry") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": correlation_id,
        }

    def _tool_body(
        self,
        *,
        name: str = "claims.lookup",
        owner_team: str = "claims-platform",
        input_schema_json: dict | None = VALID_INPUT_SCHEMA,
    ) -> dict:
        return {
            "name": name,
            "display_name": "Claims Lookup",
            "description": "Lookup claim details.",
            "owner_team": owner_team,
            "required_scope": f"{name}:read",
            "input_schema_json": input_schema_json,
        }

    def _create_tool(self, **overrides: object) -> dict:
        response = self.client.post(
            "/api/v1/tools",
            headers=self._headers(),
            json=self._tool_body(**overrides),
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_api_creates_and_retrieves_tool_definition(self) -> None:
        created = self._create_tool()

        self.assertTrue(created["id"].startswith("tool_"))
        self.assertEqual(created["name"], "claims.lookup")
        self.assertEqual(created["status"], "draft")
        self.assertEqual(created["latest_version"]["version"], 1)
        self.assertEqual(len(created["versions"]), 1)

        fetched = self.client.get(f"/api/v1/tools/{created['id']}", headers=self._headers())
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["id"], created["id"])
        self.assertEqual(fetched.json()["versions"][0]["version"], 1)

        versions = self.client.get(f"/api/v1/tools/{created['id']}/versions", headers=self._headers())
        self.assertEqual(versions.status_code, 200)
        self.assertEqual([version["version"] for version in versions.json()], [1])

    def test_api_list_supports_status_and_owner_filters(self) -> None:
        draft = self._create_tool(name="claims.lookup", owner_team="claims-platform")
        active = self._create_tool(name="refund.issue", owner_team="payments-platform")
        activated = self.client.post(
            f"/api/v1/tools/{active['id']}/activate",
            headers=self._headers(),
            json={"reason": "ready for gateway tests"},
        )
        self.assertEqual(activated.status_code, 200)

        active_list = self.client.get(
            "/api/v1/tools",
            headers=self._headers(),
            params={"status": "active"},
        )
        self.assertEqual(active_list.status_code, 200)
        self.assertEqual([tool["id"] for tool in active_list.json()], [active["id"]])

        owner_list = self.client.get(
            "/api/v1/tools",
            headers=self._headers(),
            params={"owner_team": "claims-platform"},
        )
        self.assertEqual(owner_list.status_code, 200)
        self.assertEqual([tool["id"] for tool in owner_list.json()], [draft["id"]])

    def test_api_patch_creates_new_version_when_contract_changes(self) -> None:
        created = self._create_tool()
        patched_schema = {
            "type": "object",
            "properties": {
                "claim_id": {"type": "string"},
                "include_history": {"type": "boolean"},
            },
            "required": ["claim_id"],
            "additionalProperties": False,
        }

        patched = self.client.patch(
            f"/api/v1/tools/{created['id']}",
            headers=self._headers(),
            json={
                "input_schema_json": patched_schema,
                "required_scope": "claims.lookup:extended",
                "change_summary": "include history flag",
            },
        )

        self.assertEqual(patched.status_code, 200)
        payload = patched.json()
        self.assertEqual(payload["required_scope"], "claims.lookup:extended")
        self.assertEqual(payload["latest_version"]["version"], 2)
        self.assertEqual([version["version"] for version in payload["versions"]], [2, 1])
        self.assertEqual(payload["versions"][0]["change_summary"], "include history flag")

    def test_api_invalid_schema_returns_field_details(self) -> None:
        response = self.client.post(
            "/api/v1/tools",
            headers=self._headers(),
            json=self._tool_body(
                input_schema_json={
                    "type": "object",
                    "properties": {"claim_id": {"type": "not-real"}},
                }
            ),
        )

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["code"], "SCHEMA_VALIDATION_ERROR")
        self.assertEqual(payload["details"]["field"], "input_schema_json")
        self.assertNotIn("Bearer", str(payload))

    def test_api_activation_fails_when_schema_missing(self) -> None:
        created = self._create_tool(name="claims.no_schema", input_schema_json=None)

        response = self.client.post(
            f"/api/v1/tools/{created['id']}/activate",
            headers=self._headers(),
            json={"reason": "should fail"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("Input schema is required", response.json()["message"])

    def test_api_create_rejects_non_draft_status(self) -> None:
        body = {
            **self._tool_body(name="claims.active_create", input_schema_json=None),
            "status": "active",
        }

        response = self.client.post(
            "/api/v1/tools",
            headers=self._headers(),
            json=body,
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("created as draft", response.text)

    def test_integration_lifecycle_changes_emit_audit_events(self) -> None:
        created = self._create_tool()
        patched = self.client.patch(
            f"/api/v1/tools/{created['id']}",
            headers=self._headers(correlation_id="corr-tool-audit"),
            json={"display_name": "Claims Lookup v2"},
        )
        self.assertEqual(patched.status_code, 200)
        activated = self.client.post(
            f"/api/v1/tools/{created['id']}/activate",
            headers=self._headers(correlation_id="corr-tool-audit"),
            json={"reason": "contract approved"},
        )
        self.assertEqual(activated.status_code, 200)
        disabled = self.client.post(
            f"/api/v1/tools/{created['id']}/disable",
            headers=self._headers(correlation_id="corr-tool-audit"),
            json={"reason": "maintenance"},
        )
        self.assertEqual(disabled.status_code, 200)

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="tool_definition",
                resource_id=created["id"],
            )
        )

        self.assertEqual(
            [event.event_type for event in events],
            [
                "tool.definition.disabled",
                "tool.definition.activated",
                "tool.definition.updated",
                "tool.definition.created",
            ],
        )
        self.assertEqual(events[0].payload_json["previous_status"], "active")
        self.assertEqual(events[0].payload_json["reason"], "maintenance")
        self.assertEqual(events[1].payload_json["previous_status"], "draft")
        self.assertEqual(events[1].payload_json["reason"], "contract approved")
        self.assertEqual(events[2].correlation_id, "corr-tool-audit")


if __name__ == "__main__":
    unittest.main()
