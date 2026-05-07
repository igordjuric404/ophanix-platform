"""Response validation, redaction, and visibility handling for Tool Gateway."""

from __future__ import annotations

import json
import re
from typing import Any

from product_platform.tool_gateway.invocation import ToolExecutionError, ToolExecutionResult
from product_platform.tool_gateway.schemas import ToolSchemaValidationError, validate_payload

REDACTED_VALUE = "[redacted]"


def process_tool_execution_response(
    tool: Any,
    policy: Any,
    execution: ToolExecutionResult,
) -> ToolExecutionResult:
    """Return a safe agent-facing execution result."""

    if execution.status != "succeeded":
        return execution
    body = execution.body
    schema_valid: bool | None = None
    warnings = list(execution.warnings)
    output_schema = _json_from_row_value(tool["output_schema_json"])
    if output_schema is not None:
        try:
            validate_payload(body, output_schema)
            schema_valid = True
        except ToolSchemaValidationError as exc:
            schema_valid = False
            if bool(policy["strict_output_validation"]):
                raise ToolExecutionError(
                    code="response_schema_invalid",
                    message=f"Upstream response failed output schema validation: {exc}",
                    status_code=502,
                ) from exc
            warnings.append("response_schema_invalid")

    redaction_rules = _json_from_row_value(policy["redaction_rules_json"]) or {}
    redacted_body, redaction_applied = _redact_value(body, redaction_rules)
    if _response_size(redacted_body) > int(policy["max_response_bytes"]):
        raise ToolExecutionError(
            code="response_too_large",
            message="Upstream response exceeds the configured size limit.",
            status_code=502,
        )
    exposed = bool(policy["expose_to_agent"])
    return execution.model_copy(
        update={
            "body": redacted_body if exposed else None,
            "response_schema_valid": schema_valid,
            "redaction_applied": execution.redaction_applied or redaction_applied,
            "exposed_to_agent": exposed,
            "warnings": warnings,
        }
    )


def _json_from_row_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return value


def _redact_value(value: Any, rules: dict[str, Any], *, key: str = "") -> tuple[Any, bool]:
    redact_keys = [item.lower() for item in rules.get("redact_keys", [])]
    redact_patterns = [re.compile(pattern) for pattern in rules.get("redact_patterns", [])]
    lowered = key.lower()
    if key and any(token in lowered for token in redact_keys):
        return REDACTED_VALUE, True
    if isinstance(value, dict):
        changed = False
        output: dict[str, Any] = {}
        for child_key, child_value in value.items():
            redacted, child_changed = _redact_value(child_value, rules, key=str(child_key))
            output[str(child_key)] = redacted
            changed = changed or child_changed
        return output, changed
    if isinstance(value, list):
        changed = False
        output_list = []
        for item in value:
            redacted, child_changed = _redact_value(item, rules, key=key)
            output_list.append(redacted)
            changed = changed or child_changed
        return output_list, changed
    if isinstance(value, str):
        redacted = value
        changed = False
        for pattern in redact_patterns:
            redacted, count = pattern.subn(REDACTED_VALUE, redacted)
            changed = changed or count > 0
        return redacted, changed
    return value, False


def _response_size(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, default=str).encode("utf-8"))
