"""Database connection and transaction management."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from queue import Empty, LifoQueue

from product_platform.db.migrator import MigrationRunner, connect_database
from product_platform.db.postgres import Connection


class Database:
    """Small connection manager for the product database."""

    def __init__(
        self,
        database_url: str,
        *,
        cleanup: Callable[[], None] | None = None,
        max_pool_size: int = 5,
        checkout_timeout_seconds: float = 30.0,
    ) -> None:
        if max_pool_size <= 0:
            raise ValueError("max_pool_size must be greater than zero.")
        if checkout_timeout_seconds <= 0:
            raise ValueError("checkout_timeout_seconds must be greater than zero.")
        self.database_url = database_url
        self._connection: Connection | None = None
        self._cleanup = cleanup
        self._max_pool_size = max_pool_size
        self._checkout_timeout_seconds = checkout_timeout_seconds
        self._pool: LifoQueue[Connection] = LifoQueue()
        self._pool_lock = threading.Lock()
        self._pool_connections = 0
        self._local = threading.local()
        self._closed = False

    def connect(self) -> Connection:
        if self._connection is None:
            self._connection = connect_database(self.database_url)
        return self._connection

    def migrate(self) -> list[str]:
        connection = self._checkout_connection()
        try:
            return MigrationRunner(connection).apply_all()
        finally:
            self._release_connection(connection)

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        existing = getattr(self._local, "connection", None)
        if existing is not None:
            self._local.depth = int(getattr(self._local, "depth", 1)) + 1
            try:
                yield existing
            finally:
                self._local.depth -= 1
            return

        connection = self._checkout_connection()
        self._local.connection = connection
        self._local.depth = 1
        try:
            connection.execute("BEGIN")
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            self._local.depth = 0
            self._local.connection = None
            self._release_connection(connection)

    def close(self) -> None:
        self._closed = True
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        while True:
            try:
                connection = self._pool.get_nowait()
            except Empty:
                break
            connection.close()
        self._pool_connections = 0
        if self._cleanup is not None:
            cleanup = self._cleanup
            self._cleanup = None
            cleanup()

    def _checkout_connection(self) -> Connection:
        if self._closed:
            raise RuntimeError("Database connection manager is closed.")
        try:
            return self._pool.get_nowait()
        except Empty:
            with self._pool_lock:
                if self._pool_connections < self._max_pool_size:
                    self._pool_connections += 1
                    try:
                        return connect_database(self.database_url)
                    except Exception:
                        self._pool_connections -= 1
                        raise
            try:
                return self._pool.get(timeout=self._checkout_timeout_seconds)
            except Empty as exc:
                raise TimeoutError("Timed out waiting for a database connection.") from exc

    def _release_connection(self, connection: Connection) -> None:
        if self._closed:
            connection.close()
            return
        self._pool.put(connection)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
