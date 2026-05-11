from __future__ import annotations

import unittest

from fastapi.testclient import TestClient
from pydantic import ValidationError

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.models import (
    ToolDefinitionCreateRequest,
    ToolResponsePolicyPatchRequest,
)
from product_platform.tool_gateway.repository import ToolRegistryRepository


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
}


class ToolGatewayResponsePhase1Tests(unittest.TestCase):
    def test_integration_default_response_policy_is_created_for_new_tool(self) -> None:
        database = create_migrated_test_database()
        with database.transaction() as connection:
            seed_demo_data(connection)
            repository = ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            tool = repository.create_tool(
                ToolDefinitionCreateRequest(
                    name="claims.lookup",
                    display_name="Claims Lookup",
                    owner_team="claims-platform",
                    required_scope="claims.lookup:read",
                    input_schema_json=VALID_INPUT_SCHEMA,
                ),
                created_by=DEMO_ADMIN_USER_ID,
            )
            policy = repository.get_response_policy(tool["id"])

        self.assertIsNotNone(policy)
        self.assertEqual(policy["tool_id"], tool["id"])
        self.assertEqual(policy["max_response_bytes"], 32768)
        self.assertEqual(policy["expose_to_agent"], 1)
        self.assertEqual(policy["strict_output_validation"], 1)
        self.assertIn("email", policy["redaction_rules_json"])
        self.assertIn("ssn", policy["redaction_rules_json"])

    def test_unit_invalid_max_response_size_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ToolResponsePolicyPatchRequest(max_response_bytes=0)

    def test_api_updates_response_policy(self) -> None:
        database = create_migrated_test_database()
        with database.transaction() as connection:
            seed_demo_data(connection)
        app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            ),
            database=database,
        )
        client = TestClient(app, raise_server_exceptions=False)
        login = client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Security Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        headers = {
            "Authorization": f"Bearer {login.json()['access_token']}",
            "X-Environment-ID": DEMO_ENV_ID,
        }
        created = client.post(
            "/api/v1/tools",
            headers=headers,
            json={
                "name": "claims.lookup",
                "display_name": "Claims Lookup",
                "owner_team": "claims-platform",
                "required_scope": "claims.lookup:read",
                "input_schema_json": VALID_INPUT_SCHEMA,
            },
        )
        self.assertEqual(created.status_code, 201, created.text)

        patched = client.patch(
            f"/api/v1/tools/{created.json()['id']}/response-policy",
            headers=headers,
            json={
                "max_response_bytes": 1024,
                "redaction_rules_json": {"redact_keys": ["claim_secret"]},
                "expose_to_agent": False,
                "strict_output_validation": False,
            },
        )

        self.assertEqual(patched.status_code, 200, patched.text)
        payload = patched.json()
        self.assertEqual(payload["max_response_bytes"], 1024)
        self.assertEqual(payload["redaction_rules_json"], {"redact_keys": ["claim_secret"]})
        self.assertFalse(payload["expose_to_agent"])
        self.assertFalse(payload["strict_output_validation"])


if __name__ == "__main__":
    unittest.main()
