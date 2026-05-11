"""Database connection and transaction management."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from product_platform.db.migrator import MigrationRunner, connect_database


class Database:
    """Small connection manager for the product database."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._connection: sqlite3.Connection | Any | None = None
        self._transaction_lock = threading.RLock()

    def connect(self) -> Any:
        if self._connection is None:
            self._connection = connect_database(self.database_url)
        return self._connection

    def migrate(self) -> list[str]:
        return MigrationRunner(self.connect()).apply_all()

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        with self._transaction_lock:
            connection = self.connect()
            try:
                connection.execute("BEGIN")
                yield connection
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
