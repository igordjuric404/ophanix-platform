from __future__ import annotations

import asyncio
import json
import unittest

from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.runtime.models import SagaCreateRequest, SagaStepCreateRequest
from product_platform.runtime.saga_executor import DemoSafeActionRunner, SagaExecutionService
from product_platform.runtime.sagas import SagaRepository
from product_platform.worker.store import JobStateConflictError, JobStateRepository, JobStatus


class CountingActionRunner(DemoSafeActionRunner):
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


class TestsDocsProductionReadinessPhase3Tests(unittest.TestCase):
    def test_runtime_crash_replay_and_dlq(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                self._insert_agent(connection)
                repository = SagaRepository(connection, "org_default", "env_default")
                saga_id, steps = self._create_two_step_saga(repository)
                first_step = steps[0]
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
                    result={
                        "action_name": first_step["action_name"],
                        "mode": "execute",
                        "saga_id": saga_id,
                        "step_id": first_step["id"],
                        "correlation_id": "tst-runtime-crash-replay",
                        "target_agent_id": "agent_claims",
                        "demo_safe": True,
                    },
                )

            runner = CountingActionRunner()
            with database.transaction() as connection:
                repository = SagaRepository(connection, "org_default", "env_default")
                result = asyncio.run(
                    SagaExecutionService(repository, action_runner=runner).execute(saga_id)
                )
                replayed_steps = repository.list_steps(saga_id)
                activity_results = repository.list_activity_results(saga_id)
                events = repository.list_events(saga_id)

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.replayed_step_ids, [first_step["id"]])
            self.assertEqual(runner.calls, [("claims.issue_refund", "execute")])
            self.assertEqual([step["status"] for step in replayed_steps], ["committed", "committed"])
            self.assertEqual(len(activity_results), 2)
            self.assertEqual(
                json.loads(activity_results[0]["result_json"])["action_name"],
                "claims.lookup_order",
            )
            self.assertTrue(activity_results[0]["idempotency_key"].startswith("saga:"))
            self.assertIn("saga.recovered", {event["event_type"] for event in events})
            self.assertIn("saga.activity.replayed", {event["event_type"] for event in events})

            with database.transaction() as connection:
                jobs = JobStateRepository(connection)
                job = jobs.create_job(
                    organization_id="org_default",
                    environment_id="env_default",
                    job_type="runtime.failure",
                    payload={"source": "test_runtime_crash_replay_and_dlq"},
                    max_attempts=1,
                    job_id="job_runtime_dlq",
                )
                running = jobs.mark_running(job["id"])
                failed = jobs.mark_failed(
                    job["id"],
                    expected_attempt=running["attempts"],
                    error_message="exhausted retries",
                    logs=["started", "failed"],
                )
                with self.assertRaises(JobStateConflictError):
                    jobs.requeue_for_retry(job["id"], expected_attempt=failed["attempts"])
                terminal = jobs.get_job(job["id"])
                runs = jobs.runs_for_job(job["id"])

            self.assertEqual(terminal["status"], JobStatus.FAILED)
            self.assertEqual(terminal["attempts"], terminal["max_attempts"])
            self.assertEqual(terminal["error_message"], "exhausted retries")
            self.assertEqual(len(runs), 1)
            self.assertEqual(json.loads(runs[0]["result_json"])["error"], "exhausted retries")
        finally:
            database.close()

    def _insert_agent(self, connection) -> None:
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
                "agent_claims",
                "org_default",
                "env_default",
                "Claims Agent",
                "Runtime reliability test agent",
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
        for capability in ("claims.lookup", "claims.refund"):
            connection.execute(
                """
                INSERT INTO agent_capabilities (
                    id, agent_id, capability_name, resource_type, status,
                    requested_by, approved_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"cap_agent_claims_{capability.replace('.', '_')}",
                    "agent_claims",
                    capability,
                    "runtime-action",
                    "approved",
                    "user_admin",
                    "user_admin",
                    now,
                ),
            )

    def _create_two_step_saga(self, repository: SagaRepository) -> tuple[str, list]:
        saga = repository.create_saga(
            SagaCreateRequest(
                name="Runtime Crash Replay",
                correlation_id="tst-runtime-crash-replay",
            ),
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


if __name__ == "__main__":
    unittest.main()
