"""Agent registry API models."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

CAPABILITY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*:[a-z][a-z0-9_.-]*(?::[a-z0-9_.-]+)?$")
SUPPORTED_CREDENTIAL_SCOPE_RESOURCE_TYPES = {"agent", "claim", "tool"}


class AgentRegistrationDraftCreate(BaseModel):
    """Create an agent registration draft."""

    name: str = Field(min_length=1)
    owner_user_id: str = Field(min_length=1)
    sponsor_user_id: str = Field(min_length=1)
    framework: str = Field(min_length=1)
    runtime_type: str = Field(min_length=1)
    description: str = ""
    endpoint_url: str | None = None

    @field_validator("name", "owner_user_id", "sponsor_user_id", "framework", "runtime_type")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be blank.")
        return stripped

    @field_validator("description")
    @classmethod
    def _strip_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("endpoint_url")
    @classmethod
    def _strip_endpoint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class AgentRegistrationDraftPatch(BaseModel):
    """Patch an agent registration draft."""

    name: str | None = Field(default=None, min_length=1)
    owner_user_id: str | None = Field(default=None, min_length=1)
    sponsor_user_id: str | None = Field(default=None, min_length=1)
    framework: str | None = Field(default=None, min_length=1)
    runtime_type: str | None = Field(default=None, min_length=1)
    description: str | None = None
    endpoint_url: str | None = None
    capabilities: list["AgentCapabilityRequest"] | None = None
    policy_selections: list["AgentPolicySelectionRequest"] | None = None

    @field_validator("name", "owner_user_id", "sponsor_user_id", "framework", "runtime_type")
    @classmethod
    def _strip_optional_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be blank.")
        return stripped

    @field_validator("description")
    @classmethod
    def _strip_optional_description(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()

    @field_validator("endpoint_url")
    @classmethod
    def _strip_optional_endpoint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class AgentRegistrationDraftResponse(BaseModel):
    """Registration draft returned by the API."""

    id: str
    organization_id: str
    environment_id: str
    name: str
    description: str
    framework: str
    runtime_type: str
    endpoint_url: str | None = None
    owner_user_id: str
    sponsor_user_id: str
    status: str
    created_at: str
    updated_at: str
    capabilities: list["AgentCapabilityResponse"] = Field(default_factory=list)
    policy_selections: list["AgentPolicySelectionResponse"] = Field(default_factory=list)


class AgentIdentityResponse(BaseModel):
    """Persisted public identity metadata for a registered agent."""

    id: str
    agent_id: str
    did: str
    public_key_fingerprint: str
    key_type: str
    identity_status: str
    created_at: str


class AgentBootstrapMaterial(BaseModel):
    """One-time bootstrap material returned immediately after local key creation."""

    did: str
    public_key: str
    verification_key_id: str
    private_key_pem: str


class AgentIdentityCreateResponse(BaseModel):
    """Identity creation response with optional one-time bootstrap material."""

    identity: AgentIdentityResponse
    bootstrap: AgentBootstrapMaterial | None = None


class AgentCapabilityRequest(BaseModel):
    """Capability requested for a draft agent."""

    capability_name: str = Field(min_length=1)
    resource_type: str = Field(default="agent", min_length=1)

    @field_validator("capability_name")
    @classmethod
    def _validate_capability_name(cls, value: str) -> str:
        stripped = value.strip().lower()
        if not CAPABILITY_PATTERN.match(stripped):
            raise ValueError("Capability must use namespace:action format.")
        return stripped

    @field_validator("resource_type")
    @classmethod
    def _strip_resource_type(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("resource_type must not be blank.")
        return stripped


class AgentCapabilityResponse(BaseModel):
    """Persisted agent capability request."""

    id: str
    agent_id: str
    capability_name: str
    resource_type: str
    status: str
    requested_by: str
    approved_by: str | None = None
    created_at: str


class AgentPolicySelectionRequest(BaseModel):
    """Policy pack or binding selected during registration."""

    policy_id: str = Field(min_length=1)
    selection_type: str = Field(default="policy_binding", min_length=1)

    @field_validator("policy_id", "selection_type")
    @classmethod
    def _strip_policy_fields(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Policy selection fields must not be blank.")
        return stripped


class AgentPolicySelectionResponse(BaseModel):
    """Persisted policy selection for a draft agent."""

    id: str
    agent_id: str
    policy_id: str
    selection_type: str
    status: str
    created_at: str


class AgentRegistrationSimulationResponse(BaseModel):
    """Result of simulating the first requested registration action."""

    agent_id: str
    decision: str
    action: str | None = None
    matched_policy_ids: list[str] = Field(default_factory=list)
    reason: str


class AgentLifecycleActionRequest(BaseModel):
    """Optional lifecycle action metadata."""

    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class AgentInventorySummary(BaseModel):
    """Agent row returned by the inventory table API."""

    id: str
    organization_id: str
    environment_id: str
    name: str
    description: str
    framework: str
    runtime_type: str
    endpoint_url: str | None = None
    owner_user_id: str
    sponsor_user_id: str
    status: str
    trust_score: float | None = None
    trust_tier: str | None = None
    credential_status: str | None = None
    credential_expires_at: str | None = None
    last_heartbeat_at: str | None = None
    did: str | None = None
    capability_count: int = 0
    protocol_count: int = 0
    created_at: str
    updated_at: str


class AgentProtocolResponse(BaseModel):
    """Protocol endpoint configured for an agent."""

    id: str
    agent_id: str
    protocol: str
    endpoint: str
    status: str


class AgentHeartbeatResponse(BaseModel):
    """Latest observed agent heartbeat."""

    id: str
    agent_id: str
    observed_at: str
    status: str
    metadata_json: dict = Field(default_factory=dict)


class AgentDetailResponse(BaseModel):
    """Aggregate agent detail response."""

    summary: AgentInventorySummary
    identity: AgentIdentityResponse | None = None
    capabilities: list[AgentCapabilityResponse] = Field(default_factory=list)
    protocols: list[AgentProtocolResponse] = Field(default_factory=list)
    policy_selections: list[AgentPolicySelectionResponse] = Field(default_factory=list)
    latest_heartbeat: AgentHeartbeatResponse | None = None
    lifecycle_summary: dict = Field(default_factory=dict)


class AgentTimelineEvent(BaseModel):
    """Combined lifecycle/audit timeline event."""

    id: str
    source: str
    event_type: str
    created_at: str
    previous_state: str | None = None
    next_state: str | None = None
    actor_id: str | None = None
    payload_json: dict = Field(default_factory=dict)


class AgentPatchRequest(BaseModel):
    """Patch editable agent detail fields."""

    description: str | None = None
    owner_user_id: str | None = Field(default=None, min_length=1)
    sponsor_user_id: str | None = Field(default=None, min_length=1)

    @field_validator("description")
    @classmethod
    def _strip_patch_description(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()

    @field_validator("owner_user_id", "sponsor_user_id")
    @classmethod
    def _strip_patch_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("User id must not be blank.")
        return stripped


class AgentOwnerChangeRequest(BaseModel):
    """Owner transfer request."""

    new_owner_user_id: str = Field(min_length=1)
    reason: str | None = None

    @field_validator("new_owner_user_id")
    @classmethod
    def _strip_new_owner(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("new_owner_user_id must not be blank.")
        return stripped


class AgentHeartbeatRequest(BaseModel):
    """Agent heartbeat payload."""

    status: str = Field(default="healthy", min_length=1)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class OrphanDetectionRunRequest(BaseModel):
    """Manual orphan detection request."""

    threshold_hours: int = Field(default=24, ge=1)


class OrphanDetectionRunResponse(BaseModel):
    """Manual orphan detection result."""

    processed_count: int
    orphaned_agent_ids: list[str] = Field(default_factory=list)


class CredentialScopeRequest(BaseModel):
    """Scope attached to an agent credential."""

    scope: str = Field(min_length=1)
    resource_type: str = Field(default="agent", min_length=1)
    resource_id: str | None = None

    @field_validator("scope", "resource_type")
    @classmethod
    def _strip_required_scope_fields(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Credential scope fields must not be blank.")
        return stripped

    @field_validator("resource_type")
    @classmethod
    def _validate_resource_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_CREDENTIAL_SCOPE_RESOURCE_TYPES:
            supported = ", ".join(sorted(SUPPORTED_CREDENTIAL_SCOPE_RESOURCE_TYPES))
            raise ValueError(f"resource_type must be one of: {supported}.")
        return normalized

    @field_validator("resource_id")
    @classmethod
    def _strip_resource_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class CredentialScopeResponse(BaseModel):
    """Persisted credential scope."""

    id: str
    credential_id: str
    scope: str
    resource_type: str
    resource_id: str | None = None


class AgentCredentialResponse(BaseModel):
    """Credential metadata returned by the product API without secret material."""

    id: str
    agent_id: str
    credential_type: str
    issuer: str
    status: str
    issued_at: str
    expires_at: str
    revoked_at: str | None = None
    last_used_at: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    scopes: list[CredentialScopeResponse] = Field(default_factory=list)


class AgentCredentialIssueRequest(BaseModel):
    """Request to issue a new credential for an agent."""

    credential_type: str = Field(default="bearer", min_length=1)
    issuer: str = Field(default="local-agentmesh", min_length=1)
    ttl_seconds: int = Field(default=900, ge=60, le=86_400)
    issued_for: str | None = None
    scopes: list[CredentialScopeRequest] = Field(default_factory=list)

    @field_validator("credential_type", "issuer")
    @classmethod
    def _strip_issue_fields(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Credential issue fields must not be blank.")
        return stripped

    @field_validator("issued_for")
    @classmethod
    def _strip_issued_for(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class AgentCredentialIssueResponse(BaseModel):
    """Credential issue response with one-time token material."""

    credential: AgentCredentialResponse
    token: str
    bearer_token: str


class CredentialActionRequest(BaseModel):
    """Reasoned credential lifecycle action request."""

    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class AgentCredentialRotationResponse(BaseModel):
    """Credential rotation response with one-time replacement token material."""

    rotation_id: str
    previous_credential: AgentCredentialResponse
    credential: AgentCredentialResponse
    token: str
    bearer_token: str


class CredentialVerifyRequest(BaseModel):
    """Credential token verification request."""

    token: str = Field(min_length=1)

    @field_validator("token")
    @classmethod
    def _strip_token(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Token must not be blank.")
        return stripped


class CredentialVerifyResponse(BaseModel):
    """Credential token verification result without exposing stored hashes."""

    credential_id: str
    agent_id: str
    valid: bool
    status: str
    reason: str
    verified_at: str
