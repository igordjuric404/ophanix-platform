from __future__ import annotations

import unittest

from pydantic import ValidationError

from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.models import (
    ToolDefinitionCreateRequest,
    ToolUpstreamTargetCreateRequest,
)
from product_platform.tool_gateway.repository import (
    DuplicateToolUpstreamTargetError,
    ToolRegistryRepository,
)


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
}


class ToolGatewayUpstreamPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.connection = self.database.connect()
        self.repository = ToolRegistryRepository(self.connection, DEMO_ORG_ID, DEMO_ENV_ID)

    def _create_active_tool(self, *, name: str = "claims.lookup") -> str:
        tool = self.repository.create_tool(
            ToolDefinitionCreateRequest(
                name=name,
                display_name="Claims Lookup",
                owner_team="claims-platform",
                required_scope=f"{name}:read",
                input_schema_json=VALID_INPUT_SCHEMA,
            ),
            created_by=DEMO_ADMIN_USER_ID,
        )
        self.repository.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
        return tool["id"]

    def _target_body(self) -> ToolUpstreamTargetCreateRequest:
        return ToolUpstreamTargetCreateRequest(
            base_url="https://claims.internal.example",
            path_template="/v1/claims/{claim_id}",
            method="POST",
            auth_mode="bearer",
            timeout_ms=2_500,
            health_url="https://claims.internal.example/health",
            expected_status=204,
        )

    def test_integration_creates_target_for_tool_with_health_check(self) -> None:
        with self.database.transaction():
            tool_id = self._create_active_tool()
            target = self.repository.create_upstream_target(tool_id, self._target_body())

        self.assertTrue(target["id"].startswith("target_"))
        self.assertEqual(target["tool_id"], tool_id)
        self.assertEqual(target["tool_name"], "claims.lookup")
        self.assertEqual(target["base_url"], "https://claims.internal.example")
        self.assertEqual(target["method"], "POST")
        self.assertEqual(target["status"], "configured")

        health = self.repository.get_upstream_health(target["id"])
        self.assertIsNotNone(health)
        self.assertEqual(health["health_url"], "https://claims.internal.example/health")
        self.assertEqual(health["expected_status"], 204)
        self.assertEqual(health["enabled"], 1)

    def test_integration_duplicate_active_target_is_rejected(self) -> None:
        with self.database.transaction():
            tool_id = self._create_active_tool()
            self.repository.create_upstream_target(tool_id, self._target_body())
            with self.assertRaisesRegex(DuplicateToolUpstreamTargetError, "already has"):
                self.repository.create_upstream_target(tool_id, self._target_body())

    def test_unit_invalid_url_is_rejected(self) -> None:
        with self.assertRaises(ValidationError) as context:
            ToolUpstreamTargetCreateRequest(
                base_url="file:///tmp/claims.sock",
                path_template="/claims",
            )

        self.assertIn("absolute http or https URL", str(context.exception))

    def test_repository_resolves_target_by_active_tool_name(self) -> None:
        with self.database.transaction():
            tool_id = self._create_active_tool(name="claims.lookup")
            target = self.repository.create_upstream_target(tool_id, self._target_body())

        resolved = self.repository.resolve_upstream_target_by_tool_name("claims.lookup")
        missing = self.repository.resolve_upstream_target_by_tool_name("claims.missing")

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["id"], target["id"])
        self.assertIsNone(missing)


if __name__ == "__main__":
    unittest.main()
