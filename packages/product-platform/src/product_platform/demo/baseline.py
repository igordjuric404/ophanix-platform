"""Reusable Demo Lab baseline prerequisite checks."""

from __future__ import annotations

from product_platform.db.postgres import Connection

from product_platform.db.time import utc_now_iso
from product_platform.demo.catalog import CUSTOMER_SUPPORT_REFUND_SCENARIO
from product_platform.demo.models import DemoBaselineCheck, DemoBaselineStatusResponse

DEMO_BASELINE_AGENT_IDS = (
    "agent_demo_support",
    "agent_demo_refund",
    "agent_demo_supervisor",
)
DEMO_BASELINE_MCP_SERVER_ID = "mcp_demo_refund"


def demo_baseline_status(
    connection: Connection,
    *,
    organization_id: str,
    environment_id: str,
) -> DemoBaselineStatusResponse:
    """Return the current health of the local demo baseline."""

    checks = [
        _policy_pack_check(connection, organization_id, environment_id),
        _scenario_check(connection, organization_id, environment_id),
        _sample_agents_check(connection, organization_id, environment_id),
        _mcp_server_check(connection, organization_id, environment_id),
        _provider_credentials_check(connection, organization_id),
    ]
    missing_items = [
        item
        for check in checks
        if check.required and check.status != "healthy"
        for item in check.missing
    ]
    return DemoBaselineStatusResponse(
        organization_id=organization_id,
        environment_id=environment_id,
        overall_status="degraded" if missing_items else "healthy",
        checked_at=utc_now_iso(),
        checks=checks,
        missing_items=missing_items,
    )


def _policy_pack_check(
    connection: Connection,
    organization_id: str,
    environment_id: str,
) -> DemoBaselineCheck:
    expected_ids = {
        "policy_placeholder_default_allow",
        "policy_placeholder_sensitive_tools",
    }
    rows = connection.execute(
        """
        SELECT id
        FROM policy_placeholders
        WHERE organization_id = ? AND environment_id = ?
        """,
        (organization_id, environment_id),
    ).fetchall()
    found_ids = {row["id"] for row in rows}
    missing = sorted(expected_ids - found_ids)
    return DemoBaselineCheck(
        key="policy-pack",
        label="Seed policy pack",
        status="degraded" if missing else "healthy",
        required=True,
        detail="Required demo policy placeholders are loaded."
        if not missing
        else "Required demo policy placeholders are missing.",
        count=len(found_ids),
        expected_count=len(expected_ids),
        missing=missing,
    )


def _scenario_check(
    connection: Connection,
    organization_id: str,
    environment_id: str,
) -> DemoBaselineCheck:
    row = connection.execute(
        """
        SELECT sc.id, COUNT(ds.id) AS step_count
        FROM demo_scenarios sc
        LEFT JOIN demo_steps ds ON ds.scenario_id = sc.id
        WHERE sc.id = ?
          AND sc.organization_id = ?
          AND sc.environment_id = ?
        GROUP BY sc.id
        """,
        (CUSTOMER_SUPPORT_REFUND_SCENARIO["id"], organization_id, environment_id),
    ).fetchone()
    expected_steps = len(CUSTOMER_SUPPORT_REFUND_SCENARIO["steps"])
    count = int(row["step_count"]) if row is not None else 0
    missing: list[str] = []
    if row is None:
        missing.append(CUSTOMER_SUPPORT_REFUND_SCENARIO["id"])
    if row is not None and count != expected_steps:
        missing.append("customer-support-refund steps")
    return DemoBaselineCheck(
        key="demo-scenario",
        label="Customer support refund scenario",
        status="degraded" if missing else "healthy",
        required=True,
        detail="Scenario and ordered steps are loaded."
        if not missing
        else "Scenario definition or ordered steps are incomplete.",
        count=count,
        expected_count=expected_steps,
        missing=missing,
    )


def _sample_agents_check(
    connection: Connection,
    organization_id: str,
    environment_id: str,
) -> DemoBaselineCheck:
    rows = connection.execute(
        """
        SELECT id
        FROM agents
        WHERE organization_id = ?
          AND environment_id = ?
          AND id IN (?, ?, ?)
          AND deleted_at IS NULL
        """,
        (organization_id, environment_id, *DEMO_BASELINE_AGENT_IDS),
    ).fetchall()
    found_ids = {row["id"] for row in rows}
    missing = [agent_id for agent_id in DEMO_BASELINE_AGENT_IDS if agent_id not in found_ids]
    return DemoBaselineCheck(
        key="sample-agents",
        label="Sample demo agents",
        status="degraded" if missing else "healthy",
        required=True,
        detail="Sample support, refund, and supervisor agents are registered."
        if not missing
        else "One or more sample demo agents are missing.",
        count=len(found_ids),
        expected_count=len(DEMO_BASELINE_AGENT_IDS),
        missing=missing,
    )


def _mcp_server_check(
    connection: Connection,
    organization_id: str,
    environment_id: str,
) -> DemoBaselineCheck:
    row = connection.execute(
        """
        SELECT id
        FROM mcp_servers
        WHERE id = ?
          AND organization_id = ?
          AND environment_id = ?
        """,
        (DEMO_BASELINE_MCP_SERVER_ID, organization_id, environment_id),
    ).fetchone()
    missing = [] if row is not None else [DEMO_BASELINE_MCP_SERVER_ID]
    return DemoBaselineCheck(
        key="mcp-server",
        label="Sample MCP server",
        status="degraded" if missing else "healthy",
        required=True,
        detail="Sample refund MCP server is registered."
        if not missing
        else "Sample refund MCP server is missing.",
        count=0 if missing else 1,
        expected_count=1,
        missing=missing,
    )


def _provider_credentials_check(
    connection: Connection,
    organization_id: str,
) -> DemoBaselineCheck:
    count = int(
        connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM provider_credentials
            WHERE organization_id = ? AND status = 'active'
            """,
            (organization_id,),
        ).fetchone()["count"]
    )
    return DemoBaselineCheck(
        key="provider-credential",
        label="Provider credential",
        status="healthy" if count else "warning",
        required=False,
        detail="At least one active provider credential is configured."
        if count
        else "Provider credential is optional for local scripted demos.",
        count=count,
        expected_count=1,
        missing=[] if count else ["provider credential"],
    )
