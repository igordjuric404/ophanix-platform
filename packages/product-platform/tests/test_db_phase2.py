from __future__ import annotations

import unittest

from product_platform.db.repositories import BaseRepository, OrganizationRepository
from product_platform.db.testing import create_migrated_test_database


class DatabasePhase2Tests(unittest.TestCase):
    def test_repository_scope_helper_applies_organization_id(self) -> None:
        database = create_migrated_test_database()
        try:
            repository = BaseRepository(database.connect(), "org_default")

            filters = repository.scoped_filters({"status": "active", "organization_id": "org_other"})

            self.assertEqual(filters["status"], "active")
            self.assertEqual(filters["organization_id"], "org_default")
        finally:
            database.close()

    def test_integration_writes_and_reads_organization(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                organizations = OrganizationRepository(connection)
                organizations.create(
                    organization_id="org_test",
                    name="Test Org",
                    slug="test-org",
                )

            row = OrganizationRepository(database.connect()).get("org_test")

            self.assertIsNotNone(row)
            self.assertEqual(row["name"], "Test Org")
        finally:
            database.close()

    def test_transaction_rolls_back_on_exception(self) -> None:
        database = create_migrated_test_database()
        try:
            with self.assertRaises(RuntimeError):
                with database.transaction() as connection:
                    organizations = OrganizationRepository(connection)
                    organizations.create(
                        organization_id="org_rollback",
                        name="Rollback Org",
                        slug="rollback-org",
                    )
                    raise RuntimeError("force rollback")

            row = OrganizationRepository(database.connect()).get("org_rollback")

            self.assertIsNone(row)
        finally:
            database.close()


if __name__ == "__main__":
    unittest.main()

