"""Marketplace plugin artifact evidence validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


PASS_STATUSES = {"allow", "allowed", "approve", "approved", "clean", "pass", "passed"}
BLOCK_STATUSES = {"block", "blocked", "deny", "denied", "fail", "failed", "malicious", "vulnerable"}
_SHA256_RE = re.compile(r"^(sha256:)?[a-fA-F0-9]{64}$")


@dataclass(frozen=True)
class PluginArtifactEvidenceEvaluation:
    status: str
    findings: list[dict[str, Any]]


def normalize_plugin_artifact_evidence(value: Any) -> dict[str, Any]:
    """Normalize plugin artifact provenance and scan evidence from a manifest or API body."""

    if not isinstance(value, dict):
        raise ValueError("artifact_evidence must be an object.")
    digest_algorithm = str(value.get("digest_algorithm") or "sha256").strip().lower()
    if digest_algorithm != "sha256":
        raise ValueError("artifact_evidence.digest_algorithm must be sha256.")
    artifact_digest = _normalize_sha256(value.get("artifact_digest") or value.get("digest") or value.get("sha256"))
    evidence = {
        "artifact_digest": artifact_digest,
        "digest_algorithm": digest_algorithm,
        "provenance": _dict_field(value, "provenance"),
        "sbom": _dict_field(value, "sbom"),
        "license": _dict_field(value, "license"),
        "vulnerability_scan": _dict_field(value, "vulnerability_scan"),
        "malware_scan": _dict_field(value, "malware_scan"),
    }
    evaluation = evaluate_plugin_artifact_evidence(evidence)
    return {
        **evidence,
        "status": evaluation.status,
        "findings": evaluation.findings,
    }


def evaluate_plugin_artifact_evidence(evidence: dict[str, Any] | None) -> PluginArtifactEvidenceEvaluation:
    """Return blocking findings for missing or failed artifact evidence."""

    if evidence is None:
        return PluginArtifactEvidenceEvaluation(
            status="missing",
            findings=[
                _finding(
                    "artifact_evidence_missing",
                    "Plugin install requires immutable artifact digest, provenance, SBOM, license, vulnerability, and malware evidence.",
                    field="artifact_evidence",
                    details={},
                )
            ],
        )

    findings: list[dict[str, Any]] = []
    artifact_digest = evidence.get("artifact_digest")
    if not isinstance(artifact_digest, str) or not _SHA256_RE.match(artifact_digest):
        findings.append(
            _finding(
                "artifact_digest_missing",
                "Plugin artifact evidence requires a sha256 digest.",
                field="artifact_digest",
                details={"digest_algorithm": evidence.get("digest_algorithm")},
            )
        )
    _require_non_empty_dict(findings, evidence, "provenance", "artifact_provenance_missing")
    _require_non_empty_dict(findings, evidence, "sbom", "artifact_sbom_missing")
    _check_status(findings, evidence, "license", "license_status_blocked")
    _check_status(findings, evidence, "vulnerability_scan", "vulnerability_scan_blocked")
    _check_status(findings, evidence, "malware_scan", "malware_scan_blocked")
    return PluginArtifactEvidenceEvaluation(status="blocked" if findings else "passed", findings=findings)


def _normalize_sha256(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("artifact_evidence.artifact_digest is required.")
    digest = value.strip()
    if digest.startswith("sha256:"):
        digest = digest.removeprefix("sha256:")
    if not _SHA256_RE.match(digest):
        raise ValueError("artifact_evidence.artifact_digest must be a sha256 hex digest.")
    return digest.lower()


def _dict_field(value: dict[str, Any], field_name: str) -> dict[str, Any]:
    field_value = value.get(field_name)
    if field_value is None:
        return {}
    if not isinstance(field_value, dict):
        raise ValueError(f"artifact_evidence.{field_name} must be an object.")
    return field_value


def _require_non_empty_dict(
    findings: list[dict[str, Any]],
    evidence: dict[str, Any],
    field_name: str,
    code: str,
) -> None:
    value = evidence.get(field_name)
    if isinstance(value, dict) and value:
        return
    findings.append(
        _finding(
            code,
            f"Plugin artifact evidence requires {field_name} metadata.",
            field=field_name,
            details={},
        )
    )


def _check_status(
    findings: list[dict[str, Any]],
    evidence: dict[str, Any],
    field_name: str,
    code: str,
) -> None:
    value = evidence.get(field_name)
    if not isinstance(value, dict) or not value:
        findings.append(
            _finding(
                f"{field_name}_missing",
                f"Plugin artifact evidence requires {field_name} status.",
                field=field_name,
                details={},
            )
        )
        return
    status = str(value.get("status") or value.get("result") or "").strip().lower()
    if status in PASS_STATUSES:
        return
    if status in BLOCK_STATUSES:
        message = f"Plugin artifact {field_name} status blocks installation."
    else:
        message = f"Plugin artifact {field_name} status must be passing."
    findings.append(
        _finding(
            code,
            message,
            field=field_name,
            details={"status": status or None, "findings": value.get("findings", [])},
        )
    )


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
