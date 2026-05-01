"""Seeded Demo Lab scenario definitions."""

from __future__ import annotations

import json
from sqlite3 import Connection
from typing import Any

from product_platform.db.time import utc_now_iso

DEFAULT_DEMO_ORG_ID = "org_default"
DEFAULT_DEMO_ENV_ID = "env_default"


CUSTOMER_SUPPORT_REFUND_SCENARIO: dict[str, Any] = {
    "id": "demo_scenario_customer_support_refund",
    "name": "Customer Support Refund Governance",
    "slug": "customer-support-refund",
    "description": (
        "A governed customer-support agent handles a refund request while policy, MCP, "
        "runtime, trust, discovery, and observability controls produce live evidence."
    ),
    "value_proof": (
        "Shows an allowed low-risk action, a human approval path for a high-value refund, "
        "a denied unsafe tool path, credential rotation, discovery reconciliation, saga "
        "execution, and compliance evidence from live product state."
    ),
    "status": "published",
    "required_services": [
        {
            "key": "product-api",
            "label": "Product API",
            "required": True,
            "health_endpoint": "/health",
            "evidence_route": "/overview",
        },
        {
            "key": "database",
            "label": "SQLite database",
            "required": True,
            "health_endpoint": "/ready",
            "evidence_route": "/settings",
        },
        {
            "key": "worker",
            "label": "Demo runner worker",
            "required": True,
            "evidence_route": "/workflows",
        },
        {
            "key": "sample-mcp-server",
            "label": "Sample refund MCP server",
            "required": True,
            "evidence_route": "/mcp",
        },
        {
            "key": "provider-credential",
            "label": "Model provider credential",
            "required": False,
            "evidence_route": "/integrations",
        },
    ],
    "steps": [
        {
            "id": "demo_step_refund_register_agents",
            "step_order": 1,
            "title": "Register support and refund agents",
            "expected_result": "Support, refund, and supervisor agents appear in inventory.",
            "action_type": "register_agents",
            "action_config": {
                "agents": [
                    {"id": "agent_demo_support", "framework": "openai-agents"},
                    {"id": "agent_demo_refund", "framework": "langchain"},
                    {"id": "agent_demo_supervisor", "framework": "agentmesh"},
                ]
            },
            "proof_links": [
                {
                    "area": "Agents",
                    "label": "Agent inventory",
                    "route": "/agents",
                    "resource_hint": "agent_demo_support",
                }
            ],
        },
        {
            "id": "demo_step_refund_import_policies",
            "step_order": 2,
            "title": "Import refund policy pack",
            "expected_result": "Refund limit and sensitive-tool policies are active.",
            "action_type": "import_policies",
            "action_config": {
                "policy_slugs": ["refund-limit", "sensitive-tool-approval"],
                "mode": "enforce",
            },
            "proof_links": [
                {
                    "area": "Policies",
                    "label": "Policy library",
                    "route": "/policies",
                    "resource_hint": "refund-limit",
                }
            ],
        },
        {
            "id": "demo_step_refund_register_mcp",
            "step_order": 3,
            "title": "Register refund MCP server",
            "expected_result": "Refund tools are discovered, versioned, and policy-scanned.",
            "action_type": "register_mcp_server",
            "action_config": {
                "server_id": "mcp_demo_refund",
                "tools": ["lookup_order", "issue_refund", "escalate_refund"],
            },
            "proof_links": [
                {
                    "area": "MCP",
                    "label": "MCP server registry",
                    "route": "/mcp",
                    "resource_hint": "mcp_demo_refund",
                }
            ],
        },
        {
            "id": "demo_step_refund_allowed_prompt",
            "step_order": 4,
            "title": "Run allowed refund lookup",
            "expected_result": "The support agent looks up an eligible order and emits a mesh handoff.",
            "action_type": "run_agent_prompt",
            "action_config": {
                "prompt": "Customer asks for refund status on order ORD-1001.",
                "expected_decision": "allow",
            },
            "proof_links": [
                {
                    "area": "Mesh",
                    "label": "Agent mesh message feed",
                    "route": "/mesh",
                    "resource_hint": "ORD-1001",
                }
            ],
        },
        {
            "id": "demo_step_refund_high_value_approval",
            "step_order": 5,
            "title": "Request high-value refund approval",
            "expected_result": "A high-value refund pauses for approval before execution.",
            "action_type": "request_approval",
            "action_config": {
                "amount_cents": 125000,
                "currency": "USD",
                "approval_policy": "refund-limit",
            },
            "proof_links": [
                {
                    "area": "Runtime",
                    "label": "Runtime approval timeline",
                    "route": "/runtime",
                    "resource_hint": "refund-limit",
                },
                {
                    "area": "MCP",
                    "label": "MCP approval queue",
                    "route": "/mcp",
                    "resource_hint": "issue_refund",
                },
            ],
        },
        {
            "id": "demo_step_refund_rotate_credential",
            "step_order": 6,
            "title": "Rotate refund agent credential",
            "expected_result": "Credential rotation updates the trust card and audit trail.",
            "action_type": "rotate_credential",
            "action_config": {
                "agent_id": "agent_demo_refund",
                "reason": "demo-approved credential hygiene",
            },
            "proof_links": [
                {
                    "area": "Trust",
                    "label": "Trust cards",
                    "route": "/trust",
                    "resource_hint": "agent_demo_refund",
                },
                {
                    "area": "Agents",
                    "label": "Agent credentials",
                    "route": "/agents",
                    "resource_hint": "agent_demo_refund",
                },
            ],
        },
        {
            "id": "demo_step_refund_discovery",
            "step_order": 7,
            "title": "Run shadow AI discovery",
            "expected_result": "Discovery flags an unmanaged refund helper and reconciles ownership.",
            "action_type": "run_discovery",
            "action_config": {
                "target_id": "discovery_demo_refund_repo",
                "expected_finding": "shadow_refund_helper",
            },
            "proof_links": [
                {
                    "area": "Discovery",
                    "label": "Discovery findings",
                    "route": "/discovery",
                    "resource_hint": "shadow_refund_helper",
                }
            ],
        },
        {
            "id": "demo_step_refund_saga",
            "step_order": 8,
            "title": "Execute refund saga",
            "expected_result": "The refund saga completes with compensating steps available.",
            "action_type": "run_saga",
            "action_config": {
                "saga_id": "saga_demo_refund",
                "steps": ["validate_policy", "issue_refund", "notify_customer"],
            },
            "proof_links": [
                {
                    "area": "Runtime",
                    "label": "Saga monitor",
                    "route": "/runtime",
                    "resource_hint": "saga_demo_refund",
                }
            ],
        },
        {
            "id": "demo_step_refund_report",
            "step_order": 9,
            "title": "Generate compliance and observability report",
            "expected_result": "Compliance evidence and operational telemetry summarize the demo run.",
            "action_type": "generate_report",
            "action_config": {
                "report_type": "demo_refund_evidence",
                "controls": ["policy_enforcement", "credential_rotation", "runtime_approval"],
            },
            "proof_links": [
                {
                    "area": "Compliance",
                    "label": "Evidence report",
                    "route": "/compliance",
                    "resource_hint": "demo_refund_evidence",
                },
                {
                    "area": "Observability",
                    "label": "Demo telemetry",
                    "route": "/observability",
                    "resource_hint": "demo_refund_evidence",
                },
            ],
        },
    ],
}


def seed_demo_scenarios(
    connection: Connection,
    organization_id: str = DEFAULT_DEMO_ORG_ID,
    environment_id: str = DEFAULT_DEMO_ENV_ID,
) -> None:
    """Seed Demo Lab scenario definitions for the local demo organization."""

    now = utc_now_iso()
    scenario = CUSTOMER_SUPPORT_REFUND_SCENARIO
    connection.execute(
        """
        INSERT INTO demo_scenarios (
            id, organization_id, environment_id, name, slug, description,
            value_proof, status, required_services_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            organization_id = excluded.organization_id,
            environment_id = excluded.environment_id,
            name = excluded.name,
            slug = excluded.slug,
            description = excluded.description,
            value_proof = excluded.value_proof,
            status = excluded.status,
            required_services_json = excluded.required_services_json,
            updated_at = excluded.updated_at
        """,
        (
            scenario["id"],
            organization_id,
            environment_id,
            scenario["name"],
            scenario["slug"],
            scenario["description"],
            scenario["value_proof"],
            scenario["status"],
            _json(scenario["required_services"]),
            now,
            now,
        ),
    )
    step_ids: list[str] = []
    for step in scenario["steps"]:
        step_ids.append(step["id"])
        connection.execute(
            """
            INSERT INTO demo_steps (
                id, scenario_id, step_order, title, expected_result,
                action_type, action_config_json, proof_links_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                scenario_id = excluded.scenario_id,
                step_order = excluded.step_order,
                title = excluded.title,
                expected_result = excluded.expected_result,
                action_type = excluded.action_type,
                action_config_json = excluded.action_config_json,
                proof_links_json = excluded.proof_links_json,
                updated_at = excluded.updated_at
            """,
            (
                step["id"],
                scenario["id"],
                step["step_order"],
                step["title"],
                step["expected_result"],
                step["action_type"],
                _json(step["action_config"]),
                _json(step["proof_links"]),
                now,
                now,
            ),
        )
    placeholders = ",".join("?" for _ in step_ids)
    connection.execute(
        f"""
        DELETE FROM demo_steps
        WHERE scenario_id = ?
          AND id NOT IN ({placeholders})
        """,
        [scenario["id"], *step_ids],
    )


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
