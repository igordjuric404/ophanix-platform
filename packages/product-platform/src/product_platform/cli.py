"""Command-line entrypoint for the product API."""

from __future__ import annotations

import argparse
import time

import uvicorn

from product_platform.api.settings import load_settings
from product_platform.db.migrator import MigrationRunner
from product_platform.db.seed import reset_demo_data, seed_demo_data
from product_platform.demo.services import check_demo_http_health, run_demo_http_service
from product_platform.worker import InMemoryJobQueue, JobRegistry, JobRequest, JobResult, Worker


def main() -> None:
    """Run product platform commands."""

    parser = argparse.ArgumentParser(description="Run Ophanix product platform commands")
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="Run the product API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8088)

    db = subparsers.add_parser("db", help="Manage the product database")
    db_subparsers = db.add_subparsers(dest="db_command")
    db_subparsers.add_parser("migrate", help="Apply all pending migrations")
    db_subparsers.add_parser("rollback", help="Roll back the latest migration")
    db_subparsers.add_parser("seed", help="Seed local demo data")
    reset = db_subparsers.add_parser("reset-demo", help="Reset local demo data")
    reset.add_argument("--remove-admin", action="store_true")

    worker = subparsers.add_parser("worker", help="Run local worker utilities")
    worker_subparsers = worker.add_subparsers(dest="worker_command")
    worker_subparsers.add_parser("noop", help="Execute one in-memory no-op job")
    loop = worker_subparsers.add_parser("loop", help="Run a lightweight local worker loop")
    loop.add_argument("--interval-seconds", type=float, default=5.0)

    demo_service = subparsers.add_parser("demo-service", help="Run local demo helper services")
    demo_service_subparsers = demo_service.add_subparsers(dest="demo_service_command")
    demo_serve = demo_service_subparsers.add_parser("serve", help="Run a demo HTTP service")
    demo_serve.add_argument("--service", choices=["mcp", "agent"], required=True)
    demo_serve.add_argument("--host", default="0.0.0.0")
    demo_serve.add_argument("--port", type=int, required=True)
    demo_serve.add_argument("--agent-id", default=None)
    demo_health = demo_service_subparsers.add_parser("health", help="Check a demo service URL")
    demo_health.add_argument("--url", required=True)

    parser.add_argument("--host", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.command == "db":
        runner = MigrationRunner.from_settings(load_settings())
        if args.db_command == "migrate":
            applied = runner.apply_all()
            print(f"Applied migrations: {', '.join(applied) if applied else 'none'}")
            return
        if args.db_command == "rollback":
            version = runner.rollback_last()
            print(f"Rolled back migration: {version or 'none'}")
            return
        if args.db_command == "seed":
            runner.apply_all()
            with runner.connection:
                seed_demo_data(runner.connection)
            print("Seeded demo data")
            return
        if args.db_command == "reset-demo":
            runner.apply_all()
            with runner.connection:
                reset_demo_data(runner.connection, remove_admin=args.remove_admin)
            print("Reset demo data")
            return
        parser.error("db command requires migrate, rollback, seed, or reset-demo")

    if args.command == "worker":
        if args.worker_command == "noop":
            execution = _run_noop_worker_job()
            print(f"Worker no-op job {execution.status}: {execution.result.get('ok')}")
            return
        if args.worker_command == "loop":
            print("Worker loop started")
            try:
                while True:
                    _run_noop_worker_job()
                    time.sleep(args.interval_seconds)
            except KeyboardInterrupt:
                print("Worker loop stopped")
                return
        parser.error("worker command requires noop or loop")

    if args.command == "demo-service":
        if args.demo_service_command == "serve":
            run_demo_http_service(
                service_type=args.service,
                host=args.host,
                port=args.port,
                agent_id=args.agent_id,
            )
            return
        if args.demo_service_command == "health":
            payload = check_demo_http_health(args.url)
            print(f"Demo service healthy: {payload['service']}")
            return
        parser.error("demo-service command requires serve or health")

    host = args.host or "127.0.0.1"
    port = args.port or 8088
    uvicorn.run("product_platform.api.app:app", host=host, port=port, reload=False)


def _run_noop_worker_job():
    """Execute one deterministic worker job for local compose health checks."""

    def handle_noop(context):
        context.log(f"processed {context.job_id}")
        return JobResult(status="succeeded", result={"ok": True})

    registry = JobRegistry()
    registry.register("demo.noop", handle_noop)
    queue = InMemoryJobQueue()
    queue.enqueue(JobRequest(job_type="demo.noop", payload={}))
    execution = Worker(queue, registry).run_once()
    if execution is None:
        raise RuntimeError("No worker job was executed.")
    return execution


if __name__ == "__main__":
    main()
