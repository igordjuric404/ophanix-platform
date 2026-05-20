"""Command-line entrypoint for the product API."""

from __future__ import annotations

import argparse
import os
import socket
import time

import uvicorn

from product_platform.api.app import create_app
from product_platform.api.settings import load_settings
from product_platform.db.connection import Database
from product_platform.db.migrator import MigrationRunner
from product_platform.db.seed import reset_demo_data, seed_demo_data
from product_platform.demo.services import check_demo_http_health, run_demo_http_service
from product_platform.tool_gateway.runtime_audit import purge_tool_invocation_idempotency_records
from product_platform.worker import InMemoryJobQueue, JobRegistry, JobRequest, JobResult, Worker
from product_platform.worker.persistent import ProductPlatformWorker, check_worker_store_ready


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
    cleanup_idempotency = db_subparsers.add_parser(
        "cleanup-idempotency",
        help="Delete expired Tool Gateway idempotency replay records",
    )
    cleanup_idempotency.add_argument(
        "--retention-seconds",
        type=int,
        default=None,
        help="Replay retention window; defaults to OPHANIX_TOOL_GATEWAY_IDEMPOTENCY_REPLAY_RETENTION_SECONDS.",
    )

    worker = subparsers.add_parser("worker", help="Run local worker utilities")
    worker_subparsers = worker.add_subparsers(dest="worker_command")
    worker_subparsers.add_parser("noop", help="Execute one in-memory no-op job")
    worker_subparsers.add_parser("ready", help="Check persistent worker job-store readiness")
    run_once = worker_subparsers.add_parser("run-once", help="Claim and execute one persistent queued job")
    run_once.add_argument("--queue", default=None, help="Optional queue name to consume")
    run_once.add_argument("--worker-id", default=None, help="Stable worker identity for leases")
    run_once.add_argument("--lease-seconds", type=int, default=300)
    loop = worker_subparsers.add_parser("loop", help="Run the persistent worker loop")
    loop.add_argument("--interval-seconds", type=float, default=5.0)
    loop.add_argument("--queue", default=None, help="Optional queue name to consume")
    loop.add_argument("--worker-id", default=None, help="Stable worker identity for leases")
    loop.add_argument("--lease-seconds", type=int, default=300)
    loop.add_argument(
        "--dev-noop",
        action="store_true",
        help="Run the old in-memory no-op loop for local diagnostics only.",
    )

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
                seed_demo_data(runner.connection, include_baseline=True)
            print("Seeded demo data")
            return
        if args.db_command == "reset-demo":
            runner.apply_all()
            with runner.connection:
                reset_demo_data(runner.connection, remove_admin=args.remove_admin)
            print("Reset demo data")
            return
        if args.db_command == "cleanup-idempotency":
            settings = load_settings()
            retention_seconds = (
                args.retention_seconds
                if args.retention_seconds is not None
                else settings.tool_gateway_idempotency_replay_retention_seconds
            )
            if retention_seconds <= 0:
                parser.error("--retention-seconds must be greater than zero")
            runner.apply_all()
            with runner.connection:
                result = purge_tool_invocation_idempotency_records(
                    runner.connection,
                    retention_seconds=retention_seconds,
                    in_progress_ttl_seconds=(
                        settings.tool_gateway_idempotency_in_progress_ttl_seconds
                    ),
                )
            print(f"Marked stale idempotency records unknown: {result.marked_failed_unknown}")
            print(f"Deleted idempotency records: {result.deleted_records}")
            return
        parser.error("db command requires migrate, rollback, seed, reset-demo, or cleanup-idempotency")

    if args.command == "worker":
        if args.worker_command == "noop":
            execution = _run_noop_worker_job()
            print(f"Worker no-op job {execution.status}: {execution.result.get('ok')}")
            return
        if args.worker_command == "ready":
            database = _worker_database()
            try:
                check_worker_store_ready(database)
            finally:
                database.close()
            print("Worker ready: job store reachable")
            return
        if args.worker_command == "run-once":
            database = _worker_database()
            try:
                execution = ProductPlatformWorker(
                    database,
                    queue_name=args.queue,
                    worker_id=args.worker_id or _default_worker_id(),
                    lease_seconds=args.lease_seconds,
                ).run_once()
            finally:
                database.close()
            if execution is None:
                print("Worker found no queued jobs")
            else:
                print(f"Worker job {execution.job_id} {execution.status}")
            return
        if args.worker_command == "loop":
            if args.dev_noop:
                print("Worker dev no-op loop started")
                try:
                    while True:
                        _run_noop_worker_job()
                        time.sleep(args.interval_seconds)
                except KeyboardInterrupt:
                    print("Worker dev no-op loop stopped")
                    return
            database = _worker_database()
            persistent_worker = ProductPlatformWorker(
                database,
                queue_name=args.queue,
                worker_id=args.worker_id or _default_worker_id(),
                lease_seconds=args.lease_seconds,
            )
            print("Worker loop started")
            try:
                while True:
                    execution = persistent_worker.run_once()
                    if execution is not None:
                        print(f"Worker job {execution.job_id} {execution.status}")
                    time.sleep(args.interval_seconds)
            except KeyboardInterrupt:
                print("Worker loop stopped")
                database.close()
                return
            finally:
                database.close()
        parser.error("worker command requires noop, ready, run-once, or loop")

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
    settings = load_settings()
    database = Database(settings.database_url, max_pool_size=int(settings.database_max_pool_size))
    database.migrate()
    uvicorn.run(create_app(settings, database=database), host=host, port=port, reload=False)


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


def _worker_database() -> Database:
    settings = load_settings()
    return Database(settings.database_url, max_pool_size=int(settings.database_max_pool_size))


def _default_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


if __name__ == "__main__":
    main()
