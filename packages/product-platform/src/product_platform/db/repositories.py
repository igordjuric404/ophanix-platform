"""Repository base classes for product data."""

from __future__ import annotations

from sqlite3 import Connection, Row

from product_platform.db.time import utc_now_iso


class BaseRepository:
    """Base repository with organization scoping helpers."""

    def __init__(self, connection: Connection, organization_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id

    def scoped_filters(self, filters: dict[str, object] | None = None) -> dict[str, object]:
        scoped = dict(filters or {})
        scoped["organization_id"] = self.organization_id
        return scoped

    def soft_delete_by_id(self, table: str, row_id: str) -> None:
        self.connection.execute(
            f"UPDATE {table} SET deleted_at = ?, updated_at = ? WHERE id = ? AND organization_id = ?",
            (utc_now_iso(), utc_now_iso(), row_id, self.organization_id),
        )


class OrganizationRepository:
    """Repository for organization rows."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def create(self, *, organization_id: str, name: str, slug: str) -> None:
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO organizations (id, name, slug, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (organization_id, name, slug, now, now),
        )

    def get(self, organization_id: str, *, include_deleted: bool = False) -> Row | None:
        deleted_clause = "" if include_deleted else "AND deleted_at IS NULL"
        return self.connection.execute(
            f"""
            SELECT * FROM organizations
            WHERE id = ? {deleted_clause}
            """,
            (organization_id,),
        ).fetchone()

    def soft_delete(self, organization_id: str) -> None:
        now = utc_now_iso()
        self.connection.execute(
            "UPDATE organizations SET deleted_at = ?, updated_at = ? WHERE id = ?",
            (now, now, organization_id),
        )


class EnvironmentRepository:
    """Repository for environment rows."""

    def __init__(self, connection: Connection, organization_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id

    def get(self, environment_id: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT * FROM environments
            WHERE id = ? AND organization_id = ? AND deleted_at IS NULL
            """,
            (environment_id, self.organization_id),
        ).fetchone()
