"""Local-only fixtures for direct HTTP Tool Gateway examples."""

from __future__ import annotations

import json
from dataclasses import dataclass
from sqlite3 import Connection

from product_platform.agents.credentials import hash_credential_token
from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID
from product_platform.db.time import utc_now_iso

DIRECT_HTTP_TOOL_ID = "tool_direct_http_claims_lookup"
DIRECT_HTTP_TOOL_VERSION_ID = "toolver_direct_http_claims_lookup_v1"
DIRECT_HTTP_TOOL_NAME = "claims.lookup"
DIRECT_HTTP_TOOL_SCOPE = "claims.lookup:read"
DIRECT_HTTP_TARGET_ID = "target_direct_http_claims_lookup"
DIRECT_HTTP_ALLOWED_AGENT_ID = "agent_direct_http_allowed"
DIRECT_HTTP_DENIED_AGENT_ID = "agent_direct_http_denied"
DIRECT_HTTP_ALLOWED_CREDENTIAL_ID = "cred_direct_http_allowed"
DIRECT_HTTP_DENIED_CREDENTIAL_ID = "cred_direct_http_denied"
DIRECT_HTTP_ALLOWED_TOKEN = "ophanix-local-only-tool-gateway-allowed-token"
DIRECT_HTTP_DENIED_TOKEN = "ophanix-local-only-tool-gateway-denied-token"
DIRECT_HTTP_UPSTREAM_BASE_URL = "https://claims-demo.example.invalid"
DIRECT_HTTP_UPSTREAM_HEALTH_URL = "https://claims-demo.example.invalid/health"
SUPPORT_BULK_CLAIMS_TOOL_ID = "tool_direct_http_claims_list_all"
SUPPORT_BULK_CLAIMS_TOOL_VERSION_ID = "toolver_direct_http_claims_list_all_v1"
SUPPORT_BULK_CLAIMS_TOOL_NAME = "claims.list_all"
SUPPORT_BULK_CLAIMS_TOOL_SCOPE = "claims.bulk:read"
SUPPORT_BULK_CLAIMS_TARGET_ID = "target_direct_http_claims_list_all"
SUPPORT_CROSS_CUSTOMER_CLAIM_TOOL_ID = "tool_direct_http_claims_lookup_cross_customer"
SUPPORT_CROSS_CUSTOMER_CLAIM_TOOL_VERSION_ID = "toolver_direct_http_claims_lookup_cross_customer_v1"
SUPPORT_CROSS_CUSTOMER_CLAIM_TOOL_NAME = "claims.lookup_cross_customer"
SUPPORT_CROSS_CUSTOMER_CLAIM_TOOL_SCOPE = "claims.cross_customer:read"
SUPPORT_CROSS_CUSTOMER_CLAIM_TARGET_ID = "target_direct_http_claims_lookup_cross_customer"

DIRECT_HTTP_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
    "additionalProperties": False,
}

DIRECT_HTTP_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_status": {"type": "string"}},
    "required": ["claim_status"],
    "additionalProperties": True,
}


SUPPORT_BULK_CLAIMS_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"scope": {"type": "string"}},
    "required": ["scope"],
    "additionalProperties": False,
}

SUPPORT_CROSS_CUSTOMER_CLAIM_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "claim_id": {"type": "string"},
        "requested_scope": {"type": "string"},
    },
    "required": ["claim_id", "requested_scope"],
    "additionalProperties": False,
}

@dataclass(frozen=True)
class DirectHttpDemoFixtures:
    """Identifiers and local-only tokens created for direct HTTP demos."""

    tool_id: str
    tool_name: str
    allowed_agent_id: str
    denied_agent_id: str
    allowed_token: str
    denied_token: str


def seed_tool_gateway_direct_http_fixtures(
    connection: Connection,
    *,
    organization_id: str = DEMO_ORG_ID,
    environment_id: str = DEMO_ENV_ID,
    actor_id: str = DEMO_ADMIN_USER_ID,
    upstream_base_url: str = DIRECT_HTTP_UPSTREAM_BASE_URL,
) -> DirectHttpDemoFixtures:
    """Seed opt-in local fixtures for the direct HTTP examples.

    The raw tokens are deterministic placeholders for local demos only. They are
    never stored directly; only their SHA-256 hashes are persisted.
    """

    now = utc_now_iso()
    _seed_agent(
        connection,
        agent_id=DIRECT_HTTP_ALLOWED_AGENT_ID,
        name="Direct HTTP Demo Agent",
        description="Allowed local-only agent for Tool Gateway direct HTTP examples.",
        now=now,
        organization_id=organization_id,
        environment_id=environment_id,
        actor_id=actor_id,
    )
    _seed_agent(
        connection,
        agent_id=DIRECT_HTTP_DENIED_AGENT_ID,
        name="Direct HTTP Denied Demo Agent",
        description="Denied local-only agent that authenticates but has no tool permission.",
        now=now,
        organization_id=organization_id,
        environment_id=environment_id,
        actor_id=actor_id,
    )
    tool_id = _seed_tool(
        connection,
        now=now,
        organization_id=organization_id,
        environment_id=environment_id,
        actor_id=actor_id,
    )
    _seed_upstream_target(
        connection,
        tool_id=tool_id,
        now=now,
        organization_id=organization_id,
        environment_id=environment_id,
        base_url=upstream_base_url,
    )
    _seed_credential(
        connection,
        credential_id=DIRECT_HTTP_ALLOWED_CREDENTIAL_ID,
        scope_id="scope_direct_http_allowed",
        agent_id=DIRECT_HTTP_ALLOWED_AGENT_ID,
        token=DIRECT_HTTP_ALLOWED_TOKEN,
        now=now,
    )
    _seed_credential(
        connection,
        credential_id=DIRECT_HTTP_DENIED_CREDENTIAL_ID,
        scope_id="scope_direct_http_denied",
        agent_id=DIRECT_HTTP_DENIED_AGENT_ID,
        token=DIRECT_HTTP_DENIED_TOKEN,
        now=now,
    )
    _seed_allowed_permission(
        connection,
        tool_id=tool_id,
        now=now,
        organization_id=organization_id,
        environment_id=environment_id,
        actor_id=actor_id,
    )
    connection.execute(
        """
        DELETE FROM agent_tool_permissions
        WHERE organization_id = ? AND environment_id = ?
          AND agent_id = ? AND tool_id = ?
        """,
        (organization_id, environment_id, DIRECT_HTTP_DENIED_AGENT_ID, tool_id),
    )
    return DirectHttpDemoFixtures(
        tool_id=tool_id,
        tool_name=DIRECT_HTTP_TOOL_NAME,
        allowed_agent_id=DIRECT_HTTP_ALLOWED_AGENT_ID,
        denied_agent_id=DIRECT_HTTP_DENIED_AGENT_ID,
        allowed_token=DIRECT_HTTP_ALLOWED_TOKEN,
        denied_token=DIRECT_HTTP_DENIED_TOKEN,
    )


def seed_support_demo_tool_gateway_fixtures(
    connection: Connection,
    *,
    organization_id: str = DEMO_ORG_ID,
    environment_id: str = DEMO_ENV_ID,
    actor_id: str = DEMO_ADMIN_USER_ID,
    upstream_base_url: str = DIRECT_HTTP_UPSTREAM_BASE_URL,
) -> None:
    """Seed support-demo denied contracts into the local Product Platform DB."""

    seed_tool_gateway_direct_http_fixtures(
        connection,
        organization_id=organization_id,
        environment_id=environment_id,
        actor_id=actor_id,
        upstream_base_url=upstream_base_url,
    )
    now = utc_now_iso()
    for tool in [
        {
            "tool_id": SUPPORT_BULK_CLAIMS_TOOL_ID,
            "version_id": SUPPORT_BULK_CLAIMS_TOOL_VERSION_ID,
            "target_id": SUPPORT_BULK_CLAIMS_TARGET_ID,
            "name": SUPPORT_BULK_CLAIMS_TOOL_NAME,
            "display_name": "Claims Bulk Export",
            "description": "Support-demo contract for denied bulk claims database reads.",
            "required_scope": SUPPORT_BULK_CLAIMS_TOOL_SCOPE,
            "input_schema": SUPPORT_BULK_CLAIMS_INPUT_SCHEMA,
        },
        {
            "tool_id": SUPPORT_CROSS_CUSTOMER_CLAIM_TOOL_ID,
            "version_id": SUPPORT_CROSS_CUSTOMER_CLAIM_TOOL_VERSION_ID,
            "target_id": SUPPORT_CROSS_CUSTOMER_CLAIM_TARGET_ID,
            "name": SUPPORT_CROSS_CUSTOMER_CLAIM_TOOL_NAME,
            "display_name": "Cross-Customer Claims Lookup",
            "description": "Support-demo contract for denied cross-customer claim lookups.",
            "required_scope": SUPPORT_CROSS_CUSTOMER_CLAIM_TOOL_SCOPE,
            "input_schema": SUPPORT_CROSS_CUSTOMER_CLAIM_INPUT_SCHEMA,
        },
    ]:
        tool_id = _seed_named_tool(
            connection,
            now=now,
            organization_id=organization_id,
            environment_id=environment_id,
            actor_id=actor_id,
            tool_id=str(tool["tool_id"]),
            version_id=str(tool["version_id"]),
            name=str(tool["name"]),
            display_name=str(tool["display_name"]),
            description=str(tool["description"]),
            required_scope=str(tool["required_scope"]),
            input_schema=tool["input_schema"],
            output_schema=DIRECT_HTTP_OUTPUT_SCHEMA,
            change_summary="Initial support demo denied contract.",
        )
        _seed_upstream_target(
            connection,
            tool_id=tool_id,
            now=now,
            organization_id=organization_id,
            environment_id=environment_id,
            target_id=str(tool["target_id"]),
            base_url=upstream_base_url,
        )
        connection.execute(
            """
            DELETE FROM agent_tool_permissions
            WHERE organization_id = ? AND environment_id = ?
              AND agent_id IN (?, ?) AND tool_id = ?
            """,
            (
                organization_id,
                environment_id,
                DIRECT_HTTP_ALLOWED_AGENT_ID,
                DIRECT_HTTP_DENIED_AGENT_ID,
                tool_id,
            ),
        )


def _seed_agent(
    connection: Connection,
    *,
    agent_id: str,
    name: str,
    description: str,
    now: str,
    organization_id: str,
    environment_id: str,
    actor_id: str,
) -> None:
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
            organization_id,
            environment_id,
            name,
            description,
            "direct-http-demo",
            "service",
            None,
            actor_id,
            actor_id,
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
        UPDATE agents
        SET status = 'active', credential_status = 'issued', updated_at = ?
        WHERE id = ?
        """,
        (now, agent_id),
    )


def _seed_tool(
    connection: Connection,
    *,
    now: str,
    organization_id: str,
    environment_id: str,
    actor_id: str,
) -> str:
    existing = connection.execute(
        """
        SELECT id FROM tool_definitions
        WHERE organization_id = ? AND environment_id = ? AND lower(name) = lower(?)
        LIMIT 1
        """,
        (organization_id, environment_id, DIRECT_HTTP_TOOL_NAME),
    ).fetchone()
    tool_id = existing["id"] if existing is not None else DIRECT_HTTP_TOOL_ID
    connection.execute(
        """
        INSERT OR IGNORE INTO tool_definitions (
            id, organization_id, environment_id, name, display_name, description,
            owner_team, status, required_scope, input_schema_json, output_schema_json,
            created_by, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            tool_id,
            organization_id,
            environment_id,
            DIRECT_HTTP_TOOL_NAME,
            "Claims Lookup",
            "Local-only Tool Gateway direct HTTP demo tool.",
            "claims-platform",
            "active",
            DIRECT_HTTP_TOOL_SCOPE,
            json.dumps(DIRECT_HTTP_INPUT_SCHEMA, sort_keys=True),
            json.dumps(DIRECT_HTTP_OUTPUT_SCHEMA, sort_keys=True),
            actor_id,
            now,
            now,
        ),
    )
    connection.execute(
        """
        UPDATE tool_definitions
        SET status = 'active',
            required_scope = ?,
            input_schema_json = ?,
            output_schema_json = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            DIRECT_HTTP_TOOL_SCOPE,
            json.dumps(DIRECT_HTTP_INPUT_SCHEMA, sort_keys=True),
            json.dumps(DIRECT_HTTP_OUTPUT_SCHEMA, sort_keys=True),
            now,
            tool_id,
        ),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO tool_definition_versions (
            id, tool_id, version, input_schema_json, output_schema_json,
            required_scope, change_summary, created_by, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            DIRECT_HTTP_TOOL_VERSION_ID if tool_id == DIRECT_HTTP_TOOL_ID else f"toolver_direct_http_{tool_id}",
            tool_id,
            1,
            json.dumps(DIRECT_HTTP_INPUT_SCHEMA, sort_keys=True),
            json.dumps(DIRECT_HTTP_OUTPUT_SCHEMA, sort_keys=True),
            DIRECT_HTTP_TOOL_SCOPE,
            "Initial direct HTTP demo contract.",
            actor_id,
            now,
        ),
    )
    return tool_id


def _seed_named_tool(
    connection: Connection,
    *,
    now: str,
    organization_id: str,
    environment_id: str,
    actor_id: str,
    tool_id: str,
    version_id: str,
    name: str,
    display_name: str,
    description: str,
    required_scope: str,
    input_schema: dict[str, object],
    output_schema: dict[str, object],
    change_summary: str,
) -> str:
    existing = connection.execute(
        """
        SELECT id FROM tool_definitions
        WHERE organization_id = ? AND environment_id = ? AND lower(name) = lower(?)
        LIMIT 1
        """,
        (organization_id, environment_id, name),
    ).fetchone()
    resolved_tool_id = existing["id"] if existing is not None else tool_id
    input_schema_json = json.dumps(input_schema, sort_keys=True)
    output_schema_json = json.dumps(output_schema, sort_keys=True)
    connection.execute(
        """
        INSERT OR IGNORE INTO tool_definitions (
            id, organization_id, environment_id, name, display_name, description,
            owner_team, status, required_scope, input_schema_json, output_schema_json,
            created_by, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            resolved_tool_id,
            organization_id,
            environment_id,
            name,
            display_name,
            description,
            "claims-platform",
            "active",
            required_scope,
            input_schema_json,
            output_schema_json,
            actor_id,
            now,
            now,
        ),
    )
    connection.execute(
        """
        UPDATE tool_definitions
        SET display_name = ?,
            description = ?,
            status = 'active',
            required_scope = ?,
            input_schema_json = ?,
            output_schema_json = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            display_name,
            description,
            required_scope,
            input_schema_json,
            output_schema_json,
            now,
            resolved_tool_id,
        ),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO tool_definition_versions (
            id, tool_id, version, input_schema_json, output_schema_json,
            required_scope, change_summary, created_by, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version_id if resolved_tool_id == tool_id else f"toolver_direct_http_{resolved_tool_id}",
            resolved_tool_id,
            1,
            input_schema_json,
            output_schema_json,
            required_scope,
            change_summary,
            actor_id,
            now,
        ),
    )
    return resolved_tool_id


def _seed_upstream_target(
    connection: Connection,
    *,
    tool_id: str,
    now: str,
    organization_id: str,
    environment_id: str,
    target_id: str | None = None,
    base_url: str = DIRECT_HTTP_UPSTREAM_BASE_URL,
    path_template: str = "/claims/{claim_id}",
    health_url: str | None = None,
) -> None:
    target_id = target_id or (
        DIRECT_HTTP_TARGET_ID if tool_id == DIRECT_HTTP_TOOL_ID else f"target_direct_http_{tool_id}"
    )
    health_url = health_url or f"{base_url.rstrip('/')}/health"
    connection.execute(
        """
        INSERT OR IGNORE INTO tool_upstream_targets (
            id, organization_id, environment_id, tool_id, base_url, path_template,
            method, auth_mode, timeout_ms, status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            target_id,
            organization_id,
            environment_id,
            tool_id,
            base_url,
            path_template,
            "POST",
            "none",
            1200,
            "configured",
            now,
            now,
        ),
    )
    connection.execute(
        """
        UPDATE tool_upstream_targets
        SET base_url = ?,
            path_template = ?,
            method = 'POST',
            auth_mode = 'none',
            timeout_ms = 1200,
            status = 'configured',
            updated_at = ?
        WHERE organization_id = ? AND environment_id = ? AND tool_id = ?
        """,
        (base_url, path_template, now, organization_id, environment_id, tool_id),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO tool_upstream_health_checks (
            id, target_id, health_url, expected_status, interval_seconds,
            last_status, last_checked_at, last_error, enabled
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"health_{target_id}",
            target_id,
            health_url,
            200,
            60,
            None,
            None,
            None,
            1,
        ),
    )
    connection.execute(
        """
        UPDATE tool_upstream_health_checks
        SET health_url = ?
        WHERE target_id = ?
        """,
        (health_url, target_id),
    )


def _seed_credential(
    connection: Connection,
    *,
    credential_id: str,
    scope_id: str,
    agent_id: str,
    token: str,
    now: str,
) -> None:
    token_hash = hash_credential_token(token)
    connection.execute(
        """
        INSERT OR IGNORE INTO agent_credentials (
            id, agent_id, credential_type, token_hash, issuer, status,
            issued_at, expires_at, revoked_at, last_used_at, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            credential_id,
            agent_id,
            "bearer",
            token_hash,
            "local-direct-http-demo",
            "active",
            now,
            "2030-01-01T00:00:00+00:00",
            None,
            None,
            json.dumps({"local_only": True, "example": "tool-gateway-direct-http"}, sort_keys=True),
        ),
    )
    stored = connection.execute(
        "SELECT id FROM agent_credentials WHERE token_hash = ?",
        (token_hash,),
    ).fetchone()
    stored_credential_id = stored["id"] if stored is not None else credential_id
    connection.execute(
        """
        INSERT OR IGNORE INTO credential_scopes (
            id, credential_id, scope, resource_type, resource_id
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            scope_id,
            stored_credential_id,
            DIRECT_HTTP_TOOL_SCOPE,
            "tool",
            DIRECT_HTTP_TOOL_NAME,
        ),
    )


def _seed_allowed_permission(
    connection: Connection,
    *,
    tool_id: str,
    now: str,
    organization_id: str,
    environment_id: str,
    actor_id: str,
) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO agent_tool_permissions (
            id, organization_id, environment_id, agent_id, tool_id, scope, status,
            granted_by, granted_reason, granted_at, revoked_by, revoked_reason,
            revoked_at, expires_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "perm_direct_http_allowed",
            organization_id,
            environment_id,
            DIRECT_HTTP_ALLOWED_AGENT_ID,
            tool_id,
            DIRECT_HTTP_TOOL_SCOPE,
            "active",
            actor_id,
            "Local direct HTTP demo fixture.",
            now,
            None,
            None,
            None,
            None,
        ),
    )
