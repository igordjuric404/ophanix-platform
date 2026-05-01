"""Compliance and audit export API models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


AUDIT_EXPORT_FORMATS = {"json", "csv", "markdown"}
COMPLIANCE_VIOLATION_STATUSES = {"open", "acknowledged", "resolved"}


class AuditExportRequest(BaseModel):
    """Request to persist an audit export job/metadata row."""

    filters: dict[str, Any] = Field(default_factory=dict)
    format: str = "json"

    @field_validator("format")
    @classmethod
    def _validate_format(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in AUDIT_EXPORT_FORMATS:
            raise ValueError(f"format must be one of: {', '.join(sorted(AUDIT_EXPORT_FORMATS))}.")
        return normalized


class AuditExportResponse(BaseModel):
    """Stored audit export metadata."""

    id: str
    organization_id: str
    filters: dict[str, Any] = Field(default_factory=dict)
    format: str
    status: str
    artifact_uri: str
    created_by: str
    created_at: str


class ComplianceFrameworkCreateRequest(BaseModel):
    """Create a compliance framework."""

    name: str = Field(min_length=1)
    version: str = Field(default="1.0", min_length=1)
    description: str = ""
    status: str = "active"


class ComplianceFrameworkResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    version: str
    description: str
    status: str
    created_at: str


class ComplianceControlResponse(BaseModel):
    id: str
    framework_id: str
    framework_name: str | None = None
    control_code: str
    title: str
    description: str
    required_evidence_types: list[str] = Field(default_factory=list)
    owner_user_id: str | None = None


class ControlMappingCreateRequest(BaseModel):
    control_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    source_component: str | None = None
    predicate: dict[str, Any] = Field(default_factory=dict)
    evidence_type: str = Field(default="audit_event", min_length=1)


class ControlMappingResponse(BaseModel):
    id: str
    control_id: str
    event_type: str
    source_component: str | None = None
    predicate: dict[str, Any] = Field(default_factory=dict)
    evidence_type: str


class EvidenceItemResponse(BaseModel):
    id: str
    organization_id: str
    environment_id: str
    control_id: str
    control_code: str | None = None
    source_type: str
    source_id: str
    title: str
    summary: str
    freshness_at: str
    status: str
    created_at: str


class EvidenceRecomputeResponse(BaseModel):
    scanned_event_count: int
    evidence_count: int
    refreshed_count: int


class ComplianceViolationPatchRequest(BaseModel):
    status: str = Field(min_length=1)
    reason: str | None = None

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"acknowledged", "resolved"}:
            raise ValueError("status must be acknowledged or resolved.")
        return normalized

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def _require_resolution_reason(self) -> "ComplianceViolationPatchRequest":
        if self.status == "resolved" and not self.reason:
            raise ValueError("reason is required when resolving a violation.")
        return self


class ComplianceViolationResponse(BaseModel):
    id: str
    organization_id: str
    environment_id: str
    control_id: str
    control_code: str | None = None
    agent_id: str | None = None
    severity: str
    status: str
    reason: str
    source_type: str
    source_id: str
    source_event_id: str | None = None
    acknowledged_by: str | None = None
    acknowledged_at: str | None = None
    resolved_by: str | None = None
    resolved_at: str | None = None
    resolution_reason: str | None = None
    created_at: str
    updated_at: str


class ComplianceReportCreateRequest(BaseModel):
    framework_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    date_from: str = Field(min_length=1)
    date_to: str = Field(min_length=1)

    @field_validator("framework_id", "name", "date_from", "date_to")
    @classmethod
    def _strip_report_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @model_validator(mode="after")
    def _validate_date_range(self) -> "ComplianceReportCreateRequest":
        if self.date_from > self.date_to:
            raise ValueError("date_from must be before or equal to date_to.")
        return self


class ComplianceReportResponse(BaseModel):
    id: str
    organization_id: str
    environment_id: str
    framework_id: str
    framework_name: str | None = None
    name: str
    status: str
    date_from: str
    date_to: str
    generated_by: str | None = None
    artifact_uri: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    generated_at: str | None = None
    evidence_item_ids: list[str] = Field(default_factory=list)
    attestation_count: int = 0
    rendered_markdown: str | None = None


class ComplianceReportAttestationRequest(BaseModel):
    statement: str = Field(min_length=1)
    signature_ref: str | None = None

    @field_validator("statement")
    @classmethod
    def _strip_statement(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("statement must not be blank.")
        return stripped

    @field_validator("signature_ref")
    @classmethod
    def _strip_signature_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ComplianceReportAttestationResponse(BaseModel):
    id: str
    report_id: str
    attested_by: str
    statement: str
    signature_ref: str | None = None
    created_at: str
