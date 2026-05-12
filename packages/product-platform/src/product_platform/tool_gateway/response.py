"""Response validation, redaction, and visibility handling for Tool Gateway."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

import regex as safe_regex

from product_platform.tool_gateway.invocation import ToolExecutionError, ToolExecutionResult
from product_platform.tool_gateway.schemas import ToolSchemaValidationError, validate_payload

REDACTED_VALUE = "[redacted]"
MAX_REDACTION_DEPTH = 20
MAX_REDACTION_PATTERN_LENGTH = 300
MAX_REDACTION_STRING_CHARS = 16_384
REDACTION_REGEX_TIMEOUT_SECONDS = 0.01


def process_tool_execution_response(
    tool: Any,
    policy: Any,
    execution: ToolExecutionResult,
) -> ToolExecutionResult:
    """Return a safe agent-facing execution result."""

    try:
        policy_status = str(policy["status"]).strip().lower()
    except Exception:
        policy_status = "active"
    if policy_status != "active":
        return execution

    body = execution.body
    schema_valid: bool | None = None
    warnings = list(execution.warnings)
    output_schema = _json_from_row_value(tool["output_schema_json"])
    if execution.status == "succeeded" and output_schema is not None:
        try:
            validate_payload(body, output_schema)
            schema_valid = True
        except ToolSchemaValidationError as exc:
            schema_valid = False
            if bool(policy["strict_output_validation"]):
                raise ToolExecutionError(
                    code="response_schema_invalid",
                    message="Upstream response failed output schema validation.",
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
    return _redact_value_at_depth(value, _compiled_redaction_rules(rules), key=key, depth=0)


def _compiled_redaction_rules(rules: dict[str, Any]) -> dict[str, Any]:
    redact_keys = tuple(_normalize_redaction_key(item) for item in rules.get("redact_keys", []))
    redact_patterns = tuple(str(pattern) for pattern in rules.get("redact_patterns", []))
    return _cached_compiled_redaction_rules(redact_keys, redact_patterns)


@lru_cache(maxsize=512)
def _cached_compiled_redaction_rules(
    redact_keys: tuple[str, ...],
    redact_patterns: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "redact_keys": list(redact_keys),
        "redact_patterns": [safe_regex.compile(pattern) for pattern in redact_patterns],
    }


def _redact_value_at_depth(
    value: Any,
    rules: dict[str, Any],
    *,
    key: str = "",
    depth: int,
) -> tuple[Any, bool]:
    if depth > MAX_REDACTION_DEPTH:
        return "[truncated]", True
    redact_keys = rules.get("redact_keys", [])
    redact_patterns = rules.get("redact_patterns", [])
    lowered = key.lower()
    normalized_key = _normalize_redaction_key(lowered)
    if key and _is_redaction_key_match(normalized_key, redact_keys):
        return REDACTED_VALUE, True
    if isinstance(value, dict):
        changed = False
        output: dict[str, Any] = {}
        for child_key, child_value in value.items():
            redacted, child_changed = _redact_value_at_depth(
                child_value,
                rules,
                key=str(child_key),
                depth=depth + 1,
            )
            output[str(child_key)] = redacted
            changed = changed or child_changed
        return output, changed
    if isinstance(value, list):
        changed = False
        output_list = []
        for item in value:
            redacted, child_changed = _redact_value_at_depth(
                item,
                rules,
                key=key,
                depth=depth + 1,
            )
            output_list.append(redacted)
            changed = changed or child_changed
        return output_list, changed
    if isinstance(value, str):
        redacted = value[:MAX_REDACTION_STRING_CHARS]
        truncated = len(value) > MAX_REDACTION_STRING_CHARS
        changed = False
        for pattern in redact_patterns:
            try:
                redacted, count = pattern.subn(
                    REDACTED_VALUE,
                    redacted,
                    timeout=REDACTION_REGEX_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                return REDACTED_VALUE, True
            changed = changed or count > 0
        if truncated:
            redacted = f"{redacted}..."
            changed = True
        return redacted, changed
    return value, False


def validate_redaction_rules(rules: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize response redaction rules at policy-write time."""

    allowed = {"redact_keys", "redact_patterns"}
    unknown = set(rules) - allowed
    if unknown:
        raise ValueError(f"unsupported redaction rule keys: {', '.join(sorted(unknown))}.")
    normalized: dict[str, Any] = {}
    for key in ["redact_keys", "redact_patterns"]:
        if key in rules and (
            not isinstance(rules[key], list)
            or not all(isinstance(item, str) and item.strip() for item in rules[key])
        ):
            raise ValueError(f"{key} must be a list of nonblank strings.")
    normalized["redact_keys"] = [
        item.strip()
        for item in rules.get("redact_keys", [])
    ]
    normalized["redact_patterns"] = [
        _validate_redaction_pattern(item.strip())
        for item in rules.get("redact_patterns", [])
    ]
    return {key: value for key, value in normalized.items() if key in rules}


def _validate_redaction_pattern(pattern: str) -> str:
    try:
        safe_regex.compile(pattern)
    except safe_regex.error as exc:
        raise ValueError(f"invalid redaction regex pattern: {exc}") from exc
    if len(pattern) > MAX_REDACTION_PATTERN_LENGTH:
        raise ValueError(
            f"redact_patterns entries must be {MAX_REDACTION_PATTERN_LENGTH} characters or fewer."
        )
    # Keep policy regexes simple enough to avoid obvious catastrophic backtracking.
    if re.search(r"\([^)]*[+*][^)]*\)[+*?]", pattern):
        raise ValueError("redact_patterns entries must not contain nested unbounded quantifiers.")
    if re.search(r"(?:\.\*|\.\+).*(?:\.\*|\.\+)", pattern):
        raise ValueError("redact_patterns entries must not contain multiple unbounded wildcards.")
    if re.search(r"(\[[^\]]+\]|\w)[+*].*(\[[^\]]+\]|\w)[+*]", pattern):
        raise ValueError("redact_patterns entries must not contain repeated unbounded atoms.")
    return pattern


def _normalize_redaction_key(key: str) -> str:
    with_word_boundaries = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key.strip())
    return re.sub(r"[^a-z0-9]+", "_", with_word_boundaries.lower()).strip("_")


def _is_redaction_key_match(normalized_key: str, redact_keys: list[str]) -> bool:
    normalized_rules = [_normalize_redaction_key(rule) for rule in redact_keys]
    return any(
        normalized_key == rule
        or normalized_key.endswith(f"_{rule}")
        or rule.endswith(f"_{normalized_key}")
        for rule in normalized_rules
        if rule
    )


def _response_size(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, default=str).encode("utf-8"))
