"""Migration runner and connection helpers for product platform databases."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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


def database_backend_from_url(database_url: str) -> str:
    """Return the supported database backend for a URL."""

    if database_url in {":memory:", "sqlite:///:memory:"} or database_url.startswith("sqlite:///"):
        return "sqlite"
    parsed = urlparse(database_url)
    if parsed.scheme in {"postgresql", "postgres"} and parsed.hostname:
        return "postgresql"
    raise ValueError("OPHANIX_DATABASE_URL must be a sqlite:/// or postgresql:// URL.")


def is_supported_database_url(database_url: str) -> bool:
    """Return whether the current runtime can connect to this database URL."""

    try:
        database_backend_from_url(database_url)
    except ValueError:
        return False
    return True


def connect_database(database_url: str) -> Any:
    """Open a database connection with product defaults."""

    if database_backend_from_url(database_url) == "postgresql":
        return PostgresConnection(database_url)
    connection = sqlite3.connect(database_path_from_url(database_url), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


class MigrationRunner:
    """Apply and roll back migrations."""

    def __init__(self, connection: Any) -> None:
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


class DatabaseRow:
    """Small sqlite.Row-compatible mapping used by the Postgres adapter."""

    def __init__(self, columns: list[str], values: tuple[Any, ...]) -> None:
        self._columns = columns
        self._values = values
        self._by_name = dict(zip(columns, values, strict=False))

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._by_name[key]

    def __iter__(self) -> Any:
        return iter(self._by_name)

    def __len__(self) -> int:
        return len(self._values)

    def __contains__(self, key: object) -> bool:
        return key in self._by_name

    def keys(self) -> list[str]:
        return list(self._columns)

    def items(self) -> Any:
        return self._by_name.items()

    def values(self) -> Any:
        return self._by_name.values()

    def get(self, key: str, default: Any = None) -> Any:
        return self._by_name.get(key, default)

    def __repr__(self) -> str:
        return repr(self._by_name)


class PostgresCursor:
    """sqlite-style cursor facade over psycopg cursors."""

    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor
        self.rowcount = cursor.rowcount
        self._columns = [column.name for column in cursor.description or []]

    def fetchone(self) -> DatabaseRow | None:
        row = self._cursor.fetchone()
        if row is None:
            return None
        return DatabaseRow(self._columns, tuple(row))

    def fetchall(self) -> list[DatabaseRow]:
        return [DatabaseRow(self._columns, tuple(row)) for row in self._cursor.fetchall()]

    def __iter__(self) -> Any:
        for row in self._cursor:
            yield DatabaseRow(self._columns, tuple(row))


class StaticCursor:
    """Cursor facade for translated compatibility queries."""

    def __init__(self, rows: list[DatabaseRow]) -> None:
        self._rows = rows
        self.rowcount = len(rows)

    def fetchone(self) -> DatabaseRow | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[DatabaseRow]:
        return list(self._rows)

    def __iter__(self) -> Any:
        return iter(self._rows)


class PostgresConnection:
    """sqlite-compatible connection facade for the repository layer.

    The product repositories currently use sqlite-style placeholders and row
    access. This adapter keeps that public surface stable while allowing the
    same repositories and migration runner to execute against PostgreSQL.
    """

    backend = "postgresql"

    def __init__(self, database_url: str) -> None:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - packaging guard
            raise RuntimeError(
                "PostgreSQL database URLs require the psycopg package. "
                "Install ophanix-product-platform with its runtime dependencies."
            ) from exc

        self.database_url = database_url
        self._psycopg = psycopg
        try:
            self._connection = psycopg.connect(database_url)
        except psycopg.Error as exc:
            raise sqlite3.DatabaseError(str(exc)) from exc

    def execute(self, sql: str, parameters: Any = ()) -> PostgresCursor | StaticCursor:
        pragma_result = self._execute_compatibility_query(sql, parameters)
        if pragma_result is not None:
            return pragma_result
        translated_sql = translate_sql_for_postgres(sql)
        translated_parameters = () if parameters is None else parameters
        try:
            cursor = self._connection.execute(translated_sql, translated_parameters)
        except self._psycopg.IntegrityError as exc:
            raise sqlite3.IntegrityError(str(exc)) from exc
        except self._psycopg.Error as exc:
            raise sqlite3.DatabaseError(str(exc)) from exc
        return PostgresCursor(cursor)

    def executemany(self, sql: str, parameter_rows: Any) -> PostgresCursor:
        translated_sql = translate_sql_for_postgres(sql)
        try:
            cursor = self._connection.cursor()
            cursor.executemany(translated_sql, parameter_rows)
        except self._psycopg.IntegrityError as exc:
            raise sqlite3.IntegrityError(str(exc)) from exc
        except self._psycopg.Error as exc:
            raise sqlite3.DatabaseError(str(exc)) from exc
        return PostgresCursor(cursor)

    def executescript(self, sql_script: str) -> None:
        translated_script = translate_script_for_postgres(sql_script)
        for statement in split_sql_script(translated_script):
            self.execute(statement)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "PostgresConnection":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()

    def _execute_compatibility_query(self, sql: str, parameters: Any) -> StaticCursor | None:
        normalized = " ".join(sql.strip().split()).lower()
        if normalized.startswith("pragma table_info("):
            table_name = sql.strip()[len("PRAGMA table_info(") :].rstrip(")").strip()
            rows = self._connection.execute(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = ANY (current_schemas(false))
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table_name,),
            ).fetchall()
            return StaticCursor(
                [
                    DatabaseRow(
                        ["cid", "name", "type", "notnull", "dflt_value", "pk"],
                        (
                            index,
                            row[0],
                            row[1],
                            1 if row[2] == "NO" else 0,
                            row[3],
                            0,
                        ),
                    )
                    for index, row in enumerate(rows)
                ]
            )
        if "from sqlite_master" in normalized:
            table_name = parameters[0] if parameters else ""
            row = self._connection.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = ANY (current_schemas(false))
                  AND table_name = %s
                LIMIT 1
                """,
                (table_name,),
            ).fetchone()
            return StaticCursor([DatabaseRow(["1"], (1,))] if row is not None else [])
        return None


def translate_script_for_postgres(sql_script: str) -> str:
    """Translate known SQLite migration patterns into PostgreSQL DDL."""

    if "tool_runtime_actions_new" in sql_script and "PRAGMA foreign_keys" in sql_script:
        if "CAST(latency_ms AS INTEGER)" in sql_script:
            return """
            ALTER TABLE tool_runtime_actions
                ALTER COLUMN latency_ms TYPE INTEGER
                USING latency_ms::integer;
            """
        return """
        ALTER TABLE tool_runtime_actions
            ALTER COLUMN latency_ms TYPE DOUBLE PRECISION
            USING latency_ms::double precision;
        """
    return "\n".join(
        line
        for line in sql_script.splitlines()
        if not line.strip().upper().startswith("PRAGMA ")
    )


def translate_sql_for_postgres(sql: str) -> str:
    """Translate sqlite-style SQL used by repositories into PostgreSQL SQL."""

    translated = _replace_qmark_placeholders(sql)
    translated = _replace_insert_or_ignore(translated)
    translated = _quote_postgres_reserved_identifiers(translated)
    return translated


def split_sql_script(sql_script: str) -> list[str]:
    """Split a SQL script into statements outside quoted string literals."""

    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_double_quote = False
    index = 0
    while index < len(sql_script):
        char = sql_script[index]
        if char == "'" and not in_double_quote:
            current.append(char)
            if in_single_quote and index + 1 < len(sql_script) and sql_script[index + 1] == "'":
                index += 1
                current.append(sql_script[index])
            else:
                in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            current.append(char)
        elif char == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
        index += 1
    statement = "".join(current).strip()
    if statement:
        statements.append(statement)
    return statements


def _replace_qmark_placeholders(sql: str) -> str:
    result: list[str] = []
    in_single_quote = False
    in_double_quote = False
    index = 0
    while index < len(sql):
        char = sql[index]
        if char == "'" and not in_double_quote:
            result.append(char)
            if in_single_quote and index + 1 < len(sql) and sql[index + 1] == "'":
                index += 1
                result.append(sql[index])
            else:
                in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            result.append(char)
        elif char == "?" and not in_single_quote and not in_double_quote:
            result.append("%s")
        else:
            result.append(char)
        index += 1
    return "".join(result)


def _replace_insert_or_ignore(sql: str) -> str:
    upper = sql.upper()
    marker = "INSERT OR IGNORE INTO"
    if marker not in upper:
        return sql
    marker_index = upper.index(marker)
    values_index = upper.rfind("VALUES")
    if values_index == -1:
        return sql.replace("INSERT OR IGNORE INTO", "INSERT INTO")
    return (
        sql[:marker_index]
        + "INSERT INTO"
        + sql[marker_index + len(marker) :]
        + " ON CONFLICT DO NOTHING"
    )


def _quote_postgres_reserved_identifiers(sql: str) -> str:
    return _replace_word_outside_quotes(sql, "window", '"window"')


def _replace_word_outside_quotes(sql: str, word: str, replacement: str) -> str:
    result: list[str] = []
    in_single_quote = False
    in_double_quote = False
    index = 0
    word_length = len(word)
    while index < len(sql):
        char = sql[index]
        if char == "'" and not in_double_quote:
            result.append(char)
            if in_single_quote and index + 1 < len(sql) and sql[index + 1] == "'":
                index += 1
                result.append(sql[index])
            else:
                in_single_quote = not in_single_quote
            index += 1
            continue
        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            result.append(char)
            index += 1
            continue
        if (
            not in_single_quote
            and not in_double_quote
            and sql[index : index + word_length].lower() == word
            and (index == 0 or not _is_identifier_char(sql[index - 1]))
            and (index + word_length == len(sql) or not _is_identifier_char(sql[index + word_length]))
        ):
            result.append(replacement)
            index += word_length
            continue
        result.append(char)
        index += 1
    return "".join(result)


def _is_identifier_char(char: str) -> bool:
    return char.isalnum() or char == "_"
