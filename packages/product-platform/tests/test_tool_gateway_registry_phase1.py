from __future__ import annotations

import unittest

from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.db.time import utc_now_iso
from product_platform.tool_gateway.models import ToolDefinitionCreateRequest
from product_platform.tool_gateway.repository import DuplicateToolNameError, ToolRegistryRepository


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
    "additionalProperties": False,
}


class ToolGatewayRegistryPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            connection.execute(
                """
                INSERT INTO environments
                    (id, organization_id, name, slug, type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (
                    "env_other",
                    DEMO_ORG_ID,
                    "Other",
                    "other",
                    "development",
                    utc_now_iso(),
                    utc_now_iso(),
                ),
            )
        self.connection = self.database.connect()
        self.repository = ToolRegistryRepository(self.connection, DEMO_ORG_ID, DEMO_ENV_ID)

    def _body(self, *, name: str = "claims.lookup", status: str = "draft") -> ToolDefinitionCreateRequest:
        return ToolDefinitionCreateRequest(
            name=name,
            display_name="Claims Lookup",
            description="Lookup claim details for support workflows.",
            owner_team="claims-platform",
            required_scope="claims.lookup:read",
            input_schema_json=VALID_INPUT_SCHEMA,
            status=status,
        )

    def test_integration_creates_tool_definition_with_initial_version(self) -> None:
        with self.database.transaction():
            row = self.repository.create_tool(self._body(), created_by=DEMO_ADMIN_USER_ID)

        self.assertTrue(row["id"].startswith("tool_"))
        self.assertEqual(row["organization_id"], DEMO_ORG_ID)
        self.assertEqual(row["environment_id"], DEMO_ENV_ID)
        self.assertEqual(row["name"], "claims.lookup")
        self.assertEqual(row["status"], "draft")

        versions = self.repository.list_versions(row["id"])
        self.assertEqual(len(versions), 1)
        self.assertTrue(versions[0]["id"].startswith("toolv_"))
        self.assertEqual(versions[0]["version"], 1)
        self.assertEqual(versions[0]["required_scope"], "claims.lookup:read")
        self.assertIn("claim_id", versions[0]["input_schema_json"])

    def test_integration_duplicate_name_same_environment_is_rejected(self) -> None:
        with self.database.transaction():
            self.repository.create_tool(self._body(), created_by=DEMO_ADMIN_USER_ID)
            with self.assertRaisesRegex(DuplicateToolNameError, "already exists"):
                self.repository.create_tool(self._body(), created_by=DEMO_ADMIN_USER_ID)

    def test_integration_same_name_in_different_environment_is_allowed(self) -> None:
        with self.database.transaction():
            default_row = self.repository.create_tool(self._body(), created_by=DEMO_ADMIN_USER_ID)
            other_repository = ToolRegistryRepository(self.connection, DEMO_ORG_ID, "env_other")
            other_row = other_repository.create_tool(self._body(), created_by=DEMO_ADMIN_USER_ID)

        self.assertNotEqual(default_row["id"], other_row["id"])
        self.assertEqual(default_row["name"], other_row["name"])
        self.assertEqual(other_row["environment_id"], "env_other")

    def test_repository_filters_by_status_and_resolves_active_name(self) -> None:
        with self.database.transaction():
            draft = self.repository.create_tool(self._body(name="claims.lookup"), created_by=DEMO_ADMIN_USER_ID)
            active = self.repository.create_tool(self._body(name="refund.issue"), created_by=DEMO_ADMIN_USER_ID)
            self.repository.activate_tool(active["id"], actor_id=DEMO_ADMIN_USER_ID)

        draft_rows = self.repository.list_tools(status="draft")
        active_rows = self.repository.list_tools(status="active")
        resolved = self.repository.get_tool_by_name("refund.issue", active_only=True)
        disabled_resolution = self.repository.get_tool_by_name("claims.lookup", active_only=True)

        self.assertEqual([row["id"] for row in draft_rows], [draft["id"]])
        self.assertEqual([row["id"] for row in active_rows], [active["id"]])
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["id"], active["id"])
        self.assertIsNone(disabled_resolution)


if __name__ == "__main__":
    unittest.main()
