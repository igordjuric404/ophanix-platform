from __future__ import annotations

import asyncio
import json
import unittest
from collections.abc import Iterator
from contextlib import contextmanager

from product_platform.db.seed import seed_demo_data
from product_platform.db.postgres import Connection
from product_platform.db.testing import create_migrated_test_database
from product_platform.runtime.models import SagaCreateRequest, SagaStepCreateRequest
from product_platform.runtime.saga_executor import DemoSafeActionRunner, SagaExecutionService
from product_platform.runtime.sagas import SagaRepository, SagaStepValidationError


class SagaBuilderPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection, "agent_claims", "Claims Agent")
            self._insert_capability(connection, "agent_claims", "claims.lookup")
            self._insert_capability(connection, "agent_claims", "claims.refund")
            self._insert_capability(connection, "agent_claims", "notifications.email")

    def _insert_agent(self, connection, agent_id: str, name: str) -> None:
        now = "2026-05-01T00:00:00+00:00"
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
                "Saga test agent",
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
        now = "2026-05-01T00:00:00+00:00"
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

    def _create_saga(self, repository: SagaRepository, name: str = "Refund Saga") -> str:
        row = repository.create_saga(
            SagaCreateRequest(name=name, correlation_id="order-demo-001"),
            created_by="user_admin",
        )
        return row["id"]

    def test_successful_executor_step_records_status_and_result(self) -> None:
        with self.database.transaction() as connection:
            repository = self._repository(connection)
            saga_id = self._create_saga(repository)
            repository.add_step(
                saga_id,
                SagaStepCreateRequest(
                    step_order=1,
                    name="Lookup order",
                    action_name="claims.lookup_order",
                    target_agent_id="agent_claims",
                    required_capability="claims.lookup",
                ),
            )

            result = asyncio.run(SagaExecutionService(repository).execute(saga_id))

            self.assertEqual(result.status, "completed")
            self.assertEqual(repository.get_saga(saga_id)["status"], "completed")
            step = repository.list_steps(saga_id)[0]
            self.assertEqual(step["status"], "committed")
            payload = json.loads(step["result_json"])
            self.assertEqual(payload["action_name"], "claims.lookup_order")
            self.assertTrue(payload["demo_safe"])

    def test_completed_saga_cannot_be_executed_again(self) -> None:
        with self.database.transaction() as connection:
            repository = self._repository(connection)
            saga_id = self._create_saga(repository)
            repository.add_step(
                saga_id,
                SagaStepCreateRequest(
                    step_order=1,
                    name="Lookup order",
                    action_name="claims.lookup_order",
                    target_agent_id="agent_claims",
                    required_capability="claims.lookup",
                ),
            )

            asyncio.run(SagaExecutionService(repository).execute(saga_id))

            with self.assertRaisesRegex(ValueError, "completed"):
                asyncio.run(SagaExecutionService(repository).execute(saga_id))

    def test_rejects_unknown_saga_action_when_adding_step(self) -> None:
        with self.database.transaction() as connection:
            repository = self._repository(connection)
            saga_id = self._create_saga(repository)

            with self.assertRaisesRegex(SagaStepValidationError, "supported saga actions"):
                repository.add_step(
                    saga_id,
                    SagaStepCreateRequest(
                        step_order=1,
                        name="Unknown action",
                        action_name="claims.transfer_cash",
                        target_agent_id="agent_claims",
                        required_capability="claims.lookup",
                    ),
                )

    def test_executor_transaction_factory_keeps_execution_in_short_transactions(self) -> None:
        transaction_count = 0

        @contextmanager
        def transaction_factory() -> Iterator[Connection]:
            nonlocal transaction_count
            transaction_count += 1
            with self.database.transaction() as connection:
                yield connection

        with self.database.transaction() as connection:
            repository = self._repository(connection)
            saga_id = self._create_saga(repository)
            repository.add_step(
                saga_id,
                SagaStepCreateRequest(
                    step_order=1,
                    name="Lookup order",
                    action_name="claims.lookup_order",
                    target_agent_id="agent_claims",
                    required_capability="claims.lookup",
                ),
            )

        repository = SagaRepository(self.database.connect(), "org_default", "env_default")
        result = asyncio.run(
            SagaExecutionService(repository, transaction_factory=transaction_factory).execute(saga_id)
        )

        self.assertEqual(result.status, "completed")
        self.assertGreaterEqual(transaction_count, 3)

    def test_failed_step_triggers_reverse_compensation(self) -> None:
        with self.database.transaction() as connection:
            repository = self._repository(connection)
            saga_id = self._create_saga(repository)
            refund_step = repository.add_step(
                saga_id,
                SagaStepCreateRequest(
                    step_order=1,
                    name="Issue refund",
                    action_name="claims.issue_refund",
                    target_agent_id="agent_claims",
                    required_capability="claims.refund",
                    compensation_action="claims.reverse_refund",
                ),
            )
            failed_step = repository.add_step(
                saga_id,
                SagaStepCreateRequest(
                    step_order=2,
                    name="Send email",
                    action_name="notifications.send_email",
                    target_agent_id="agent_claims",
                    required_capability="notifications.email",
                ),
            )

            service = SagaExecutionService(
                repository,
                action_runner=DemoSafeActionRunner(failure_actions={"notifications.send_email"}),
            )
            result = asyncio.run(service.execute(saga_id))

            self.assertEqual(result.status, "compensated")
            self.assertEqual(result.failed_step_id, failed_step["id"])
            self.assertEqual(result.compensated_step_ids, [refund_step["id"]])
            self.assertEqual(repository.get_saga(saga_id)["status"], "compensated")
            statuses = {step["id"]: step["status"] for step in repository.list_steps(saga_id)}
            self.assertEqual(statuses[refund_step["id"]], "compensated")
            self.assertEqual(statuses[failed_step["id"]], "failed")

    def test_step_events_are_persisted(self) -> None:
        with self.database.transaction() as connection:
            repository = self._repository(connection)
            saga_id = self._create_saga(repository)
            repository.add_step(
                saga_id,
                SagaStepCreateRequest(
                    step_order=1,
                    name="Issue refund",
                    action_name="claims.issue_refund",
                    target_agent_id="agent_claims",
                    required_capability="claims.refund",
                    compensation_action="claims.reverse_refund",
                ),
            )
            repository.add_step(
                saga_id,
                SagaStepCreateRequest(
                    step_order=2,
                    name="Send email",
                    action_name="notifications.send_email",
                    target_agent_id="agent_claims",
                    required_capability="notifications.email",
                ),
            )

            service = SagaExecutionService(
                repository,
                action_runner=DemoSafeActionRunner(failure_actions={"notifications.send_email"}),
            )
            asyncio.run(service.execute(saga_id))

            event_types = [event["event_type"] for event in repository.list_events(saga_id)]
            self.assertIn("saga.started", event_types)
            self.assertIn("saga.step.committed", event_types)
            self.assertIn("saga.step.failed", event_types)
            self.assertIn("saga.compensating", event_types)
            self.assertIn("saga.step.compensated", event_types)
            self.assertIn("saga.compensated", event_types)


if __name__ == "__main__":
    unittest.main()
