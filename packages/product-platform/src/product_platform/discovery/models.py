"""Discovery scan runner API models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class DiscoveryScannerResponse(BaseModel):
    """Scanner metadata exposed to the product UI/API."""

    id: str
    scanner_type: str
    name: str
    description: str
    status: str
    available: bool
    required_config: list[str] = Field(default_factory=list)
    optional_config: list[str] = Field(default_factory=list)
    config_schema: dict = Field(default_factory=dict)


class DiscoveryTargetCreateRequest(BaseModel):
    """Create a tenant-scoped discovery scan target."""

    scanner_type: str = Field(min_length=1)
    target_type: str = Field(min_length=1)
    target_value: str = Field(min_length=1)
    credentials_ref: str | None = None
    schedule_id: str | None = None
    enabled: bool = True
    config_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("scanner_type", "target_type", "target_value")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be blank.")
        return stripped

    @field_validator("credentials_ref", "schedule_id")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class DiscoveryTargetSchedulePatch(BaseModel):
    """Patch target scheduling controls."""

    mode: str = Field(default="manual", min_length=1)
    enabled: bool = True
    next_run_at: str | None = None

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str) -> str:
        mode = value.strip().lower()
        if mode not in {"manual", "hourly", "daily"}:
            raise ValueError("mode must be one of manual, hourly, or daily.")
        return mode

    @field_validator("next_run_at")
    @classmethod
    def _strip_next_run_at(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class DiscoveryTargetResponse(BaseModel):
    """Discovery target returned by the API."""

    id: str
    organization_id: str
    environment_id: str
    scanner_id: str
    scanner_type: str
    target_type: str
    target_value: str
    credentials_ref: str | None = None
    schedule_id: str | None = None
    schedule_mode: str = "manual"
    schedule_enabled: bool = False
    next_run_at: str | None = None
    last_run_at: str | None = None
    enabled: bool
    config_json: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class DiscoveryRunCreateRequest(BaseModel):
    """Start a manual discovery scan run for a target."""

    target_id: str = Field(min_length=1)

    @field_validator("target_id")
    @classmethod
    def _strip_target_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("target_id must not be blank.")
        return stripped


class DiscoveryRawFindingResponse(BaseModel):
    """Raw scanner finding persisted for later reconciliation."""

    id: str
    run_id: str
    fingerprint: str
    raw_payload_json: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class DiscoveryRunResponse(BaseModel):
    """Discovery scan run returned by the API."""

    id: str
    organization_id: str
    environment_id: str
    scanner_id: str
    scanner_type: str
    target_id: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None
    summary_json: dict[str, Any] = Field(default_factory=dict)
    raw_finding_count: int = 0
    raw_findings: list[DiscoveryRawFindingResponse] = Field(default_factory=list)
    created_at: str
    updated_at: str


class DiscoveryEvidenceResponse(BaseModel):
    """Evidence supporting a normalized discovery finding."""

    id: str
    finding_id: str
    run_id: str
    evidence_type: str
    evidence_value: str
    confidence: float
    created_at: str


class DiscoveryFindingResponse(BaseModel):
    """Normalized discovery finding returned by the API."""

    id: str
    organization_id: str
    environment_id: str
    fingerprint: str
    detected_name: str
    agent_type: str
    source: str | None = None
    owner_hint: str | None = None
    registry_agent_id: str | None = None
    status: str
    risk_score: float
    risk_level: str
    risk_factors: list[str] = Field(default_factory=list)
    first_seen_at: str
    last_seen_at: str
    evidence: list[DiscoveryEvidenceResponse] = Field(default_factory=list)


class DiscoveryAssignOwnerRequest(BaseModel):
    """Assign an owner hint to a discovery finding."""

    owner_user_id: str = Field(min_length=1)

    @field_validator("owner_user_id")
    @classmethod
    def _strip_owner(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("owner_user_id must not be blank.")
        return stripped


class DiscoverySuppressRequest(BaseModel):
    """Suppress a discovery finding with a required reason."""

    reason: str = Field(min_length=1)
    expires_at: str | None = None

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason must not be blank.")
        return stripped

    @field_validator("expires_at")
    @classmethod
    def _strip_expires_at(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class DiscoveryRegisterAgentRequest(BaseModel):
    """Create an agent registration draft from a discovery finding."""

    owner_user_id: str = Field(min_length=1)
    sponsor_user_id: str = Field(min_length=1)
    framework: str | None = None
    runtime_type: str = "discovered"

    @field_validator("owner_user_id", "sponsor_user_id", "runtime_type")
    @classmethod
    def _strip_required_registration_field(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be blank.")
        return stripped

    @field_validator("framework")
    @classmethod
    def _strip_framework(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
