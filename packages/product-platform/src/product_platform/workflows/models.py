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
