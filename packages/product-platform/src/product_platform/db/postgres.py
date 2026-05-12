"""PostgreSQL connection helpers for product platform repositories."""

from __future__ import annotations

from typing import Any


class DatabaseError(Exception):
    """Base database error exposed to repository callers."""


class DatabaseIntegrityError(DatabaseError):
    """Raised when PostgreSQL rejects a write because of an integrity constraint."""


class DatabaseRow:
    """Small mapping/sequence row object for repository code."""

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
    """Cursor facade over psycopg cursors."""

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


class PostgresConnection:
    """PostgreSQL connection facade used by the repository layer."""

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
            raise DatabaseError(str(exc)) from exc

    def execute(self, sql: str, parameters: Any = ()) -> PostgresCursor:
        translated_sql = translate_sql_for_postgres(sql)
        translated_parameters = () if parameters is None else parameters
        try:
            cursor = self._connection.execute(translated_sql, translated_parameters)
        except self._psycopg.IntegrityError as exc:
            raise DatabaseIntegrityError(str(exc)) from exc
        except self._psycopg.Error as exc:
            raise DatabaseError(str(exc)) from exc
        return PostgresCursor(cursor)

    def executemany(self, sql: str, parameter_rows: Any) -> PostgresCursor:
        translated_sql = translate_sql_for_postgres(sql)
        try:
            cursor = self._connection.cursor()
            cursor.executemany(translated_sql, parameter_rows)
        except self._psycopg.IntegrityError as exc:
            raise DatabaseIntegrityError(str(exc)) from exc
        except self._psycopg.Error as exc:
            raise DatabaseError(str(exc)) from exc
        return PostgresCursor(cursor)

    def executescript(self, sql_script: str) -> None:
        for statement in split_sql_script(sql_script):
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


Connection = PostgresConnection
Row = DatabaseRow
IntegrityError = DatabaseIntegrityError


def translate_sql_for_postgres(sql: str) -> str:
    """Normalize repository SQL to psycopg's parameter style."""

    translated = _replace_qmark_placeholders(sql)
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
