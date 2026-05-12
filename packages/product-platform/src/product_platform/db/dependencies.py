"""FastAPI database dependencies."""

from __future__ import annotations

from collections.abc import Iterator
from product_platform.db.postgres import Connection

from fastapi import Request

from product_platform.db.connection import Database


def get_database(request: Request) -> Database:
    """Return the app database manager."""

    database = getattr(request.app.state, "database", None)
    if not isinstance(database, Database):
        raise RuntimeError("Database is not configured on app.state.database.")
    return database


def transaction_dependency(request: Request) -> Iterator[Connection]:
    """Yield a request-scoped transaction."""

    with get_database(request).transaction() as connection:
        yield connection

