"""Seed and reset helpers for local demo data."""

from __future__ import annotations

from sqlite3 import Connection

from product_platform.db.time import utc_now_iso
from product_platform.integrations.catalog import seed_framework_catalog
from product_platform.workflows.catalog import seed_workflow_catalog

DEMO_ORG_ID = "org_default"
DEMO_ENV_ID = "env_default"
DEMO_ADMIN_USER_ID = "user_admin"
DEMO_ADMIN_EMAIL = "admin@ophanix.local"


def seed_demo_data(connection: Connection) -> None:
    """Seed local demo organization, environment, admin user, and policy placeholders."""

    now = utc_now_iso()
    connection.execute(
        """
        INSERT OR IGNORE INTO organizations (id, name, slug, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (DEMO_ORG_ID, "Ophanix Demo", "ophanix-demo", now, now),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO environments
            (id, organization_id, name, slug, type, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (DEMO_ENV_ID, DEMO_ORG_ID, "Development", "development", "development", now, now),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO users (id, email, display_name, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (DEMO_ADMIN_USER_ID, DEMO_ADMIN_EMAIL, "Demo Admin", "active", now, now),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO organization_memberships
            (organization_id, user_id, role, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (DEMO_ORG_ID, DEMO_ADMIN_USER_ID, "Platform Admin", "active", now, now),
    )
    for policy_id, name, description in [
        ("policy_placeholder_default_allow", "Default Allow", "Demo allow policy placeholder."),
        ("policy_placeholder_sensitive_tools", "Sensitive Tools", "Demo sensitive tool policy placeholder."),
    ]:
        connection.execute(
            """
            INSERT OR IGNORE INTO policy_placeholders
                (id, organization_id, environment_id, name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (policy_id, DEMO_ORG_ID, DEMO_ENV_ID, name, description, now, now),
        )
    seed_framework_catalog(connection)
    seed_workflow_catalog(connection, DEMO_ORG_ID)


def reset_demo_data(connection: Connection, *, remove_admin: bool = False) -> None:
    """Reset demo-only rows while preserving the admin user by default."""

    connection.execute("DELETE FROM policy_placeholders WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM workflow_runs WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM audit_events WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM api_keys WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM auth_sessions WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM organization_memberships WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM environments WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM organizations WHERE id = ?", (DEMO_ORG_ID,))
    if remove_admin:
        connection.execute("DELETE FROM users WHERE id = ?", (DEMO_ADMIN_USER_ID,))
