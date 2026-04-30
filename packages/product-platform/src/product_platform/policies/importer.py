"""Policy import parsing and validation helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from product_platform.policies.models import (
    POLICY_BODY_FORMATS,
    PolicyCreateRequest,
    PolicyImportRequest,
    PolicyVersionCreateRequest,
)

KNOWN_OPERATORS = {"eq", "ne", "gt", "lt", "gte", "lte", "in", "matches", "contains"}
KNOWN_ACTIONS = {"allow", "deny", "audit", "block"}


@dataclass(frozen=True)
class PreparedPolicyImport:
    """A parsed policy import ready for persistence."""

    policy: PolicyCreateRequest
    version: PolicyVersionCreateRequest
    source_type: str
    source_path: str | None
    summary: dict[str, Any]


def prepare_policy_import(request: PolicyImportRequest) -> PreparedPolicyImport:
    """Read, parse, validate, and normalize a policy import request."""

    body_text, source_type, source_path, body_format = _resolve_import_body(request)
    parsed = _parse_body(body_text, body_format)
    warnings = _validate_policy_shape(parsed)
    name = request.name or _string_or_none(parsed.get("name")) or _fallback_name(source_path)
    description = request.description
    if description is None:
        description = _string_or_none(parsed.get("description")) or ""
    policy = PolicyCreateRequest(
        name=name,
        slug=request.slug,
        description=description,
        scope=request.scope,
        owner_user_id=request.owner_user_id,
        tags=request.tags,
    )
    version = PolicyVersionCreateRequest(
        body_format=body_format,
        body_text=body_text,
        backend=request.backend,
    )
    summary = {
        "name": policy.name,
        "format": body_format,
        "backend": request.backend,
        "rule_count": _rule_count(parsed),
        "source_type": source_type,
        "source_path": source_path,
        "warnings": warnings,
    }
    return PreparedPolicyImport(
        policy=policy,
        version=version,
        source_type=source_type,
        source_path=source_path,
        summary=summary,
    )


def _resolve_import_body(request: PolicyImportRequest) -> tuple[str, str, str | None, str]:
    if request.body_text and request.body_text.strip():
        body_format = request.body_format or "yaml"
        return request.body_text, "body", request.source_path, body_format
    if request.source_path is None:
        raise ValueError("source_path is required when body_text is not provided.")
    path = _safe_repo_path(request.source_path)
    body_format = request.body_format or _format_from_path(path)
    return path.read_text(encoding="utf-8"), "repo_path", str(path.relative_to(_repo_root())), body_format


def _format_from_path(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    if suffix == "yml":
        return "yaml"
    if suffix in POLICY_BODY_FORMATS:
        return suffix
    raise ValueError(f"Cannot infer policy body format from path: {path}")


def _safe_repo_path(raw_path: str) -> Path:
    repo_root = _repo_root()
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    resolved = candidate.resolve()
    if not resolved.exists() or not resolved.is_file():
        raise ValueError(f"Policy source path does not exist: {raw_path}")
    if repo_root not in resolved.parents and resolved != repo_root:
        raise ValueError("Policy source path must be inside the repository.")
    return resolved


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "packages").exists() and (parent / "examples").exists():
            return parent
    return current.parents[6]


def _parse_body(body_text: str, body_format: str) -> dict[str, Any]:
    try:
        if body_format == "json":
            parsed = json.loads(body_text)
        elif body_format == "yaml":
            import yaml

            parsed = yaml.safe_load(body_text)
        else:
            parsed = {"name": f"{body_format} policy", "rules": []}
    except (json.JSONDecodeError, Exception) as exc:
        raise ValueError(f"Invalid {body_format.upper()} policy body: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Policy body must parse to a mapping/object.")
    return parsed


def _validate_policy_shape(parsed: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    required = ["version", "name", "rules"]
    missing = [field for field in required if field not in parsed]
    if missing:
        raise ValueError(f"Policy body is missing required field(s): {', '.join(missing)}.")
    rules = parsed.get("rules")
    if not isinstance(rules, list):
        raise ValueError("Policy body field 'rules' must be a list.")
    if not rules:
        warnings.append("Policy contains no rules.")
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"Rule {index} must be an object.")
        if "name" not in rule:
            raise ValueError(f"Rule {index} is missing required field: name.")
        action = rule.get("action")
        if action not in KNOWN_ACTIONS:
            raise ValueError(f"Rule '{rule.get('name')}': unknown action '{action}'.")
        condition = rule.get("condition")
        if not isinstance(condition, dict):
            raise ValueError(f"Rule '{rule.get('name')}': condition must be an object.")
        for field in ["field", "operator", "value"]:
            if field not in condition:
                raise ValueError(f"Rule '{rule.get('name')}': condition missing '{field}'.")
        operator = condition.get("operator")
        if operator not in KNOWN_OPERATORS:
            raise ValueError(f"Rule '{rule.get('name')}': unknown operator '{operator}'.")
    try:
        PolicyCreateRequest(name=str(parsed["name"]), scope="agent")
    except ValidationError as exc:
        raise ValueError(f"Policy metadata validation failed: {exc}") from exc
    return warnings


def _rule_count(parsed: dict[str, Any]) -> int:
    rules = parsed.get("rules")
    return len(rules) if isinstance(rules, list) else 0


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _fallback_name(source_path: str | None) -> str:
    if source_path:
        return Path(source_path).stem.replace("-", " ").replace("_", " ").title()
    return "Imported Policy"
