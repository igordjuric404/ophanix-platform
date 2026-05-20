from __future__ import annotations

import asyncio
import json
import unittest

from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.runtime.models import SagaCreateRequest, SagaStepCreateRequest
from product_platform.runtime.saga_executor import DemoSafeActionRunner, SagaExecutionService
from product_platform.runtime.sagas import SagaRepository


class CountingActionRunner(DemoSafeActionRunner):
    """Demo action runner that records which side effects were executed."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, str]] = []

    async def run(self, action_name: str, *, saga, step, compensation: bool = False) -> dict:
        mode = "compensation" if compensation else "execute"
        self.calls.append((action_name, mode))
        return await super().run(
            action_name,
            saga=saga,
            step=step,
            compensation=compensation,
        )


class RuntimeDurableExecutionPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_claims", "Claims Agent")
            self._insert_capability(connection, "agent_claims", "claims.lookup")
            self._insert_capability(connection, "agent_claims", "claims.refund")

    def _insert_agent(self, connection, agent_id: str, name: str) -> None:
        now = "2026-05-20T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, owner_user_id, sponsor_user_id, status, trust_score,
                trust_tier, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                "org_default",
                "env_default",
                name,
                "Durable checkpoint test agent",
                "langgraph",
                "service",
                "user_admin",
                "user_admin",
                "active",
                850,
                "trusted",
                now,
                now,
            ),
        )

    def _insert_capability(self, connection, agent_id: str, capability: str) -> None:
        now = "2026-05-20T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agent_capabilities (
                id, agent_id, capability_name, resource_type, status,
                requested_by, approved_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"cap_{agent_id}_{capability.replace('.', '_')}",
                agent_id,
                capability,
                "runtime-action",
                "approved",
                "user_admin",
                "user_admin",
                now,
            ),
        )

    def _repository(self, connection) -> SagaRepository:
        return SagaRepository(connection, "org_default", "env_default")

    def _create_two_step_saga(self, repository: SagaRepository) -> tuple[str, list]:
        saga = repository.create_saga(
            SagaCreateRequest(name="Checkpointed Refund", correlation_id="checkpoint-corr-001"),
            created_by="user_admin",
        )
        repository.add_step(
            saga["id"],
            SagaStepCreateRequest(
                step_order=1,
                name="Lookup order",
                action_name="claims.lookup_order",
                target_agent_id="agent_claims",
                required_capability="claims.lookup",
            ),
        )
        repository.add_step(
            saga["id"],
            SagaStepCreateRequest(
                step_order=2,
                name="Issue refund",
                action_name="claims.issue_refund",
                target_agent_id="agent_claims",
                required_capability="claims.refund",
                compensation_action="claims.reverse_refund",
            ),
        )
        return saga["id"], repository.list_steps(saga["id"])

    def _checkpoint_payload(self, saga_id: str, step) -> dict:
        return {
            "result": {
                "action_name": step["action_name"],
                "mode": "execute",
                "saga_id": saga_id,
                "step_id": step["id"],
                "correlation_id": "checkpoint-corr-001",
                "target_agent_id": "agent_claims",
                "demo_safe": True,
            },
            "side_effect_boundary": "after_activity_before_step_commit",
        }

    def test_checkpoint_create_restore_and_integrity_failure(self) -> None:
        with self.database.transaction() as connection:
            repository = self._repository(connection)
            saga_id, steps = self._create_two_step_saga(repository)
            first_step = steps[0]
            checkpoint = repository.create_checkpoint(
                saga_id=saga_id,
                step_id=first_step["id"],
                mode="execute",
                payload=self._checkpoint_payload(saga_id, first_step),
                policy_snapshot={"required_capability": first_step["required_capability"]},
                tool_calls=[{"action_name": first_step["action_name"], "mode": "execute"}],
            )
            restored = repository.restore_checkpoint(first_step["id"], "execute")
            connection.execute(
                """
                UPDATE saga_checkpoints
                SET payload_json = ?
                WHERE id = ?
                """,
                (json.dumps({"result": {"action_name": "claims.issue_refund"}}), checkpoint["id"]),
            )

        self.assertEqual(checkpoint["status"], "valid")
        self.assertTrue(checkpoint["payload_hash"].startswith("sha256:"))
        self.assertIsNotNone(restored["restored_at"])
        with self.database.transaction() as connection:
            repository = self._repository(connection)
            with self.assertRaises(ValueError):
                repository.restore_checkpoint(first_step["id"], "execute")

    def test_resume_restores_checkpoint_without_reexecuting_completed_side_effect(self) -> None:
        with self.database.transaction() as connection:
            repository = self._repository(connection)
            saga_id, steps = self._create_two_step_saga(repository)
            first_step = steps[0]
            checkpoint_payload = self._checkpoint_payload(saga_id, first_step)
            repository.update_saga_status(
                saga_id,
                "running",
                mark_started=True,
                expected_statuses={"draft"},
            )
            repository.update_step_status(
                first_step["id"],
                "executing",
                result={"action_name": first_step["action_name"]},
            )
            repository.complete_activity_result(
                saga_id=saga_id,
                step_id=first_step["id"],
                mode="execute",
                action_name=first_step["action_name"],
                result=checkpoint_payload["result"],
            )
            repository.create_checkpoint(
                saga_id=saga_id,
                step_id=first_step["id"],
                mode="execute",
                payload=checkpoint_payload,
                policy_snapshot={"required_capability": first_step["required_capability"]},
                tool_calls=[{"action_name": first_step["action_name"], "mode": "execute"}],
            )

        runner = CountingActionRunner()
        with self.database.transaction() as connection:
            repository = self._repository(connection)
            result = asyncio.run(
                SagaExecutionService(repository, action_runner=runner).execute(saga_id)
            )
            checkpoints = repository.list_checkpoints(saga_id)
            event_types = [event["event_type"] for event in repository.list_events(saga_id)]

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.replayed_step_ids, [first_step["id"]])
        self.assertEqual(runner.calls, [("claims.issue_refund", "execute")])
        self.assertEqual(len(checkpoints), 2)
        self.assertTrue(all(checkpoint["payload_hash"].startswith("sha256:") for checkpoint in checkpoints))
        self.assertIn("saga.checkpoint.restored", event_types)
        self.assertIn("saga.checkpoint.created", event_types)

    def test_saga_checkpoint_replay_skips_completed_step(self) -> None:
        """Selected audit regression: checkpoint replay skips an already completed step."""

        self.test_resume_restores_checkpoint_without_reexecuting_completed_side_effect()


if __name__ == "__main__":
    unittest.main()
