"""Database connection and transaction management."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from product_platform.db.migrator import MigrationRunner, connect_database
from product_platform.db.postgres import Connection


class Database:
    """Small connection manager for the product database."""

    def __init__(self, database_url: str, *, cleanup: Callable[[], None] | None = None) -> None:
        self.database_url = database_url
        self._connection: Connection | None = None
        self._cleanup = cleanup
        self._transaction_lock = threading.RLock()

    def connect(self) -> Connection:
        if self._connection is None:
            self._connection = connect_database(self.database_url)
        return self._connection

    def migrate(self) -> list[str]:
        return MigrationRunner(self.connect()).apply_all()

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
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
        if self._cleanup is not None:
            cleanup = self._cleanup
            self._cleanup = None
            cleanup()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
