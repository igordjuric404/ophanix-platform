"""Command-line entrypoint for the product API."""

from __future__ import annotations

import argparse

import uvicorn

from product_platform.api.settings import load_settings
from product_platform.db.migrator import MigrationRunner
from product_platform.db.seed import reset_demo_data, seed_demo_data


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

    host = args.host or "127.0.0.1"
    port = args.port or 8088
    uvicorn.run("product_platform.api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
