from __future__ import annotations

import unittest

from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.policies.bindings import PolicyBindingRepository
from product_platform.policies.models import (
    PolicyBindingCreateRequest,
    PolicyBindingResolutionContext,
    PolicyExceptionCreateRequest,
    PolicyCreateRequest,
    PolicyVersionCreateRequest,
)
from product_platform.policies.repository import PolicyRepository


POLICY_BODY = """version: "1.0"
name: resolver-policy
rules:
  - name: block_shell
    condition:
      field: tool_name
      operator: eq
      value: run_shell
    action: deny
"""


class PolicyBindingsPhase2ResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            now = "2026-05-01T00:00:00+00:00"
            connection.execute(
                """
                INSERT INTO agents (
                    id, organization_id, environment_id, name, description, framework,
                    runtime_type, owner_user_id, sponsor_user_id, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "agent_default",
                    "org_default",
                    "env_default",
                    "Claims Agent",
                    "",
                    "langgraph",
                    "service",
                    "owner",
                    "sponsor",
                    "active",
                    now,
                    now,
                ),
            )
        self.connection = self.database.connect()
        self.policy_repository = PolicyRepository(self.connection, "org_default")
        self.binding_repository = PolicyBindingRepository(
            self.connection,
            "org_default",
            "env_default",
        )
        with self.database.transaction() as connection:
            policy_repo = PolicyRepository(connection, "org_default")
            policy = policy_repo.create_policy(
                PolicyCreateRequest(name="Resolver Guard", scope="agent"),
                actor_id="user_admin",
            )
            version = policy_repo.create_version(
                policy["id"],
                PolicyVersionCreateRequest(body_text=POLICY_BODY),
                actor_id="user_admin",
            )
        self.policy_id = policy["id"]
        self.version_id = version["id"]

    def _context(self, *, correlation_id: str = "corr-1") -> PolicyBindingResolutionContext:
        return PolicyBindingResolutionContext(
            organization_id="org_default",
            environment_id="env_default",
            target_type="agent",
            target_id="agent_default",
            agent_id="agent_default",
            correlation_id=correlation_id,
        )

    def test_agent_specific_binding_wins_over_environment_binding_when_priority_higher(self) -> None:
        with self.database.transaction() as connection:
            bindings = PolicyBindingRepository(connection, "org_default", "env_default")
            environment = bindings.create_binding(
                PolicyBindingCreateRequest(
                    policy_id=self.policy_id,
                    policy_version_id=self.version_id,
                    target_type="environment",
                    target_id="env_default",
                    priority=1,
                ),
                actor_id="user_admin",
            )
            agent = bindings.create_binding(
                PolicyBindingCreateRequest(
                    policy_id=self.policy_id,
                    policy_version_id=self.version_id,
                    target_type="agent",
                    target_id="agent_default",
                    priority=10,
                ),
                actor_id="user_admin",
            )

        resolved = self.binding_repository.resolve_bindings(self._context())

        self.assertEqual([row["id"] for row in resolved], [agent["id"], environment["id"]])

    def test_disabled_binding_is_ignored(self) -> None:
        with self.database.transaction() as connection:
            binding = PolicyBindingRepository(connection, "org_default", "env_default").create_binding(
                PolicyBindingCreateRequest(
                    policy_id=self.policy_id,
                    policy_version_id=self.version_id,
                    target_type="agent",
                    target_id="agent_default",
                    mode="disabled",
                ),
                actor_id="user_admin",
            )

        resolved = self.binding_repository.resolve_bindings(self._context())

        self.assertEqual(resolved, [])
        self.assertEqual(binding["mode"], "disabled")

    def test_rollout_percentage_is_deterministic_by_correlation_id(self) -> None:
        with self.database.transaction() as connection:
            PolicyBindingRepository(connection, "org_default", "env_default").create_binding(
                PolicyBindingCreateRequest(
                    policy_id=self.policy_id,
                    policy_version_id=self.version_id,
                    target_type="agent",
                    target_id="agent_default",
                    rollout_percentage=50,
                ),
                actor_id="user_admin",
            )

        first = self.binding_repository.resolve_bindings(self._context(correlation_id="corr-fixed"))
        second = self.binding_repository.resolve_bindings(self._context(correlation_id="corr-fixed"))

        self.assertEqual([row["id"] for row in first], [row["id"] for row in second])

    def test_active_exception_excludes_binding(self) -> None:
        with self.database.transaction() as connection:
            bindings = PolicyBindingRepository(connection, "org_default", "env_default")
            binding = bindings.create_binding(
                PolicyBindingCreateRequest(
                    policy_id=self.policy_id,
                    policy_version_id=self.version_id,
                    target_type="agent",
                    target_id="agent_default",
                ),
                actor_id="user_admin",
            )
            bindings.create_exception(
                binding["id"],
                PolicyExceptionCreateRequest(
                    reason="maintenance window",
                    expires_at="2026-05-02T00:00:00+00:00",
                ),
                actor_id="user_admin",
            )

        resolved = self.binding_repository.resolve_bindings(
            self._context(),
            now="2026-05-01T12:00:00+00:00",
        )
        expired = self.binding_repository.resolve_bindings(
            self._context(),
            now="2026-05-03T00:00:00+00:00",
        )

        self.assertEqual(resolved, [])
        self.assertEqual([row["id"] for row in expired], [binding["id"]])


if __name__ == "__main__":
    unittest.main()
