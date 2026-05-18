from __future__ import annotations

import json
import unittest

from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.worker.store import JobStateConflictError, JobStateRepository, JobStatus


class WorkerPhase2Tests(unittest.TestCase):
    def test_job_state_transitions_capture_logs_and_metadata(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                repository = JobStateRepository(connection)
                job = repository.create_job(
                    organization_id="org_default",
                    environment_id="env_default",
                    job_type="demo.noop",
                    payload={"demo": True},
                    job_id="job_state",
                )
                running = repository.mark_running(job["id"])
                succeeded = repository.mark_succeeded(
                    job["id"],
                    expected_attempt=running["attempts"],
                    logs=["started", "finished"],
                    metrics={"duration_ms": 1},
                    result={"ok": True},
                )
                runs = repository.runs_for_job(job["id"])

            self.assertEqual(job["status"], JobStatus.QUEUED)
            self.assertEqual(running["status"], JobStatus.RUNNING)
            self.assertEqual(running["attempts"], 1)
            self.assertEqual(succeeded["status"], JobStatus.SUCCEEDED)
            self.assertEqual(len(runs), 1)
            self.assertEqual(json.loads(runs[0]["logs_json"]), ["started", "finished"])
            self.assertEqual(json.loads(runs[0]["metrics_json"])["duration_ms"], 1)
        finally:
            database.close()

    def test_failed_job_records_error_message(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                repository = JobStateRepository(connection)
                job = repository.create_job(
                    organization_id="org_default",
                    environment_id="env_default",
                    job_type="demo.fail",
                    payload={},
                    job_id="job_failed",
                )
                running = repository.mark_running(job["id"])
                failed = repository.mark_failed(
                    job["id"],
                    expected_attempt=running["attempts"],
                    error_message="boom",
                    logs=["started"],
                )
                runs = repository.runs_for_job(job["id"])

            self.assertEqual(failed["status"], JobStatus.FAILED)
            self.assertEqual(failed["error_message"], "boom")
            self.assertEqual(json.loads(runs[0]["result_json"])["error"], "boom")
        finally:
            database.close()

    def test_claim_next_queued_job_is_atomic_state_transition(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                repository = JobStateRepository(connection)
                first = repository.create_job(
                    organization_id="org_default",
                    environment_id="env_default",
                    job_type="demo.claim",
                    payload={"order": 1},
                    job_id="job_claim_first",
                )
                second = repository.create_job(
                    organization_id="org_default",
                    environment_id="env_default",
                    job_type="demo.claim",
                    payload={"order": 2},
                    job_id="job_claim_second",
                )

                claimed = repository.claim_next_queued_job(job_type="demo.claim")
                duplicate = repository.claim_queued_job(first["id"])
                next_claimed = repository.claim_next_queued_job(job_type="demo.claim")

            self.assertIsNotNone(claimed)
            self.assertEqual(claimed["id"], first["id"])
            self.assertEqual(claimed["status"], JobStatus.RUNNING)
            self.assertEqual(claimed["attempts"], 1)
            self.assertIsNone(duplicate)
            self.assertIsNotNone(next_claimed)
            self.assertEqual(next_claimed["id"], second["id"])
        finally:
            database.close()

    def test_retry_increments_attempt_count(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                repository = JobStateRepository(connection)
                job = repository.create_job(
                    organization_id="org_default",
                    environment_id="env_default",
                    job_type="demo.retry",
                    payload={},
                    max_attempts=2,
                    job_id="job_retry",
                )
                running = repository.mark_running(job["id"])
                failed = repository.mark_failed(
                    job["id"],
                    expected_attempt=running["attempts"],
                    error_message="try again",
                    logs=[],
                )
                repository.requeue_for_retry(job["id"], expected_attempt=failed["attempts"])
                retried = repository.mark_running(job["id"])

            self.assertEqual(retried["attempts"], 2)
            self.assertEqual(retried["status"], JobStatus.RUNNING)
        finally:
            database.close()

    def test_terminal_transition_rejects_stale_attempt(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                repository = JobStateRepository(connection)
                job = repository.create_job(
                    organization_id="org_default",
                    environment_id="env_default",
                    job_type="demo.retry",
                    payload={},
                    max_attempts=2,
                    job_id="job_stale_attempt",
                )
                running = repository.mark_running(job["id"])
                failed = repository.mark_failed(
                    job["id"],
                    expected_attempt=running["attempts"],
                    error_message="try again",
                    logs=[],
                )
                repository.requeue_for_retry(job["id"], expected_attempt=failed["attempts"])
                retry = repository.mark_running(job["id"])

                with self.assertRaises(JobStateConflictError):
                    repository.mark_succeeded(
                        job["id"],
                        expected_attempt=running["attempts"],
                        logs=[],
                        metrics={},
                        result={},
                    )

                current = repository.get_job(job["id"])

            self.assertEqual(retry["status"], JobStatus.RUNNING)
            self.assertEqual(current["attempts"], 2)
            self.assertEqual(current["status"], JobStatus.RUNNING)
        finally:
            database.close()


if __name__ == "__main__":
    unittest.main()
