"""Artifact API models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ArtifactCreateRequest(BaseModel):
    """Upload an artifact payload."""

    artifact_type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    content_type: str = "application/octet-stream"
    content_base64: str = Field(min_length=1)
    retention_policy: str = Field(default="standard", min_length=1)
    redaction_classification: str = Field(default="internal", min_length=1)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "artifact_type",
        "name",
        "content_type",
        "content_base64",
        "retention_policy",
        "redaction_classification",
    )
    @classmethod
    def _strip_string(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped


class ArtifactLinkCreateRequest(BaseModel):
    """Link an artifact to a product target."""

    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    link_type: str = Field(default="evidence", min_length=1)

    @field_validator("target_type", "target_id", "link_type")
    @classmethod
    def _strip_link_string(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped


class ArtifactLinkResponse(BaseModel):
    id: str
    artifact_id: str
    target_type: str
    target_id: str
    link_type: str
    created_at: str


class ArtifactAttestationCreateRequest(BaseModel):
    """Attest artifact integrity or review status."""

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


class ArtifactAttestationResponse(BaseModel):
    id: str
    artifact_id: str
    attested_by: str
    statement: str
    signature_ref: str | None = None
    artifact_checksum: str | None = None
    digest_algorithm: str = "sha256"
    signer_user_id: str | None = None
    created_at: str


class ArtifactResponse(BaseModel):
    id: str
    organization_id: str
    environment_id: str
    artifact_type: str
    name: str
    content_type: str
    storage_uri: str
    checksum: str
    digest_algorithm: str = "sha256"
    size_bytes: int
    retention_policy: str = "standard"
    redaction_classification: str = "internal"
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_by: str
    created_at: str
    links: list[ArtifactLinkResponse] = Field(default_factory=list)
    attestations: list[ArtifactAttestationResponse] = Field(default_factory=list)


class ArtifactDownloadResponse(BaseModel):
    artifact: ArtifactResponse
    content_base64: str
    metadata: dict[str, Any] = Field(default_factory=dict)
