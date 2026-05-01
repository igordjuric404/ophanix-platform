"""Seed and reset helpers for local demo data."""

from __future__ import annotations

from sqlite3 import Connection

from product_platform.db.time import utc_now_iso
from product_platform.demo.baseline import DEMO_BASELINE_AGENT_IDS, DEMO_BASELINE_MCP_SERVER_ID
from product_platform.demo.catalog import seed_demo_scenarios
from product_platform.integrations.catalog import seed_framework_catalog
from product_platform.workflows.catalog import seed_workflow_catalog

DEMO_ORG_ID = "org_default"
DEMO_ENV_ID = "env_default"
DEMO_ADMIN_USER_ID = "user_admin"
DEMO_ADMIN_EMAIL = "admin@ophanix.local"


def seed_demo_data(connection: Connection, *, include_baseline: bool = False) -> None:
    """Seed local demo organization, environment, admin user, and shared catalogs."""

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
    seed_demo_scenarios(connection, DEMO_ORG_ID, DEMO_ENV_ID)
    if include_baseline:
        seed_demo_baseline_fixtures(connection)


def seed_demo_baseline_fixtures(connection: Connection) -> None:
    """Seed optional baseline fixtures used by Demo Lab prerequisite checks."""

    now = utc_now_iso()
    for agent_id, name, description in [
        (
            DEMO_BASELINE_AGENT_IDS[0],
            "Demo Support Agent",
            "Handles customer-support intake in the refund demo.",
        ),
        (
            DEMO_BASELINE_AGENT_IDS[1],
            "Demo Refund Agent",
            "Executes refund policy decisions in the refund demo.",
        ),
        (
            DEMO_BASELINE_AGENT_IDS[2],
            "Demo Supervisor Agent",
            "Approves escalations in the refund demo.",
        ),
    ]:
        connection.execute(
            """
            INSERT OR IGNORE INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, endpoint_url, owner_user_id, sponsor_user_id, status,
                trust_score, trust_tier, credential_status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                DEMO_ORG_ID,
                DEMO_ENV_ID,
                name,
                description,
                "demo",
                "simulated",
                f"https://demo.ophanix.local/agents/{agent_id}",
                DEMO_ADMIN_USER_ID,
                DEMO_ADMIN_USER_ID,
                "active",
                85.0,
                "trusted",
                "issued",
                now,
                now,
            ),
        )
    connection.execute(
        """
        INSERT OR IGNORE INTO mcp_servers (
            id, organization_id, environment_id, name, endpoint_url,
            owner_user_id, auth_type, status, policy_pack_id, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            DEMO_BASELINE_MCP_SERVER_ID,
            DEMO_ORG_ID,
            DEMO_ENV_ID,
            "Demo Refund MCP",
            "https://demo.ophanix.local/mcp/refunds",
            DEMO_ADMIN_USER_ID,
            "none",
            "active",
            None,
            now,
            now,
        ),
    )


def reset_demo_data(connection: Connection, *, remove_admin: bool = False) -> None:
    """Reset demo-only rows while preserving the admin user by default."""

    connection.execute(
        """
        DELETE FROM demo_step_runs
        WHERE demo_run_id IN (
            SELECT id FROM demo_runs WHERE organization_id = ?
        )
        """,
        (DEMO_ORG_ID,),
    )
    connection.execute("DELETE FROM demo_runs WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute(
        """
        DELETE FROM demo_steps
        WHERE scenario_id IN (
            SELECT id FROM demo_scenarios WHERE organization_id = ?
        )
        """,
        (DEMO_ORG_ID,),
    )
    connection.execute("DELETE FROM demo_scenarios WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM mcp_servers WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM agents WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM policy_placeholders WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM workflow_runs WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM workflow_definitions WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute(
        """
        DELETE FROM audit_event_hashes
        WHERE event_id IN (
            SELECT id FROM audit_events WHERE organization_id = ?
        )
        """,
        (DEMO_ORG_ID,),
    )
    connection.execute("DELETE FROM audit_events WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM api_keys WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM auth_sessions WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM organization_memberships WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM environments WHERE organization_id = ?", (DEMO_ORG_ID,))
    connection.execute("DELETE FROM organizations WHERE id = ?", (DEMO_ORG_ID,))
    if remove_admin:
        connection.execute("DELETE FROM users WHERE id = ?", (DEMO_ADMIN_USER_ID,))
