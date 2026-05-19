"""Integration registry API models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


SUPPORTED_PROVIDER_CREDENTIAL_SUBJECT_TYPES = {
    "agent",
    "organization",
    "service_account",
    "user",
}
SUPPORTED_PROVIDER_CREDENTIAL_TYPES = {
    "api_key",
    "custom",
    "oauth",
    "service_account",
}
SUPPORTED_PROVIDER_CREDENTIAL_STATUSES = {
    "active",
    "disabled",
    "revoked",
}
SUPPORTED_PROVIDER_CREDENTIAL_ROTATION_STATUSES = {
    "current",
    "rotated",
    "rotating",
    "rotation_due",
    "revoked",
}


class FrameworkIntegrationResponse(BaseModel):
    """Supported framework catalog entry."""

    id: str
    integration_type: str
    name: str
    description: str
    status: str
    supported_versions: list[str] = Field(default_factory=list)
    setup_doc_url: str | None = None
    example_path: str | None = None
    setup_snippet: str | None = None
    created_at: str
    updated_at: str


class FrameworkInstanceCreateRequest(BaseModel):
    """Create a configured framework connector instance."""

    integration_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"

    @field_validator("integration_id", "name", "status")
    @classmethod
    def _strip_required_string(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped


class FrameworkInstancePatchRequest(BaseModel):
    """Update a configured framework connector instance."""

    name: str | None = None
    config: dict[str, Any] | None = None
    status: str | None = None

    @field_validator("name", "status")
    @classmethod
    def _strip_optional_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class FrameworkInstanceResponse(BaseModel):
    """Persisted framework connector instance."""

    id: str
    organization_id: str
    environment_id: str
    integration_id: str
    integration_name: str
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    status: str
    created_by: str
    created_at: str
    updated_at: str


class FrameworkAgentLinkRequest(BaseModel):
    """Link an agent inventory record to a framework connector instance."""

    agent_id: str = Field(min_length=1)
    framework_agent_ref: str = Field(min_length=1)
    sdk_version: str = Field(min_length=1)
    telemetry_status: str = "unknown"
    policy_coverage_status: str = "unknown"

    @field_validator(
        "agent_id",
        "framework_agent_ref",
        "sdk_version",
        "telemetry_status",
        "policy_coverage_status",
    )
    @classmethod
    def _strip_link_string(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped


class FrameworkAgentResponse(BaseModel):
    """Agent linked to a framework connector instance."""

    id: str
    integration_instance_id: str
    integration_name: str
    agent_id: str
    agent_name: str
    framework_agent_ref: str
    sdk_version: str
    telemetry_status: str
    policy_coverage_status: str
    linked_at: str
    updated_at: str


class ProviderCredentialCreateRequest(BaseModel):
    """Create a provider credential by storing only a secret reference."""

    name: str = Field(min_length=1)
    provider_type: str = Field(min_length=1)
    secret_value: str | None = Field(default=None, min_length=1)
    secret_ref: str | None = Field(default=None, min_length=1)
    status: str = "active"
    subject_type: str = "organization"
    subject_id: str | None = None
    provider_account_id: str | None = None
    credential_type: str = "api_key"
    scopes: list[str] = Field(default_factory=list)
    expires_at: str | None = None
    rotation_status: str = "current"
    allowed_tool_ids: list[str] = Field(default_factory=list)

    @field_validator(
        "name",
        "provider_type",
        "secret_value",
        "secret_ref",
        "status",
        "subject_type",
        "subject_id",
        "provider_account_id",
        "credential_type",
        "expires_at",
        "rotation_status",
    )
    @classmethod
    def _strip_credential_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        status = value.strip().lower()
        if status not in SUPPORTED_PROVIDER_CREDENTIAL_STATUSES:
            supported = ", ".join(sorted(SUPPORTED_PROVIDER_CREDENTIAL_STATUSES))
            raise ValueError(f"status must be one of: {supported}.")
        return status

    @field_validator("subject_type")
    @classmethod
    def _validate_subject_type(cls, value: str) -> str:
        subject_type = value.strip().lower()
        if subject_type not in SUPPORTED_PROVIDER_CREDENTIAL_SUBJECT_TYPES:
            supported = ", ".join(sorted(SUPPORTED_PROVIDER_CREDENTIAL_SUBJECT_TYPES))
            raise ValueError(f"subject_type must be one of: {supported}.")
        return subject_type

    @field_validator("credential_type")
    @classmethod
    def _validate_credential_type(cls, value: str) -> str:
        credential_type = value.strip().lower()
        if credential_type not in SUPPORTED_PROVIDER_CREDENTIAL_TYPES:
            supported = ", ".join(sorted(SUPPORTED_PROVIDER_CREDENTIAL_TYPES))
            raise ValueError(f"credential_type must be one of: {supported}.")
        return credential_type

    @field_validator("rotation_status")
    @classmethod
    def _validate_rotation_status(cls, value: str) -> str:
        rotation_status = value.strip().lower()
        if rotation_status not in SUPPORTED_PROVIDER_CREDENTIAL_ROTATION_STATUSES:
            supported = ", ".join(sorted(SUPPORTED_PROVIDER_CREDENTIAL_ROTATION_STATUSES))
            raise ValueError(f"rotation_status must be one of: {supported}.")
        return rotation_status

    @field_validator("scopes", "allowed_tool_ids")
    @classmethod
    def _normalize_string_list(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                raise ValueError("items must be strings.")
            stripped = item.strip()
            if not stripped:
                raise ValueError("items must not be blank.")
            if stripped in seen:
                continue
            seen.add(stripped)
            normalized.append(stripped)
        return normalized

    @model_validator(mode="after")
    def _require_exactly_one_secret_source(self) -> "ProviderCredentialCreateRequest":
        if bool(self.secret_value) == bool(self.secret_ref):
            raise ValueError("Exactly one of secret_value or secret_ref is required.")
        if self.subject_type != "organization" and self.subject_id is None:
            raise ValueError("subject_id is required unless subject_type is organization.")
        return self


class ProviderCredentialResponse(BaseModel):
    """Provider credential metadata with a masked secret display."""

    id: str
    organization_id: str
    environment_id: str
    name: str
    provider_type: str
    subject_type: str
    subject_id: str | None = None
    subject_id_redacted: bool = True
    provider_account_id: str | None = None
    provider_account_id_redacted: bool = True
    credential_type: str
    scopes: list[str] = Field(default_factory=list)
    expires_at: str | None = None
    rotation_status: str
    revoked_at: str | None = None
    revoked_by: str | None = None
    revoked_reason: str | None = None
    allowed_tool_ids: list[str] = Field(default_factory=list)
    secret_ref: str | None = None
    secret_ref_redacted: bool = True
    masked_secret: str
    status: str
    created_by: str
    created_at: str
    updated_at: str
    last_used_at: str | None = None


class IntegrationHealthCheckCreateRequest(BaseModel):
    """Create an integration health-check record."""

    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    latency_ms: int = Field(ge=0)
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("target_type", "target_id", "status", "message")
    @classmethod
    def _strip_health_string(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped


class IntegrationHealthCheckResponse(BaseModel):
    """Persisted integration health check."""

    id: str
    organization_id: str
    environment_id: str
    target_type: str
    target_id: str
    status: str
    latency_ms: int
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    checked_at: str
