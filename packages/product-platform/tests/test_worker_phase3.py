from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.worker.scheduler import (
    JobScheduleRepository,
    calculate_next_run,
    validate_schedule_expression,
)


class WorkerPhase3Tests(unittest.TestCase):
    def test_next_run_calculation_supports_interval_and_cron(self) -> None:
        start = datetime(2026, 4, 30, 10, 7, 30, tzinfo=timezone.utc)

        interval_next = calculate_next_run("interval:5m", start)
        cron_next = calculate_next_run("*/15 * * * *", start)

        self.assertEqual(interval_next, datetime(2026, 4, 30, 10, 12, 30, tzinfo=timezone.utc))
        self.assertEqual(cron_next, datetime(2026, 4, 30, 10, 15, 0, tzinfo=timezone.utc))

    def test_schedule_expression_validation_rejects_unsafe_values(self) -> None:
        with self.assertRaises(ValueError):
            validate_schedule_expression("*/0 * * * *")
        with self.assertRaises(ValueError):
            validate_schedule_expression("interval:0m")
        with self.assertRaises(ValueError):
            validate_schedule_expression("not a schedule")

    def test_disabled_schedule_does_not_enqueue(self) -> None:
        database = create_migrated_test_database()
        try:
            now = datetime(2026, 4, 30, 10, 0, tzinfo=timezone.utc)
            with database.transaction() as connection:
                seed_demo_data(connection)
                schedules = JobScheduleRepository(connection)
                schedules.create_schedule(
                    organization_id="org_default",
                    environment_id="env_default",
                    job_type="demo.noop",
                    expression="interval:5m",
                    payload={},
                    enabled=False,
                    next_run_at=now.isoformat(),
                    schedule_id="sched_disabled",
                )
                jobs = schedules.enqueue_due(now)
                job_count = connection.execute(
                    "SELECT COUNT(*) AS count FROM background_jobs"
                ).fetchone()["count"]

            self.assertEqual(jobs, [])
            self.assertEqual(job_count, 0)
        finally:
            database.close()

    def test_duplicate_prevention_for_same_schedule_and_time(self) -> None:
        database = create_migrated_test_database()
        try:
            now = datetime(2026, 4, 30, 10, 0, tzinfo=timezone.utc)
            with database.transaction() as connection:
                seed_demo_data(connection)
                schedules = JobScheduleRepository(connection)
                schedule = schedules.create_schedule(
                    organization_id="org_default",
                    environment_id="env_default",
                    job_type="demo.noop",
                    expression="interval:5m",
                    payload={"same": True},
                    enabled=True,
                    next_run_at=now.isoformat(),
                    schedule_id="sched_duplicate",
                )
                first = schedules.enqueue_due(now)
                connection.execute(
                    "UPDATE job_schedules SET next_run_at = ? WHERE id = ?",
                    (now.isoformat(), schedule["id"]),
                )
                second = schedules.enqueue_due(now)
                rows = connection.execute("SELECT * FROM background_jobs").fetchall()

            self.assertEqual(len(first), 1)
            self.assertEqual(second, [])
            self.assertEqual(len(rows), 1)
            self.assertEqual(json.loads(rows[0]["payload_json"])["same"], True)
        finally:
            database.close()


if __name__ == "__main__":
    unittest.main()
