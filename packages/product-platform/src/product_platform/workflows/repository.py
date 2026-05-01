"""Workflow catalog repository."""

from __future__ import annotations

import json
from sqlite3 import Connection, Row

from product_platform.workflows.models import WorkflowDefinitionResponse


class WorkflowRepository:
    """Read registered workflow definitions."""

    def __init__(self, connection: Connection, organization_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id

    def list_definitions(
        self,
        *,
        enabled: bool | None = None,
        workflow_type: str | None = None,
    ) -> list[Row]:
        """List workflow definitions in stable catalog order."""

        clauses = ["organization_id = ?"]
        values: list[object] = [self.organization_id]
        if enabled is not None:
            clauses.append("enabled = ?")
            values.append(1 if enabled else 0)
        if workflow_type:
            clauses.append("workflow_type = ?")
            values.append(workflow_type)
        return self.connection.execute(
            f"""
            SELECT *
            FROM workflow_definitions
            WHERE {' AND '.join(clauses)}
            ORDER BY workflow_type ASC, name ASC
            """,
            values,
        ).fetchall()


def workflow_definition_response(row: Row) -> WorkflowDefinitionResponse:
    """Serialize one workflow definition row."""

    return WorkflowDefinitionResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        name=row["name"],
        workflow_type=row["workflow_type"],
        command_ref=row["command_ref"],
        input_schema=json.loads(row["input_schema_json"]),
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
