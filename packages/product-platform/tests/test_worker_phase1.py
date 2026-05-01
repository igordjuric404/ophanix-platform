from __future__ import annotations

import unittest

from product_platform.worker import (
    InMemoryJobQueue,
    JobContext,
    JobRegistry,
    JobRequest,
    JobResult,
    Worker,
)


class WorkerPhase1Tests(unittest.TestCase):
    def test_job_registry_resolves_known_job_type(self) -> None:
        registry = JobRegistry()

        def handler(context: JobContext) -> JobResult:
            return JobResult(result={"ok": True})

        registry.register("demo.noop", handler)

        self.assertIs(registry.resolve("demo.noop"), handler)

    def test_enqueue_and_worker_executes_job(self) -> None:
        registry = JobRegistry()
        queue = InMemoryJobQueue()

        def handler(context: JobContext) -> JobResult:
            context.log("started")
            context.metrics["items"] = context.payload["items"]
            return JobResult(result={"processed": context.payload["items"]})

        registry.register("demo.process", handler)
        queue.enqueue(JobRequest(job_type="demo.process", payload={"items": 3}, id="job_demo"))
        execution = Worker(queue, registry).run_once()

        self.assertIsNotNone(execution)
        self.assertEqual(execution.status, "succeeded")
        self.assertEqual(execution.result["processed"], 3)
        self.assertEqual(execution.logs, ["started"])
        self.assertEqual(execution.metrics["items"], 3)
        self.assertEqual(len(queue), 0)

    def test_unknown_job_type_fails_with_clear_error(self) -> None:
        queue = InMemoryJobQueue()
        queue.enqueue(JobRequest(job_type="missing.job", id="job_missing"))

        execution = Worker(queue, JobRegistry()).run_once()

        self.assertIsNotNone(execution)
        self.assertEqual(execution.status, "failed")
        self.assertIn("Unknown job type: missing.job", execution.error_message or "")

    def test_worker_graceful_shutdown_prevents_execution(self) -> None:
        queue = InMemoryJobQueue()
        queue.enqueue(JobRequest(job_type="demo.noop", id="job_stopped"))
        worker = Worker(queue, JobRegistry())
        worker.stop()

        execution = worker.run_once()

        self.assertIsNone(execution)
        self.assertTrue(worker.stopping)
        self.assertEqual(len(queue), 1)


if __name__ == "__main__":
    unittest.main()

