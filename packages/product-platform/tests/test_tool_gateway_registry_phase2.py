from __future__ import annotations

import json
import unittest

from product_platform.db.ids import generate_id
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.db.time import utc_now_iso
from product_platform.tool_gateway.models import ToolDefinitionCreateRequest
from product_platform.tool_gateway.repository import ToolLifecycleError, ToolRegistryRepository
from product_platform.tool_gateway.schemas import ToolSchemaValidationError, validate_tool_contract_schema


VALID_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
}


INVALID_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "definitely-not-a-json-schema-type"}},
}


class ToolGatewayRegistryPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.connection = self.database.connect()
        self.repository = ToolRegistryRepository(self.connection, DEMO_ORG_ID, DEMO_ENV_ID)

    def _body(
        self,
        *,
        name: str = "claims.lookup",
        input_schema_json: dict | None = VALID_SCHEMA,
    ) -> ToolDefinitionCreateRequest:
        return ToolDefinitionCreateRequest(
            name=name,
            display_name="Claims Lookup",
            owner_team="claims-platform",
            required_scope="claims.lookup:read",
            input_schema_json=input_schema_json,
        )

    def test_unit_valid_json_schema_is_accepted(self) -> None:
        validate_tool_contract_schema(VALID_SCHEMA, field="input_schema_json")

    def test_unit_invalid_json_schema_is_rejected_with_clear_field(self) -> None:
        with self.assertRaises(ToolSchemaValidationError) as context:
            validate_tool_contract_schema(INVALID_SCHEMA, field="input_schema_json")

        self.assertEqual(context.exception.field, "input_schema_json")
        self.assertIn("not valid under any of the given schemas", str(context.exception))

    def test_repository_rejects_invalid_input_schema_on_create(self) -> None:
        with self.database.transaction():
            with self.assertRaises(ToolSchemaValidationError) as context:
                self.repository.create_tool(
                    self._body(input_schema_json=INVALID_SCHEMA),
                    created_by=DEMO_ADMIN_USER_ID,
                )

        self.assertEqual(context.exception.field, "input_schema_json")

    def test_repository_activation_fails_when_input_schema_is_missing(self) -> None:
        with self.database.transaction():
            row = self.repository.create_tool(
                self._body(name="claims.no_schema", input_schema_json=None),
                created_by=DEMO_ADMIN_USER_ID,
            )
            with self.assertRaisesRegex(ToolLifecycleError, "Input schema is required"):
                self.repository.activate_tool(row["id"], actor_id=DEMO_ADMIN_USER_ID)

    def test_repository_activation_fails_when_stored_schema_is_invalid(self) -> None:
        now = utc_now_iso()
        tool_id = generate_id("tool")
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO tool_definitions (
                    id, organization_id, environment_id, name, display_name,
                    description, owner_team, status, required_scope, input_schema_json,
                    output_schema_json, created_by, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tool_id,
                    DEMO_ORG_ID,
                    DEMO_ENV_ID,
                    "claims.invalid_schema",
                    "Invalid Schema",
                    "",
                    "claims-platform",
                    "draft",
                    "claims.invalid:read",
                    json.dumps(INVALID_SCHEMA, sort_keys=True),
                    None,
                    DEMO_ADMIN_USER_ID,
                    now,
                    now,
                ),
            )
            repository = ToolRegistryRepository(connection, DEMO_ORG_ID, DEMO_ENV_ID)
            with self.assertRaises(ToolSchemaValidationError) as context:
                repository.activate_tool(tool_id, actor_id=DEMO_ADMIN_USER_ID)

        self.assertEqual(context.exception.field, "input_schema_json")


if __name__ == "__main__":
    unittest.main()
