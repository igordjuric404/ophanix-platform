"""Marketplace policy compatibility checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from product_platform.marketplace.models import PluginPolicyCheckRequest


@dataclass(frozen=True)
class PluginPolicyInput:
    """Plugin data required by the policy evaluator."""

    plugin_type: str
    signature_status: str
    required_capabilities: list[str]
    manifest: dict[str, Any]


@dataclass(frozen=True)
class PluginPolicyEvaluation:
    """Compatibility decision and explainable findings."""

    result: str
    findings: list[dict[str, Any]]


def evaluate_plugin_policy(
    plugin: PluginPolicyInput,
    request: PluginPolicyCheckRequest,
) -> PluginPolicyEvaluation:
    """Evaluate a plugin version against marketplace compatibility gates."""

    findings: list[dict[str, Any]] = []
    if request.allowed_plugin_types is not None and plugin.plugin_type not in request.allowed_plugin_types:
        findings.append(
            _finding(
                "plugin_type_not_allowed",
                "Plugin type is not allowed by marketplace policy.",
                field="plugin_type",
                details={
                    "plugin_type": plugin.plugin_type,
                    "allowed_plugin_types": request.allowed_plugin_types,
                },
            )
        )
    if request.require_signature and plugin.signature_status != "signed":
        findings.append(
            _finding(
                "signature_required",
                "Plugin must have a valid signature before installation.",
                field="signature_status",
                details={"signature_status": plugin.signature_status},
            )
        )
    if request.allowed_capabilities is not None:
        allowed = set(request.allowed_capabilities)
        disallowed = [capability for capability in plugin.required_capabilities if capability not in allowed]
        if disallowed:
            findings.append(
                _finding(
                    "capability_not_allowed",
                    "Plugin requires capabilities outside the allowed marketplace set.",
                    field="required_capabilities",
                    details={"disallowed_capabilities": disallowed},
                )
            )
    if request.allowed_organizations is not None:
        manifest_org = str(plugin.manifest.get("organization") or "global")
        if manifest_org not in request.allowed_organizations:
            findings.append(
                _finding(
                    "organization_not_allowed",
                    "Plugin organization is not allowed by marketplace policy.",
                    field="organization",
                    details={
                        "organization": manifest_org,
                        "allowed_organizations": request.allowed_organizations,
                    },
                )
            )
    if request.require_review_approval and bool(plugin.manifest.get("review_required")):
        review_status = str(plugin.manifest.get("review_status") or "not_submitted")
        if review_status != "approved":
            findings.append(
                _finding(
                    "review_not_approved",
                    "Plugin requires marketplace review approval before installation.",
                    field="review_status",
                    details={"review_status": review_status},
                )
            )
    return PluginPolicyEvaluation(result="deny" if findings else "allow", findings=findings)


def _finding(
    code: str,
    message: str,
    *,
    field: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "blocking",
        "field": field,
        "message": message,
        "details": details,
    }
