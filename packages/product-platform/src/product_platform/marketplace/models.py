"""Marketplace API models and manifest validation."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from product_platform.marketplace.signing import (
    SIGNATURE_ALGORITHM_ED25519,
    PluginSignatureError,
    ed25519_public_key_fingerprint,
)
from product_platform.marketplace.artifact_evidence import normalize_plugin_artifact_evidence


SUPPORTED_PLUGIN_TYPES = {"policy_template", "integration", "agent", "validator"}
SUPPORTED_SIGNATURE_STATUSES = {"signed", "unsigned", "invalid", "unknown"}
SUPPORTED_SIGNING_KEY_TYPES = {SIGNATURE_ALGORITHM_ED25519}
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+(\.[0-9]+)?$")
PLUGIN_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class NormalizedPluginManifest(BaseModel):
    """Validated marketplace manifest with product-derived fields."""

    name: str
    version: str
    description: str
    publisher: str
    plugin_type: str
    package_ref: str
    signature_status: str
    required_capabilities: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    artifact_evidence: dict[str, Any] | None = None
    manifest: dict[str, Any] = Field(default_factory=dict)


class PluginImportRequest(BaseModel):
    """Import a plugin manifest into the product catalog."""

    manifest: dict[str, Any] = Field(default_factory=dict)
    package_ref: str | None = None
    status: str = "available"

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        status = value.strip().lower()
        if status not in {"available", "deprecated", "disabled"}:
            raise ValueError("status must be available, deprecated, or disabled.")
        return status


class PluginVersionResponse(BaseModel):
    """Persisted plugin version."""

    id: str
    plugin_id: str
    version: str
    manifest: dict[str, Any] = Field(default_factory=dict)
    package_ref: str
    signature_status: str
    quality_score: float
    trust_tier: str
    required_capabilities: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    artifact_evidence: "PluginArtifactEvidenceResponse | None" = None
    created_at: str
    updated_at: str


class PluginResponse(BaseModel):
    """Persisted marketplace plugin with versions."""

    id: str
    organization_id: str
    name: str
    description: str
    publisher: str
    plugin_type: str
    status: str
    created_at: str
    updated_at: str
    versions: list[PluginVersionResponse] = Field(default_factory=list)


class PluginPolicyCheckRequest(BaseModel):
    """Policy inputs for marketplace compatibility checks."""

    require_signature: bool = False
    allowed_plugin_types: list[str] | None = None
    allowed_capabilities: list[str] | None = None
    allowed_organizations: list[str] | None = None
    require_review_approval: bool = False
    require_artifact_evidence: bool = False

    @field_validator("allowed_plugin_types")
    @classmethod
    def _validate_allowed_plugin_types(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip().lower() for item in value if item.strip()]
        unsupported = sorted(set(normalized) - SUPPORTED_PLUGIN_TYPES)
        if unsupported:
            raise ValueError(f"Unsupported plugin types: {', '.join(unsupported)}.")
        return normalized

    @field_validator("allowed_capabilities", "allowed_organizations")
    @classmethod
    def _strip_optional_list(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [item.strip() for item in value if item.strip()]


class PluginPolicyResultResponse(BaseModel):
    """Persisted plugin policy compatibility result."""

    id: str
    plugin_version_id: str
    result: str
    findings: list[dict[str, Any]] = Field(default_factory=list)
    policy_input: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class PluginInstallationCreateRequest(BaseModel):
    """Install a plugin version into an environment or agent target."""

    plugin_version_id: str = Field(min_length=1)
    environment_id: str = Field(min_length=1)
    target_agent_id: str | None = None

    @field_validator("plugin_version_id", "environment_id")
    @classmethod
    def _strip_required_identifier(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("target_agent_id")
    @classmethod
    def _strip_optional_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PluginInstallationResponse(BaseModel):
    """Persisted marketplace plugin installation."""

    id: str
    plugin_version_id: str
    plugin_name: str
    version: str
    environment_id: str
    target_agent_id: str | None = None
    target_agent_name: str | None = None
    policy_result_id: str | None = None
    review_id: str | None = None
    artifact_evidence_id: str | None = None
    status: str
    installed_by: str
    installed_at: str
    uninstalled_at: str | None = None


class PluginReviewSubmitRequest(BaseModel):
    """Submit a plugin version for marketplace review."""

    findings: list[dict[str, Any]] = Field(default_factory=list)


class PluginReviewDecisionRequest(BaseModel):
    """Approve or reject a plugin review."""

    decision_reason: str | None = None

    @field_validator("decision_reason")
    @classmethod
    def _strip_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PluginReviewResponse(BaseModel):
    """Persisted plugin marketplace review."""

    id: str
    plugin_version_id: str
    plugin_name: str | None = None
    version: str | None = None
    status: str
    reviewer_id: str | None = None
    findings: list[dict[str, Any]] = Field(default_factory=list)
    decision_reason: str | None = None
    created_at: str
    decided_at: str | None = None


class PluginSigningKeyCreateRequest(BaseModel):
    """Register a marketplace plugin signing key."""

    name: str = Field(min_length=1)
    public_key: str = Field(min_length=1)
    key_type: str = SIGNATURE_ALGORITHM_ED25519
    trusted_root_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"

    @field_validator("name", "public_key")
    @classmethod
    def _strip_required_key_value(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("public_key")
    @classmethod
    def _validate_public_key(cls, value: str) -> str:
        try:
            ed25519_public_key_fingerprint(value)
        except PluginSignatureError as exc:
            raise ValueError(str(exc)) from exc
        return value

    @field_validator("key_type")
    @classmethod
    def _validate_key_type(cls, value: str) -> str:
        key_type = value.strip().lower()
        if key_type not in SUPPORTED_SIGNING_KEY_TYPES:
            supported = ", ".join(sorted(SUPPORTED_SIGNING_KEY_TYPES))
            raise ValueError(f"key_type must be one of: {supported}.")
        return key_type

    @field_validator("trusted_root_id")
    @classmethod
    def _strip_trusted_root_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("status")
    @classmethod
    def _validate_signing_key_status(cls, value: str) -> str:
        status = value.strip().lower()
        if status not in {"active", "revoked"}:
            raise ValueError("status must be active or revoked.")
        return status


class PluginSigningKeyResponse(BaseModel):
    """Persisted plugin signing key metadata."""

    id: str
    organization_id: str
    name: str
    public_key: str
    key_type: str
    trusted_root_id: str | None = None
    public_key_fingerprint: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str
    created_by: str
    created_at: str
    revoked_at: str | None = None


class PluginArtifactEvidenceSubmitRequest(BaseModel):
    """Submit immutable artifact provenance and scan evidence for a plugin version."""

    artifact_evidence: dict[str, Any] = Field(default_factory=dict)


class PluginArtifactEvidenceResponse(BaseModel):
    """Persisted plugin artifact evidence and security scan state."""

    id: str
    plugin_version_id: str
    package_ref: str
    artifact_digest: str
    digest_algorithm: str
    provenance: dict[str, Any] = Field(default_factory=dict)
    sbom: dict[str, Any] = Field(default_factory=dict)
    license: dict[str, Any] = Field(default_factory=dict)
    vulnerability_scan: dict[str, Any] = Field(default_factory=dict)
    malware_scan: dict[str, Any] = Field(default_factory=dict)
    status: str
    findings: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str
    updated_at: str


class PluginQualityAssessmentResponse(BaseModel):
    """Persisted plugin quality assessment."""

    id: str
    plugin_version_id: str
    score: float
    dimensions: dict[str, Any] = Field(default_factory=dict)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str


class PluginTrustRecomputeRequest(BaseModel):
    """Usage and incident signals for plugin trust recomputation."""

    daily_active_users: int = 0
    total_invocations: int = 0
    error_count: int = 0
    incident_count: int = 0
    days_since_update: int = 0
    adoption_trend: float = 0
    source_event_id: str | None = None


class PluginTrustEventResponse(BaseModel):
    """Persisted plugin trust event."""

    id: str
    plugin_version_id: str
    source_event_id: str | None = None
    delta: int
    reason: str
    score_before: int
    score_after: int
    trust_tier: str
    created_at: str


def normalize_plugin_manifest(body: PluginImportRequest) -> NormalizedPluginManifest:
    """Validate and normalize an Agent Marketplace style manifest."""

    manifest = dict(body.manifest)
    name = _required_string(manifest, "name")
    if not PLUGIN_NAME_RE.match(name):
        raise ValueError("Plugin name must contain only letters, numbers, hyphens, or underscores.")
    version = _required_string(manifest, "version")
    if not SEMVER_RE.match(version):
        raise ValueError("Plugin version must use MAJOR.MINOR or MAJOR.MINOR.PATCH format.")
    description = _required_string(manifest, "description")
    publisher = _optional_string(manifest, "publisher") or _required_string(manifest, "author")
    plugin_type = _required_string(manifest, "plugin_type").lower()
    if plugin_type not in SUPPORTED_PLUGIN_TYPES:
        supported = ", ".join(sorted(SUPPORTED_PLUGIN_TYPES))
        raise ValueError(f"plugin_type must be one of: {supported}.")
    package_ref = body.package_ref or _optional_string(manifest, "package_ref")
    if not package_ref:
        raise ValueError("package_ref is required either in the request or manifest.")
    signature_status = _signature_status(manifest)
    required_capabilities = _string_list(
        manifest.get("required_capabilities", manifest.get("capabilities", [])),
        "required_capabilities",
    )
    permissions = _string_list(manifest.get("permissions", []), "permissions")
    manifest["package_ref"] = package_ref
    artifact_evidence = None
    raw_artifact_evidence = manifest.get("artifact_evidence") or manifest.get("artifact")
    if raw_artifact_evidence is not None:
        artifact_evidence = normalize_plugin_artifact_evidence(raw_artifact_evidence)
        package_digest = _optional_string(manifest, "package_digest")
        if package_digest and package_digest.removeprefix("sha256:").lower() != artifact_evidence["artifact_digest"]:
            raise ValueError("package_digest must match artifact_evidence.artifact_digest.")
        manifest["package_digest"] = artifact_evidence["artifact_digest"]
        manifest["artifact_evidence"] = artifact_evidence
    return NormalizedPluginManifest(
        name=name,
        version=version,
        description=description,
        publisher=publisher,
        plugin_type=plugin_type,
        package_ref=package_ref,
        signature_status=signature_status,
        required_capabilities=required_capabilities,
        permissions=permissions,
        artifact_evidence=artifact_evidence,
        manifest=manifest,
    )


def _required_string(manifest: dict[str, Any], field_name: str) -> str:
    value = manifest.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required.")
    return value.strip()


def _optional_string(manifest: dict[str, Any], field_name: str) -> str | None:
    value = manifest.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    stripped = value.strip()
    return stripped or None


def _string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings.")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} must contain only non-empty strings.")
        normalized.append(item.strip())
    return normalized


def _signature_status(manifest: dict[str, Any]) -> str:
    declared = manifest.get("signature_status")
    if declared is not None:
        if not isinstance(declared, str):
            raise ValueError("signature_status must be a string.")
        status = declared.strip().lower()
        if status not in SUPPORTED_SIGNATURE_STATUSES:
            supported = ", ".join(sorted(SUPPORTED_SIGNATURE_STATUSES))
            raise ValueError(f"signature_status must be one of: {supported}.")
        return status
    signature = manifest.get("signature")
    return "signed" if isinstance(signature, str) and signature.strip() else "unsigned"
