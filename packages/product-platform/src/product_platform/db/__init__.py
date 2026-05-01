"""Database foundation for the product platform."""

from __future__ import annotations

from product_platform.db.connection import Database
from product_platform.db.migrator import MigrationRunner, connect_database

__all__ = ["Database", "MigrationRunner", "connect_database"]
