from __future__ import annotations

import unittest

from product_platform.db.repositories import EnvironmentRepository, OrganizationRepository
from product_platform.db.seed import (
    DEMO_ADMIN_USER_ID,
    DEMO_ENV_ID,
    DEMO_ORG_ID,
    reset_demo_data,
    seed_demo_data,
)
from product_platform.db.testing import create_migrated_test_database


class DatabasePhase4Tests(unittest.TestCase):
    def test_seed_is_idempotent(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                seed_demo_data(connection)

            connection = database.connect()
            org_count = connection.execute("SELECT COUNT(*) AS count FROM organizations").fetchone()[
                "count"
            ]
            env_count = connection.execute("SELECT COUNT(*) AS count FROM environments").fetchone()[
                "count"
            ]
            user_count = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
            policy_count = connection.execute(
                "SELECT COUNT(*) AS count FROM policy_placeholders"
            ).fetchone()["count"]

            self.assertEqual(org_count, 1)
            self.assertEqual(env_count, 1)
            self.assertEqual(user_count, 1)
            self.assertEqual(policy_count, 2)
        finally:
            database.close()

    def test_seeded_organization_and_environment_are_available_through_repositories(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)

            connection = database.connect()
            organization = OrganizationRepository(connection).get(DEMO_ORG_ID)
            environment = EnvironmentRepository(connection, DEMO_ORG_ID).get(DEMO_ENV_ID)

            self.assertIsNotNone(organization)
            self.assertIsNotNone(environment)
            self.assertEqual(organization["slug"], "ophanix-demo")
            self.assertEqual(environment["slug"], "development")
        finally:
            database.close()

    def test_reset_preserves_admin_user_unless_explicitly_requested(self) -> None:
        database = create_migrated_test_database()
        try:
            with database.transaction() as connection:
                seed_demo_data(connection)
                reset_demo_data(connection)

            admin_count = database.connect().execute(
                "SELECT COUNT(*) AS count FROM users WHERE id = ?",
                (DEMO_ADMIN_USER_ID,),
            ).fetchone()["count"]
            org_count = database.connect().execute(
                "SELECT COUNT(*) AS count FROM organizations WHERE id = ?",
                (DEMO_ORG_ID,),
            ).fetchone()["count"]

            self.assertEqual(admin_count, 1)
            self.assertEqual(org_count, 0)

            with database.transaction() as connection:
                reset_demo_data(connection, remove_admin=True)

            admin_count_after_remove = database.connect().execute(
                "SELECT COUNT(*) AS count FROM users WHERE id = ?",
                (DEMO_ADMIN_USER_ID,),
            ).fetchone()["count"]
            self.assertEqual(admin_count_after_remove, 0)
        finally:
            database.close()


if __name__ == "__main__":
    unittest.main()

