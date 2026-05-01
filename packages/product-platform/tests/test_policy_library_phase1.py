from __future__ import annotations

import unittest

from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.policies.models import PolicyCreateRequest, PolicyVersionCreateRequest
from product_platform.policies.repository import (
    PolicyRepository,
    calculate_policy_checksum,
    policy_response,
    policy_version_response,
)


SAMPLE_POLICY = """version: "1.0"
name: default
rules:
  - name: block_shell
    condition:
      field: tool_name
      operator: eq
      value: run_shell
    action: deny
"""


class PolicyLibraryPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.connection = self.database.connect()
        self.repository = PolicyRepository(self.connection, "org_default")

    def test_checksum_changes_when_body_changes(self) -> None:
        first = calculate_policy_checksum("rules: []\n")
        second = calculate_policy_checksum("rules:\n  - name: changed\n")

        self.assertTrue(first.startswith("sha256:"))
        self.assertNotEqual(first, second)

    def test_integration_create_policy(self) -> None:
        with self.database.transaction() as connection:
            repository = PolicyRepository(connection, "org_default")
            row = repository.create_policy(
                PolicyCreateRequest(
                    name="Runtime Guardrails",
                    description="Blocks high-risk runtime actions.",
                    scope="runtime-action",
                    tags=["Runtime", "Safety", "runtime"],
                ),
                actor_id="user_admin",
            )

        payload = policy_response(row)
        self.assertTrue(payload.id.startswith("policy_"))
        self.assertEqual(payload.organization_id, "org_default")
        self.assertEqual(payload.slug, "runtime-guardrails")
        self.assertEqual(payload.scope, "runtime-action")
        self.assertEqual(payload.owner_user_id, "user_admin")
        self.assertEqual(payload.tags, ["runtime", "safety"])
        self.assertEqual(payload.version_count, 0)

    def test_integration_create_multiple_versions(self) -> None:
        with self.database.transaction() as connection:
            repository = PolicyRepository(connection, "org_default")
            policy = repository.create_policy(
                PolicyCreateRequest(name="MCP Guard", scope="mcp-tool"),
                actor_id="user_admin",
            )
            first = repository.create_version(
                policy["id"],
                PolicyVersionCreateRequest(body_text=SAMPLE_POLICY),
                actor_id="user_admin",
            )
            second = repository.create_version(
                policy["id"],
                PolicyVersionCreateRequest(
                    body_text=SAMPLE_POLICY.replace("run_shell", "delete_file")
                ),
                actor_id="user_admin",
            )

        first_payload = policy_version_response(first)
        second_payload = policy_version_response(second)
        versions = self.repository.list_versions(policy["id"])
        refreshed = policy_response(self.repository.get_policy(policy["id"]))

        self.assertEqual(first_payload.version_number, 1)
        self.assertEqual(second_payload.version_number, 2)
        self.assertNotEqual(first_payload.checksum, second_payload.checksum)
        self.assertEqual([version["version_number"] for version in versions], [2, 1])
        self.assertEqual(refreshed.version_count, 2)

    def test_api_style_list_is_scoped_by_organization(self) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO organizations (id, name, slug, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "org_other",
                    "Other Org",
                    "other-org",
                    "2026-05-01T00:00:00+00:00",
                    "2026-05-01T00:00:00+00:00",
                ),
            )
            default_repo = PolicyRepository(connection, "org_default")
            other_repo = PolicyRepository(connection, "org_other")
            default_policy = default_repo.create_policy(
                PolicyCreateRequest(name="Default Scoped Policy", scope="agent"),
                actor_id="user_admin",
            )
            other_repo.create_policy(
                PolicyCreateRequest(name="Other Scoped Policy", scope="agent"),
                actor_id="other_user",
            )

        rows = self.repository.list_policies()
        payloads = [policy_response(row) for row in rows]

        self.assertEqual([policy.id for policy in payloads], [default_policy["id"]])
        self.assertEqual(payloads[0].organization_id, "org_default")


if __name__ == "__main__":
    unittest.main()
