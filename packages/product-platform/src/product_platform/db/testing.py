"""Helpers for deterministic database integration tests."""

from __future__ import annotations

from product_platform.db.connection import Database


def create_migrated_test_database() -> Database:
    """Create an in-memory migrated database for tests."""

    database = Database("sqlite:///:memory:")
    database.migrate()
    return database

