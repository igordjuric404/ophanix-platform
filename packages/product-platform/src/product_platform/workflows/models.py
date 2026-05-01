"""Workflow API models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkflowDefinitionResponse(BaseModel):
    """Registered workflow users can run through the product."""

    id: str
    organization_id: str
    name: str
    workflow_type: str
    command_ref: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    enabled: bool
    created_at: str
    updated_at: str


class WorkflowRunCreateRequest(BaseModel):
    """Create and optionally execute a workflow run."""

    inputs: dict[str, Any] = Field(default_factory=dict)
    run_immediately: bool = True


class WorkflowLogResponse(BaseModel):
    """One persisted workflow log line."""

    id: str
    workflow_run_id: str
    stream: str
    line_number: int
    message: str
    created_at: str


class WorkflowRunResponse(BaseModel):
    """Persisted workflow run with logs."""

    id: str
    organization_id: str
    environment_id: str | None = None
    workflow_definition_id: str
    workflow_type: str
    command_ref: str | None = None
    status: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    started_by: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    logs: list[WorkflowLogResponse] = Field(default_factory=list)


class WorkflowInputValidationError(ValueError):
    """Raised when workflow inputs do not match the stored schema."""


def validate_workflow_inputs(schema: dict[str, Any], inputs: dict[str, Any]) -> None:
    """Validate required fields from the stored JSON-schema-like input schema."""

    required = schema.get("required", [])
    if not isinstance(required, list):
        return
    missing = [
        str(name)
        for name in required
        if not str(inputs.get(str(name), "")).strip()
    ]
    if missing:
        raise WorkflowInputValidationError(
            f"Workflow input is missing required field(s): {', '.join(sorted(missing))}."
        )
