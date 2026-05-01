"""Small SQLite migration runner for local product platform development."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from product_platform.api.settings import Settings
from product_platform.db.time import utc_now_iso

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


@dataclass(frozen=True)
class Migration:
    """A database migration with up/down SQL files."""

    version: str
    name: str
    up_sql: str
    down_sql: str


def database_path_from_url(database_url: str) -> str:
    """Resolve a local SQLite path from a database URL."""

    if database_url in {":memory:", "sqlite:///:memory:"}:
        return ":memory:"
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("Only sqlite:/// URLs are supported by the local migration runner.")
    return database_url.removeprefix(prefix)


def is_supported_database_url(database_url: str) -> bool:
    """Return whether the current runtime can connect to this database URL."""

    try:
        database_path_from_url(database_url)
    except ValueError:
        return False
    return True


def connect_database(database_url: str) -> sqlite3.Connection:
    """Open a SQLite connection with product defaults."""

    connection = sqlite3.connect(database_path_from_url(database_url), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


class MigrationRunner:
    """Apply and roll back migrations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    @classmethod
    def from_settings(cls, settings: Settings) -> "MigrationRunner":
        return cls(connect_database(settings.database_url))

    def apply_all(self) -> list[str]:
        applied: list[str] = []
        self._ensure_migration_table()
        for migration in load_migrations():
            if self._is_applied(migration.version):
                continue
            self.connection.executescript(migration.up_sql)
            self.connection.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (migration.version, migration.name, utc_now_iso()),
            )
            self.connection.commit()
            applied.append(migration.version)
        return applied

    def rollback_last(self) -> str | None:
        self._ensure_migration_table()
        row = self.connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        migration = {migration.version: migration for migration in load_migrations()}[row["version"]]
        self.connection.executescript(migration.down_sql)
        if self._table_exists("schema_migrations"):
            self.connection.execute(
                "DELETE FROM schema_migrations WHERE version = ?",
                (migration.version,),
            )
        self.connection.commit()
        return migration.version

    def applied_versions(self) -> list[str]:
        self._ensure_migration_table()
        rows = self.connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        return [row["version"] for row in rows]

    def _ensure_migration_table(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    def _is_applied(self, version: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (version,),
        ).fetchone()
        return row is not None

    def _table_exists(self, table_name: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None


def load_migrations() -> list[Migration]:
    """Load migrations from package SQL files."""

    migrations: list[Migration] = []
    for up_file in sorted(MIGRATIONS_DIR.glob("*.up.sql")):
        stem = up_file.name.removesuffix(".up.sql")
        version, _, name = stem.partition("_")
        down_file = MIGRATIONS_DIR / f"{stem}.down.sql"
        migrations.append(
            Migration(
                version=version,
                name=name,
                up_sql=up_file.read_text(),
                down_sql=down_file.read_text(),
            )
        )
    return migrations
