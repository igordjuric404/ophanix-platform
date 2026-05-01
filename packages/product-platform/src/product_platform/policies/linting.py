"""Policy lint service for editor and validation workflows."""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from product_platform.policies.importer import KNOWN_ACTIONS, KNOWN_OPERATORS
from product_platform.policies.models import (
    PolicyLintIssue,
    PolicyLintRequest,
    PolicyLintResponse,
)


def lint_policy_body(request: PolicyLintRequest) -> PolicyLintResponse:
    """Lint a policy body and return normalized issues."""

    if request.body_format in {"yaml", "json"}:
        issues = _lint_structured_policy(request.body_text, request.body_format)
    elif request.body_format == "rego":
        issues = _lint_rego_policy(request.body_text)
    elif request.body_format == "cedar":
        issues = _lint_cedar_policy(request.body_text)
    else:
        issues = [
            _issue(
                "error",
                "format.unsupported",
                f"Unsupported body format: {request.body_format}",
                "$",
                fatal=True,
            )
        ]
    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    return PolicyLintResponse(
        passed=error_count == 0,
        error_count=error_count,
        warning_count=warning_count,
        issues=issues,
    )


def _lint_structured_policy(body_text: str, body_format: str) -> list[PolicyLintIssue]:
    if body_format == "yaml":
        external = _lint_with_agent_compliance(body_text)
        if external is not None:
            return external
    parsed, parse_issue = _parse_structured_policy(body_text, body_format)
    if parse_issue is not None:
        return [parse_issue]
    return _schema_issues(parsed)


def _lint_with_agent_compliance(body_text: str) -> list[PolicyLintIssue] | None:
    lint_file = _load_agent_compliance_linter()
    if lint_file is None:
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
        handle.write(body_text)
        path = Path(handle.name)
    try:
        result = lint_file(path)
    finally:
        path.unlink(missing_ok=True)
    return [
        _issue(
            message.severity,
            _code_from_message(message.message),
            message.message,
            f"line:{message.line}",
            line=message.line,
            fatal=message.severity == "error",
        )
        for message in result.messages
    ]


def _load_agent_compliance_linter() -> Any | None:
    try:
        return importlib.import_module("agent_compliance.lint_policy").lint_file
    except ImportError:
        repo_root = _repo_root()
        candidate = repo_root / "packages" / "agent-compliance" / "src"
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        try:
            return importlib.import_module("agent_compliance.lint_policy").lint_file
        except ImportError:
            return None


def _parse_structured_policy(
    body_text: str,
    body_format: str,
) -> tuple[dict[str, Any], PolicyLintIssue | None]:
    try:
        if body_format == "json":
            parsed = json.loads(body_text)
        else:
            import yaml

            parsed = yaml.safe_load(body_text)
    except json.JSONDecodeError as exc:
        return {}, _issue(
            "error",
            "parse.invalid_json",
            f"Invalid JSON: {exc}",
            f"line:{exc.lineno}",
            line=exc.lineno,
            fatal=True,
        )
    except Exception as exc:
        line = getattr(getattr(exc, "problem_mark", None), "line", None)
        line_number = int(line) + 1 if line is not None else 1
        return {}, _issue(
            "error",
            "parse.invalid_yaml",
            f"Invalid YAML: {exc}",
            f"line:{line_number}",
            line=line_number,
            fatal=True,
        )
    if not isinstance(parsed, dict):
        return {}, _issue(
            "error",
            "schema.not_mapping",
            "Policy body must be a mapping/object.",
            "$",
            line=1,
            fatal=True,
        )
    return parsed, None


def _schema_issues(parsed: dict[str, Any]) -> list[PolicyLintIssue]:
    issues: list[PolicyLintIssue] = []
    for field in ["version", "name", "rules"]:
        if field not in parsed:
            issues.append(
                _issue(
                    "error",
                    "schema.missing_required_field",
                    f"Missing required field '{field}'",
                    f"$.{field}",
                    line=1,
                    fatal=True,
                )
            )
    rules = parsed.get("rules")
    if rules is None:
        return issues
    if not isinstance(rules, list):
        issues.append(
            _issue(
                "error",
                "schema.invalid_rules",
                "Field 'rules' must be a list.",
                "$.rules",
                line=1,
                fatal=True,
            )
        )
        return issues
    if not rules:
        issues.append(
            _issue(
                "warning",
                "schema.empty_rules",
                "Rules list is empty.",
                "$.rules",
                line=1,
            )
        )
    for index, rule in enumerate(rules):
        path = f"$.rules[{index}]"
        if not isinstance(rule, dict):
            issues.append(_issue("error", "schema.invalid_rule", "Rule must be an object.", path, fatal=True))
            continue
        action = rule.get("action")
        if action is not None and action not in KNOWN_ACTIONS:
            issues.append(
                _issue(
                    "error",
                    "schema.unknown_action",
                    f"Rule '{rule.get('name', index)}': unknown action '{action}'",
                    f"{path}.action",
                    fatal=True,
                )
            )
        condition = rule.get("condition")
        if not isinstance(condition, dict):
            issues.append(
                _issue(
                    "error",
                    "schema.invalid_condition",
                    f"Rule '{rule.get('name', index)}': condition must be an object.",
                    f"{path}.condition",
                    fatal=True,
                )
            )
            continue
        operator = condition.get("operator")
        if operator is not None and operator not in KNOWN_OPERATORS:
            issues.append(
                _issue(
                    "error",
                    "schema.unknown_operator",
                    f"Rule '{rule.get('name', index)}': unknown operator '{operator}'",
                    f"{path}.condition.operator",
                    fatal=True,
                )
            )
    return issues


def _lint_rego_policy(body_text: str) -> list[PolicyLintIssue]:
    issues: list[PolicyLintIssue] = []
    if "package " not in body_text:
        issues.append(
            _issue(
                "warning",
                "rego.missing_package",
                "Rego policy does not declare a package.",
                "$",
                line=1,
            )
        )
    if "allow" not in body_text and "deny" not in body_text:
        issues.append(
            _issue(
                "warning",
                "rego.no_decision_rule",
                "Rego policy does not appear to define allow or deny.",
                "$",
                line=1,
            )
        )
    return issues


def _lint_cedar_policy(body_text: str) -> list[PolicyLintIssue]:
    if "permit" in body_text or "forbid" in body_text:
        return []
    return [
        _issue(
            "warning",
            "cedar.no_policy_statement",
            "Cedar policy does not appear to contain permit or forbid.",
            "$",
            line=1,
        )
    ]


def _code_from_message(message: str) -> str:
    lower = message.lower()
    if "missing required field" in lower:
        return "schema.missing_required_field"
    if "unknown operator" in lower:
        return "schema.unknown_operator"
    if "unknown action" in lower:
        return "schema.unknown_action"
    if "invalid yaml" in lower:
        return "parse.invalid_yaml"
    if "empty" in lower and "rules" in lower:
        return "schema.empty_rules"
    if "deprecated" in lower:
        return "schema.deprecated_field"
    return "lint.issue"


def _issue(
    severity: str,
    code: str,
    message: str,
    path: str,
    *,
    line: int | None = None,
    fatal: bool = False,
) -> PolicyLintIssue:
    normalized_severity = "error" if severity == "error" else "warning"
    return PolicyLintIssue(
        severity=normalized_severity,
        code=code,
        message=message,
        path=path,
        line=line,
        fatal=fatal or normalized_severity == "error",
    )


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "packages").exists() and (parent / "examples").exists():
            return parent
    return current.parents[6]
