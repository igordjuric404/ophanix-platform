"""Policy library API models."""

from __future__ import annotations

import re

from typing import Any

from pydantic import BaseModel, Field, model_validator, field_validator

POLICY_SCOPES = {
    "global",
    "environment",
    "agent",
    "agent-group",
    "mcp-server",
    "mcp-tool",
    "runtime-action",
    "framework-connector",
    "discovery",
}
POLICY_STATUSES = {"draft", "active", "archived"}
POLICY_VERSION_STATUSES = {"draft", "active", "inactive", "archived"}
POLICY_BODY_FORMATS = {"yaml", "json", "rego", "cedar"}
POLICY_BACKENDS = {"native", "opa", "cedar"}
POLICY_BINDING_TARGET_TYPES = {
    "agent",
    "agent-group",
    "mcp-server",
    "mcp-tool",
    "runtime-action",
    "environment",
    "framework-connector",
    "discovery",
}
POLICY_BINDING_MODES = {"enforce", "shadow", "audit-only", "disabled"}
POLICY_BINDING_STATUSES = {"active", "inactive", "deleted"}
POLICY_EVALUATION_MODES = {"simulate", "live"}
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class PolicyCreateRequest(BaseModel):
    """Create a policy library entry."""

    name: str = Field(min_length=1)
    slug: str | None = None
    description: str = ""
    scope: str = "agent"
    owner_user_id: str | None = None
    status: str = "draft"
    tags: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank.")
        return stripped

    @field_validator("slug")
    @classmethod
    def _strip_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip().lower()
        if stripped and not SLUG_PATTERN.match(stripped):
            raise ValueError("slug must contain lowercase letters, numbers, and hyphens.")
        return stripped or None

    @field_validator("description")
    @classmethod
    def _strip_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("scope")
    @classmethod
    def _validate_scope(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in POLICY_SCOPES:
            raise ValueError(f"scope must be one of: {', '.join(sorted(POLICY_SCOPES))}.")
        return normalized

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in POLICY_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(POLICY_STATUSES))}.")
        return normalized

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for tag in value:
            clean = tag.strip().lower()
            if clean and clean not in seen:
                seen.add(clean)
                normalized.append(clean)
        return normalized


class PolicyVersionCreateRequest(BaseModel):
    """Create an immutable policy version body."""

    body_format: str = "yaml"
    body_text: str = Field(min_length=1)
    backend: str = "native"
    status: str = "draft"

    @field_validator("body_format")
    @classmethod
    def _validate_body_format(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in POLICY_BODY_FORMATS:
            raise ValueError(
                f"body_format must be one of: {', '.join(sorted(POLICY_BODY_FORMATS))}."
            )
        return normalized

    @field_validator("body_text")
    @classmethod
    def _strip_body_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("body_text must not be blank.")
        return value

    @field_validator("backend")
    @classmethod
    def _validate_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in POLICY_BACKENDS:
            raise ValueError(f"backend must be one of: {', '.join(sorted(POLICY_BACKENDS))}.")
        return normalized

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in POLICY_VERSION_STATUSES:
            raise ValueError(
                f"status must be one of: {', '.join(sorted(POLICY_VERSION_STATUSES))}."
            )
        return normalized


class PolicyVersionResponse(BaseModel):
    """Policy version returned by API endpoints."""

    id: str
    policy_id: str
    version_number: int
    body_format: str
    body_text: str
    backend: str
    checksum: str
    status: str
    created_by: str
    created_at: str
    activated_at: str | None = None
    archived_at: str | None = None


class PolicyResponse(BaseModel):
    """Policy library row returned by API endpoints."""

    id: str
    organization_id: str
    name: str
    slug: str
    description: str
    scope: str
    owner_user_id: str
    status: str
    tags: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    active_version_id: str | None = None
    active_version_number: int | None = None
    version_count: int = 0


class PolicyDetailResponse(PolicyResponse):
    """Policy detail response with version history."""

    versions: list[PolicyVersionResponse] = Field(default_factory=list)


class PolicyImportRequest(BaseModel):
    """Import a policy from inline body text or a known repository path."""

    body_text: str | None = None
    body_format: str | None = None
    source_path: str | None = None
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    scope: str = "agent"
    owner_user_id: str | None = None
    backend: str = "native"
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_body_or_path(self) -> "PolicyImportRequest":
        if not (self.body_text and self.body_text.strip()) and not (
            self.source_path and self.source_path.strip()
        ):
            raise ValueError("body_text or source_path is required.")
        return self

    @field_validator("body_format")
    @classmethod
    def _validate_optional_body_format(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in POLICY_BODY_FORMATS:
            raise ValueError(
                f"body_format must be one of: {', '.join(sorted(POLICY_BODY_FORMATS))}."
            )
        return normalized

    @field_validator("source_path", "name", "slug", "description", "owner_user_id")
    @classmethod
    def _strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("scope")
    @classmethod
    def _validate_scope(cls, value: str) -> str:
        return PolicyCreateRequest._validate_scope(value)

    @field_validator("backend")
    @classmethod
    def _validate_backend(cls, value: str) -> str:
        return PolicyVersionCreateRequest._validate_backend(value)

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: list[str]) -> list[str]:
        return PolicyCreateRequest._normalize_tags(value)


class PolicyImportResponse(BaseModel):
    """Response returned after a policy import."""

    id: str
    source_type: str
    source_path: str | None = None
    status: str
    summary: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    policy: PolicyResponse
    version: PolicyVersionResponse
    created_at: str


class PolicyExportResponse(BaseModel):
    """Exported immutable policy version body."""

    filename: str
    content_type: str
    policy: PolicyResponse
    version: PolicyVersionResponse
    body_text: str
    checksum: str


class PolicyLintRequest(BaseModel):
    """Lint an unsaved or saved policy body."""

    body_text: str = Field(min_length=1)
    body_format: str = "yaml"

    @field_validator("body_text")
    @classmethod
    def _strip_body_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("body_text must not be blank.")
        return value

    @field_validator("body_format")
    @classmethod
    def _validate_body_format(cls, value: str) -> str:
        return PolicyVersionCreateRequest._validate_body_format(value)


class PolicyLintIssue(BaseModel):
    """One structured policy lint issue."""

    severity: str
    code: str
    message: str
    path: str
    line: int | None = None
    fatal: bool = False


class PolicyLintResponse(BaseModel):
    """Aggregated policy lint response."""

    passed: bool
    error_count: int
    warning_count: int
    issues: list[PolicyLintIssue] = Field(default_factory=list)


class PolicyAffectedResource(BaseModel):
    """Resource that references or will be affected by a policy."""

    target_type: str
    target_id: str
    label: str
    status: str
    mode: str | None = None
    environment_id: str | None = None


class PolicyAffectedResourcesResponse(BaseModel):
    """Affected resources grouped for editor warnings."""

    policy_id: str
    resources: list[PolicyAffectedResource] = Field(default_factory=list)
    active_binding_count: int = 0


class PolicyBindingCreateRequest(BaseModel):
    """Create a policy binding to a product target."""

    policy_id: str = Field(min_length=1)
    policy_version_id: str | None = None
    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    mode: str = "shadow"
    rollout_percentage: int = Field(default=100, ge=0, le=100)
    priority: int = 0
    status: str = "active"

    @field_validator("policy_id", "policy_version_id", "target_id")
    @classmethod
    def _strip_optional_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Identifier fields must not be blank.")
        return stripped

    @field_validator("target_type")
    @classmethod
    def _validate_target_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in POLICY_BINDING_TARGET_TYPES:
            raise ValueError(
                f"target_type must be one of: {', '.join(sorted(POLICY_BINDING_TARGET_TYPES))}."
            )
        return normalized

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in POLICY_BINDING_MODES:
            raise ValueError(f"mode must be one of: {', '.join(sorted(POLICY_BINDING_MODES))}.")
        return normalized

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in POLICY_BINDING_STATUSES:
            raise ValueError(
                f"status must be one of: {', '.join(sorted(POLICY_BINDING_STATUSES))}."
            )
        return normalized


class PolicyBindingPatchRequest(BaseModel):
    """Patch mutable policy binding controls."""

    mode: str | None = None
    rollout_percentage: int | None = Field(default=None, ge=0, le=100)
    priority: int | None = None
    status: str | None = None

    @field_validator("mode")
    @classmethod
    def _validate_optional_mode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return PolicyBindingCreateRequest._validate_mode(value)

    @field_validator("status")
    @classmethod
    def _validate_optional_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return PolicyBindingCreateRequest._validate_status(value)


class PolicyBindingResponse(BaseModel):
    """Policy binding returned by API endpoints."""

    id: str
    organization_id: str
    environment_id: str
    policy_id: str
    policy_version_id: str
    target_type: str
    target_id: str
    mode: str
    rollout_percentage: int
    priority: int
    status: str
    created_by: str
    created_at: str
    updated_at: str


class PolicyExceptionCreateRequest(BaseModel):
    """Create an exception for a policy binding."""

    target_type: str | None = None
    target_id: str | None = None
    reason: str = Field(min_length=1)
    expires_at: str | None = None
    approved_by: str | None = None
    no_expiry_approved: bool = False

    @model_validator(mode="after")
    def _require_expiration_or_approval(self) -> "PolicyExceptionCreateRequest":
        if self.expires_at is None and not self.no_expiry_approved:
            raise ValueError("expires_at is required unless no_expiry_approved is true.")
        return self

    @field_validator("target_type")
    @classmethod
    def _validate_optional_target_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return PolicyBindingCreateRequest._validate_target_type(value)

    @field_validator("target_id", "reason", "expires_at", "approved_by")
    @classmethod
    def _strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped and value is not None:
            raise ValueError("Fields must not be blank.")
        return stripped


class PolicyExceptionResponse(BaseModel):
    """Policy exception returned by API endpoints."""

    id: str
    binding_id: str
    target_type: str
    target_id: str
    reason: str
    expires_at: str | None = None
    created_by: str
    approved_by: str | None = None
    created_at: str


class PolicyBindingPromoteRequest(BaseModel):
    """Promote binding mode or rollout percentage with an operator reason."""

    mode: str | None = None
    rollout_percentage: int | None = Field(default=None, ge=0, le=100)
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def _require_change(self) -> "PolicyBindingPromoteRequest":
        if self.mode is None and self.rollout_percentage is None:
            raise ValueError("mode or rollout_percentage is required.")
        return self

    @field_validator("mode")
    @classmethod
    def _validate_optional_mode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return PolicyBindingCreateRequest._validate_mode(value)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason must not be blank.")
        return stripped


class PolicyBindingResolutionContext(BaseModel):
    """Context used to resolve applicable policy bindings."""

    organization_id: str
    environment_id: str
    target_type: str
    target_id: str
    agent_id: str | None = None
    correlation_id: str | None = None

    @field_validator("target_type")
    @classmethod
    def _validate_target_type(cls, value: str) -> str:
        return PolicyBindingCreateRequest._validate_target_type(value)


class PolicyEvaluationRequest(BaseModel):
    """Request to evaluate a policy version or the active binding for a target."""

    policy_id: str | None = None
    policy_version_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    agent_id: str | None = None
    action: str = Field(min_length=1)
    resource_type: str | None = None
    resource_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    backend: str | None = None
    mode: str = "simulate"

    @model_validator(mode="after")
    def _require_policy_or_target(self) -> "PolicyEvaluationRequest":
        if self.policy_version_id and not self.policy_id:
            raise ValueError("policy_id is required when policy_version_id is provided.")
        if self.policy_id:
            return self
        if not (self.target_type and self.target_id):
            raise ValueError("policy_id or target_type/target_id is required.")
        return self

    @field_validator(
        "policy_id",
        "policy_version_id",
        "target_id",
        "agent_id",
        "action",
        "resource_type",
        "resource_id",
    )
    @classmethod
    def _strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("String fields must not be blank.")
        return stripped

    @field_validator("target_type")
    @classmethod
    def _validate_optional_target_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return PolicyBindingCreateRequest._validate_target_type(value)

    @field_validator("backend")
    @classmethod
    def _validate_optional_backend(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return PolicyVersionCreateRequest._validate_backend(value)

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in POLICY_EVALUATION_MODES:
            raise ValueError(f"mode must be one of: {', '.join(sorted(POLICY_EVALUATION_MODES))}.")
        return normalized


class PolicyEvaluationResponse(BaseModel):
    """Normalized decision returned by the policy evaluation adapter and API."""

    id: str | None = None
    organization_id: str
    environment_id: str
    policy_id: str | None = None
    policy_version_id: str | None = None
    binding_id: str | None = None
    binding_mode: str | None = None
    agent_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    decision: str
    policy_action: str
    matched_rule: str | None = None
    reason: str
    latency_ms: float
    mode: str
    correlation_id: str | None = None
    backend: str
    error: bool = False
    audit_preview: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
