"""Seed data for supported agent framework integrations."""

from __future__ import annotations

import json
from product_platform.db.postgres import Connection
from typing import Any

from product_platform.db.time import utc_now_iso


FRAMEWORK_CATALOG: list[dict[str, Any]] = [
    {
        "id": "openai_agents",
        "integration_type": "framework",
        "name": "OpenAI Agents",
        "description": "Primary demo connector for OpenAI Agents SDK telemetry and policy hooks.",
        "status": "primary_demo",
        "supported_versions": ["0.2.x", "0.3.x"],
        "setup_doc_url": "/docs/integrations/openai-agents",
        "example_path": "packages/agent-os/examples/openai_agents",
        "setup_snippet": "ophanix integrations init openai_agents --agent agent_demo",
    },
    {
        "id": "langchain",
        "integration_type": "framework",
        "name": "LangChain",
        "description": "Supported connector for LangChain callbacks, traces, and policy decisions.",
        "status": "supported",
        "supported_versions": ["0.2.x", "0.3.x"],
        "setup_doc_url": "/docs/integrations/langchain",
        "example_path": "packages/agent-os/examples/langchain",
        "setup_snippet": "ophanix integrations init langchain --callback-handler",
    },
    {
        "id": "crewai",
        "integration_type": "framework",
        "name": "CrewAI",
        "description": "Supported connector for CrewAI agent and task lifecycle events.",
        "status": "supported",
        "supported_versions": ["0.86.x", "0.95.x"],
        "setup_doc_url": "/docs/integrations/crewai",
        "example_path": "packages/agent-os/examples/crewai",
        "setup_snippet": "ophanix integrations init crewai --crew crew_name",
    },
    {
        "id": "smolagents",
        "integration_type": "framework",
        "name": "smolagents",
        "description": "Experimental connector scaffold for lightweight agent telemetry.",
        "status": "experimental",
        "supported_versions": ["1.x"],
        "setup_doc_url": "/docs/integrations/smolagents",
        "example_path": "packages/agent-os/examples/smolagents",
        "setup_snippet": "ophanix integrations init smolagents --experimental",
    },
    {
        "id": "llamaindex",
        "integration_type": "framework",
        "name": "LlamaIndex",
        "description": "Experimental connector for workflow and retrieval telemetry.",
        "status": "experimental",
        "supported_versions": ["0.11.x", "0.12.x"],
        "setup_doc_url": "/docs/integrations/llamaindex",
        "example_path": "packages/agent-os/examples/llamaindex",
        "setup_snippet": "ophanix integrations init llamaindex --workflow",
    },
    {
        "id": "autogen",
        "integration_type": "framework",
        "name": "AutoGen",
        "description": "Scaffold connector for multi-agent conversation instrumentation.",
        "status": "scaffold",
        "supported_versions": ["0.4.x"],
        "setup_doc_url": "/docs/integrations/autogen",
        "example_path": "packages/agentmesh-integrations/autogen",
        "setup_snippet": "ophanix integrations init autogen --scaffold",
    },
    {
        "id": "custom",
        "integration_type": "framework",
        "name": "Custom",
        "description": "Bring-your-own framework connector using the generic Ophanix SDK contract.",
        "status": "scaffold",
        "supported_versions": ["sdk-contract-v1"],
        "setup_doc_url": "/docs/integrations/custom",
        "example_path": "packages/agent-os/src/agent_os/integrations",
        "setup_snippet": "ophanix integrations init custom --adapter ./adapter.py",
    },
]


def seed_framework_catalog(connection: Connection) -> None:
    """Insert or update the deterministic framework catalog."""

    now = utc_now_iso()
    for framework in FRAMEWORK_CATALOG:
        connection.execute(
            """
            INSERT INTO integrations (
                id, integration_type, name, description, status,
                supported_versions_json, setup_doc_url, example_path,
                setup_snippet, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                integration_type = excluded.integration_type,
                name = excluded.name,
                description = excluded.description,
                status = excluded.status,
                supported_versions_json = excluded.supported_versions_json,
                setup_doc_url = excluded.setup_doc_url,
                example_path = excluded.example_path,
                setup_snippet = excluded.setup_snippet,
                updated_at = excluded.updated_at
            """,
            (
                framework["id"],
                framework["integration_type"],
                framework["name"],
                framework["description"],
                framework["status"],
                json.dumps(framework["supported_versions"], sort_keys=True, separators=(",", ":")),
                framework["setup_doc_url"],
                framework["example_path"],
                framework["setup_snippet"],
                now,
                now,
            ),
        )
