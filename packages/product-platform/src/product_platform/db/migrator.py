"""Migration runner and connection helpers for product platform PostgreSQL databases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from product_platform.api.settings import Settings
from product_platform.db.postgres import Connection, PostgresConnection
from product_platform.db.time import utc_now_iso

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
MIGRATION_ADVISORY_LOCK_ID = 731_947_560_431


@dataclass(frozen=True)
class Migration:
    """A database migration with up/down SQL files."""

    version: str
    name: str
    up_sql: str
    down_sql: str


def database_backend_from_url(database_url: str) -> str:
    """Return the supported database backend for a URL."""

    parsed = urlparse(database_url)
    if parsed.scheme in {"postgresql", "postgres"} and parsed.hostname:
        return "postgresql"
    raise ValueError("OPHANIX_DATABASE_URL must be a postgresql:// URL.")


def is_supported_database_url(database_url: str) -> bool:
    """Return whether the current runtime can connect to this database URL."""

    try:
        database_backend_from_url(database_url)
    except ValueError:
        return False
    return True


def connect_database(database_url: str) -> Connection:
    """Open a PostgreSQL database connection with product defaults."""

    database_backend_from_url(database_url)
    return PostgresConnection(database_url)


class MigrationRunner:
    """Apply and roll back migrations."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    @classmethod
    def from_settings(cls, settings: Settings) -> "MigrationRunner":
        return cls(connect_database(settings.database_url))

    def apply_all(self) -> list[str]:
        applied: list[str] = []
        self._acquire_migration_lock()
        try:
            self._ensure_migration_table()
            for migration in load_migrations():
                if self._is_applied(migration.version):
                    continue
                try:
                    self.connection.execute("BEGIN")
                    self.connection.executescript(migration.up_sql)
                    self.connection.execute(
                        "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                        (migration.version, migration.name, utc_now_iso()),
                    )
                    self.connection.commit()
                except Exception:
                    self.connection.rollback()
                    raise
                applied.append(migration.version)
            return applied
        finally:
            self._release_migration_lock()

    def rollback_last(self) -> str | None:
        self._ensure_migration_table()
        row = self.connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        migration = {migration.version: migration for migration in load_migrations()}[row["version"]]
        self._acquire_migration_lock()
        try:
            try:
                self.connection.execute("BEGIN")
                self.connection.executescript(migration.down_sql)
                if self._table_exists("schema_migrations"):
                    self.connection.execute(
                        "DELETE FROM schema_migrations WHERE version = ?",
                        (migration.version,),
                    )
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise
        finally:
            self._release_migration_lock()
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

    def _acquire_migration_lock(self) -> None:
        self.connection.execute("SELECT pg_advisory_lock(?)", (MIGRATION_ADVISORY_LOCK_ID,))
        self.connection.commit()

    def _release_migration_lock(self) -> None:
        try:
            self.connection.execute("SELECT pg_advisory_unlock(?)", (MIGRATION_ADVISORY_LOCK_ID,))
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def _table_exists(self, table_name: str) -> bool:
        row = self.connection.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name = ?
            LIMIT 1
            """,
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
