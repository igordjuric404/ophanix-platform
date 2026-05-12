"""Helpers for deterministic PostgreSQL integration tests."""

from __future__ import annotations

import os
from uuid import uuid4
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

from product_platform.api.settings import DEFAULT_POSTGRES_URL
from product_platform.db.connection import Database
from product_platform.db.postgres import Connection


def test_postgres_url() -> str:
    """Return the PostgreSQL URL used by tests."""

    return os.environ.get("OPHANIX_TEST_POSTGRES_URL") or os.environ.get(
        "OPHANIX_DATABASE_URL",
        DEFAULT_POSTGRES_URL,
    )


def postgres_url_with_schema(database_url: str, schema_name: str) -> str:
    """Return a PostgreSQL URL that starts sessions in a dedicated schema."""

    parsed = urlparse(database_url)
    query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query_items["options"] = f"-c search_path={schema_name},public"
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query_items, quote_via=quote),
            parsed.fragment,
        )
    )


def create_test_schema(database_url: str, schema_name: str) -> None:
    """Create an isolated PostgreSQL schema for a test database."""

    try:
        import psycopg
        from psycopg import sql
    except ImportError as exc:  # pragma: no cover - packaging guard
        raise RuntimeError("psycopg is required for PostgreSQL tests.") from exc

    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema_name)))


def drop_test_schema(database_url: str, schema_name: str) -> None:
    """Drop an isolated PostgreSQL schema created for a test database."""

    try:
        import psycopg
        from psycopg import sql
    except ImportError as exc:  # pragma: no cover - packaging guard
        raise RuntimeError("psycopg is required for PostgreSQL tests.") from exc

    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema_name)))


def create_test_database(*, migrate: bool = True) -> Database:
    """Create an isolated PostgreSQL-backed database manager for tests."""

    base_url = test_postgres_url()
    schema_name = f"ophanix_test_{uuid4().hex}"
    create_test_schema(base_url, schema_name)
    database = Database(
        postgres_url_with_schema(base_url, schema_name),
        cleanup=lambda: drop_test_schema(base_url, schema_name),
    )
    if migrate:
        database.migrate()
    return database


def create_migrated_test_database() -> Database:
    """Create an isolated migrated PostgreSQL database for tests."""

    return create_test_database(migrate=True)


def table_names(connection: Connection) -> set[str]:
    """Return tables visible in the current PostgreSQL search path."""

    rows = connection.execute(
        """
        SELECT table_name AS name
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_type = 'BASE TABLE'
        """
    ).fetchall()
    return {row["name"] for row in rows}


def column_names(connection: Connection, table_name: str) -> set[str]:
    """Return column names for a table visible in the current PostgreSQL search path."""

    rows = connection.execute(
        """
        SELECT column_name AS name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = ?
        ORDER BY ordinal_position
        """,
        (table_name,),
    ).fetchall()
    return {row["name"] for row in rows}
