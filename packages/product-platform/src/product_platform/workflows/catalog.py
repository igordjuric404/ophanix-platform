"""Seeded workflow definitions for product-run CLI workflows."""

from __future__ import annotations

import json
from sqlite3 import Connection
from typing import Any

from product_platform.db.time import utc_now_iso


WORKFLOW_CATALOG: list[dict[str, Any]] = [
    {
        "id": "governance_verify",
        "name": "Governance Verify",
        "workflow_type": "governance",
        "command_ref": "python:governance.verify",
        "input_schema": {
            "type": "object",
            "required": ["scope"],
            "properties": {
                "scope": {"type": "string", "title": "Scope"},
                "evidence_ref": {"type": "string", "title": "Evidence Ref"},
            },
        },
    },
    {
        "id": "integrity_check",
        "name": "Integrity Check",
        "workflow_type": "integrity",
        "command_ref": "python:integrity.check",
        "input_schema": {
            "type": "object",
            "required": ["target"],
            "properties": {
                "target": {"type": "string", "title": "Target"},
            },
        },
    },
    {
        "id": "policy_lint",
        "name": "Policy Lint",
        "workflow_type": "policy",
        "command_ref": "python:policy.lint",
        "input_schema": {
            "type": "object",
            "required": ["policy_body"],
            "properties": {
                "policy_body": {"type": "string", "title": "Policy Body"},
                "policy_format": {"type": "string", "title": "Policy Format", "default": "yaml"},
            },
        },
    },
    {
        "id": "security_scan",
        "name": "Security Scan",
        "workflow_type": "security",
        "command_ref": "shell:security.scan",
        "input_schema": {
            "type": "object",
            "required": ["target_path"],
            "properties": {
                "target_path": {"type": "string", "title": "Target Path"},
            },
        },
    },
    {
        "id": "sbom_generation",
        "name": "SBOM Generation",
        "workflow_type": "supply_chain",
        "command_ref": "shell:sbom.generate",
        "input_schema": {
            "type": "object",
            "required": ["target_path"],
            "properties": {
                "target_path": {"type": "string", "title": "Target Path"},
                "format": {"type": "string", "title": "Format", "default": "cyclonedx"},
            },
        },
    },
    {
        "id": "dependency_confusion",
        "name": "Dependency Confusion Check",
        "workflow_type": "supply_chain",
        "command_ref": "shell:dependency_confusion.check",
        "input_schema": {
            "type": "object",
            "required": ["manifest_path"],
            "properties": {
                "manifest_path": {"type": "string", "title": "Manifest Path"},
            },
        },
    },
    {
        "id": "marketplace_evaluate",
        "name": "Marketplace Evaluate",
        "workflow_type": "marketplace",
        "command_ref": "python:marketplace.evaluate",
        "input_schema": {
            "type": "object",
            "required": ["plugin_id"],
            "properties": {
                "plugin_id": {"type": "string", "title": "Plugin ID"},
                "version": {"type": "string", "title": "Version"},
            },
        },
    },
]


def seed_workflow_catalog(connection: Connection, organization_id: str) -> None:
    """Seed registered workflow definitions for an organization."""

    now = utc_now_iso()
    for definition in WORKFLOW_CATALOG:
        connection.execute(
            """
            INSERT INTO workflow_definitions (
                id, organization_id, name, workflow_type, command_ref,
                input_schema_json, enabled, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                organization_id = excluded.organization_id,
                name = excluded.name,
                workflow_type = excluded.workflow_type,
                command_ref = excluded.command_ref,
                input_schema_json = excluded.input_schema_json,
                enabled = excluded.enabled,
                updated_at = excluded.updated_at
            """,
            (
                definition["id"],
                organization_id,
                definition["name"],
                definition["workflow_type"],
                definition["command_ref"],
                json.dumps(definition["input_schema"], sort_keys=True, separators=(",", ":")),
                1,
                now,
                now,
            ),
        )
