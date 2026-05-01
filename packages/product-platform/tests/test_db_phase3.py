from __future__ import annotations

import re
import sqlite3
import unittest
from datetime import datetime

from product_platform.db.ids import generate_id
from product_platform.db.repositories import OrganizationRepository
from product_platform.db.testing import create_migrated_test_database
from product_platform.db.time import utc_now_iso


class DatabasePhase3Tests(unittest.TestCase):
    def test_id_generation_format(self) -> None:
        generated = generate_id("org")

        self.assertRegex(generated, re.compile(r"^org_[0-9a-f]{32}$"))

    def test_utc_timestamp_is_timezone_aware(self) -> None:
        timestamp = utc_now_iso()
        parsed = datetime.fromisoformat(timestamp)

        self.assertIsNotNone(parsed.tzinfo)
        self.assertEqual(parsed.utcoffset().total_seconds(), 0)

    def test_unique_constraints_reject_duplicate_organization_slug(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                repository = OrganizationRepository(connection)
                repository.create(organization_id="org_one", name="One", slug="duplicate")
                repository.create(organization_id="org_two", name="Two", slug="duplicate")
        except sqlite3.IntegrityError as exc:
            self.assertIn("UNIQUE", str(exc).upper())
        else:
            self.fail("Expected duplicate organization slug to violate a unique constraint.")
        finally:
            database.close()

    def test_soft_deleted_row_is_excluded_by_default(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                repository = OrganizationRepository(connection)
                repository.create(organization_id="org_deleted", name="Deleted", slug="deleted")
                repository.soft_delete("org_deleted")

            repository = OrganizationRepository(database.connect())
            self.assertIsNone(repository.get("org_deleted"))
            self.assertIsNotNone(repository.get("org_deleted", include_deleted=True))
        finally:
            database.close()


if __name__ == "__main__":
    unittest.main()

