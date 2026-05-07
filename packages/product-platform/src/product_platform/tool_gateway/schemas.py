"""JSON Schema validation helpers for Tool Gateway contracts."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError


class ToolSchemaValidationError(ValueError):
    """Raised when a tool contract schema is invalid."""

    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field


def validate_tool_contract_schema(schema: dict[str, Any] | None, *, field: str) -> None:
    """Validate a JSON Schema document used by a tool contract."""

    if schema is None:
        return
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ToolSchemaValidationError(exc.message, field=field) from exc


def validate_payload(instance: Any, schema: dict[str, Any]) -> None:
    """Validate a runtime payload against a persisted tool schema."""

    try:
        Draft202012Validator(schema).validate(instance)
    except ValidationError as exc:
        raise ToolSchemaValidationError(exc.message, field="payload") from exc

