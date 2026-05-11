from __future__ import annotations

import re
import unittest

from product_platform.agents.credentials import hash_credential_token
from product_platform.db.seed import DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.direct_http_examples import (
    DIRECT_HTTP_ALLOWED_AGENT_ID,
    DIRECT_HTTP_ALLOWED_TOKEN,
    DIRECT_HTTP_DENIED_AGENT_ID,
    DIRECT_HTTP_DENIED_TOKEN,
    DIRECT_HTTP_TOOL_NAME,
    SUPPORT_BULK_CLAIMS_TOOL_NAME,
    SUPPORT_CROSS_CUSTOMER_CLAIM_TOOL_NAME,
    seed_support_demo_tool_gateway_fixtures,
    seed_tool_gateway_direct_http_fixtures,
)


FORBIDDEN_SECRET_PATTERNS = [
    re.compile(pattern)
    for pattern in [
        r"sk-[A-Za-z0-9]{20,}",
        r"ghp_[A-Za-z0-9]{20,}",
        r"AKIA[0-9A-Z]{16}",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    ]
]


class ToolGatewayDirectHttpExamplesPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)

    def test_seed_creates_allowed_agent_tool_target_and_permission(self) -> None:
        with self.database.transaction() as connection:
            fixtures = seed_tool_gateway_direct_http_fixtures(connection)
            seed_tool_gateway_direct_http_fixtures(connection)

            tool = connection.execute(
                """
                SELECT * FROM tool_definitions
                WHERE organization_id = ? AND environment_id = ? AND name = ?
                """,
                (DEMO_ORG_ID, DEMO_ENV_ID, DIRECT_HTTP_TOOL_NAME),
            ).fetchone()
            self.assertIsNotNone(tool)
            self.assertEqual(tool["status"], "active")
            self.assertEqual(fixtures.tool_id, tool["id"])

            agent = connection.execute(
                "SELECT * FROM agents WHERE id = ?",
                (DIRECT_HTTP_ALLOWED_AGENT_ID,),
            ).fetchone()
            self.assertIsNotNone(agent)
            self.assertEqual(agent["status"], "active")

            target = connection.execute(
                """
                SELECT * FROM tool_upstream_targets
                WHERE organization_id = ? AND environment_id = ? AND tool_id = ?
                """,
                (DEMO_ORG_ID, DEMO_ENV_ID, tool["id"]),
            ).fetchone()
            self.assertIsNotNone(target)
            self.assertEqual(target["status"], "configured")
            self.assertEqual(target["method"], "POST")

            permission = connection.execute(
                """
                SELECT * FROM agent_tool_permissions
                WHERE organization_id = ? AND environment_id = ?
                  AND agent_id = ? AND tool_id = ? AND status = 'active'
                """,
                (DEMO_ORG_ID, DEMO_ENV_ID, DIRECT_HTTP_ALLOWED_AGENT_ID, tool["id"]),
            ).fetchone()
            self.assertIsNotNone(permission)
            self.assertEqual(permission["scope"], "claims.lookup:read")

    def test_denied_fixture_has_credential_but_no_active_permission(self) -> None:
        with self.database.transaction() as connection:
            fixtures = seed_tool_gateway_direct_http_fixtures(connection)

            denied_agent = connection.execute(
                "SELECT * FROM agents WHERE id = ?",
                (DIRECT_HTTP_DENIED_AGENT_ID,),
            ).fetchone()
            self.assertIsNotNone(denied_agent)
            self.assertEqual(denied_agent["status"], "active")

            denied_credential = connection.execute(
                """
                SELECT * FROM agent_credentials
                WHERE agent_id = ? AND token_hash = ? AND status = 'active'
                """,
                (DIRECT_HTTP_DENIED_AGENT_ID, hash_credential_token(DIRECT_HTTP_DENIED_TOKEN)),
            ).fetchone()
            self.assertIsNotNone(denied_credential)

            denied_permission = connection.execute(
                """
                SELECT * FROM agent_tool_permissions
                WHERE organization_id = ? AND environment_id = ?
                  AND agent_id = ? AND tool_id = ? AND status = 'active'
                """,
                (DEMO_ORG_ID, DEMO_ENV_ID, DIRECT_HTTP_DENIED_AGENT_ID, fixtures.tool_id),
            ).fetchone()
            self.assertIsNone(denied_permission)

    def test_fixture_tokens_are_local_only_placeholders(self) -> None:
        for token in [DIRECT_HTTP_ALLOWED_TOKEN, DIRECT_HTTP_DENIED_TOKEN]:
            self.assertTrue(token.startswith("ophanix-local-only-"))
            for pattern in FORBIDDEN_SECRET_PATTERNS:
                self.assertIsNone(pattern.search(token))

    def test_support_demo_denied_tools_are_seeded_in_platform_without_permissions(self) -> None:
        with self.database.transaction() as connection:
            seed_tool_gateway_direct_http_fixtures(connection, upstream_base_url="http://127.0.0.1:8096")
            seed_support_demo_tool_gateway_fixtures(connection, upstream_base_url="http://127.0.0.1:8096")

            rows = connection.execute(
                """
                SELECT id, name, required_scope
                FROM tool_definitions
                WHERE organization_id = ? AND environment_id = ?
                  AND name IN (?, ?)
                ORDER BY name
                """,
                (
                    DEMO_ORG_ID,
                    DEMO_ENV_ID,
                    SUPPORT_BULK_CLAIMS_TOOL_NAME,
                    SUPPORT_CROSS_CUSTOMER_CLAIM_TOOL_NAME,
                ),
            ).fetchall()

            self.assertEqual([row["name"] for row in rows], [
                SUPPORT_BULK_CLAIMS_TOOL_NAME,
                SUPPORT_CROSS_CUSTOMER_CLAIM_TOOL_NAME,
            ])
            self.assertEqual(rows[0]["required_scope"], "claims.bulk:read")
            self.assertEqual(rows[1]["required_scope"], "claims.cross_customer:read")

            permission_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM agent_tool_permissions
                WHERE organization_id = ? AND environment_id = ?
                  AND tool_id IN (?, ?)
                  AND agent_id IN (?, ?)
                  AND status = 'active'
                """,
                (
                    DEMO_ORG_ID,
                    DEMO_ENV_ID,
                    rows[0]["id"],
                    rows[1]["id"],
                    DIRECT_HTTP_ALLOWED_AGENT_ID,
                    DIRECT_HTTP_DENIED_AGENT_ID,
                ),
            ).fetchone()["count"]
            self.assertEqual(permission_count, 0)


if __name__ == "__main__":
    unittest.main()
