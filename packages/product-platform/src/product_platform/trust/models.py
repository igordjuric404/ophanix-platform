"""Trust score API and repository models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from product_platform.trust.schema import (
    TRUST_SCORE_DIMENSIONS,
    TRUST_SCORE_SCHEMA_VERSION,
    TRUST_SCORE_TIER_THRESHOLDS,
)

TRUST_DIMENSIONS = set(TRUST_SCORE_DIMENSIONS)
TRUST_TIERS = {name for name, _min_score in TRUST_SCORE_TIER_THRESHOLDS}


class TrustScoreResponse(BaseModel):
    """Current trust score for one agent."""

    schema_version: str = TRUST_SCORE_SCHEMA_VERSION
    id: str
    organization_id: str
    environment_id: str
    agent_id: str
    score: int
    tier: str
    dimensions: dict[str, Any] = Field(default_factory=dict)
    calculated_at: str
    created_at: str
    updated_at: str
    agent_name: str | None = None
    explanation: dict[str, Any] = Field(default_factory=dict)


class TrustEventResponse(BaseModel):
    """Explainable trust delta linked to a source event."""

    id: str
    organization_id: str
    environment_id: str
    agent_id: str
    source_event_id: str | None = None
    dimension: str
    delta: int
    reason: str
    score_before: int
    score_after: int
    created_at: str
    agent_name: str | None = None


class TrustRulePatchRequest(BaseModel):
    """Patch mutable trust rule controls."""

    delta: int | None = None
    min_delta: int | None = None
    max_delta: int | None = None
    enabled: bool | None = None
    config: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_bounds(self) -> "TrustRulePatchRequest":
        if self.min_delta is not None and self.max_delta is not None and self.min_delta > self.max_delta:
            raise ValueError("min_delta must be less than or equal to max_delta.")
        if self.delta is not None:
            if self.min_delta is not None and self.delta < self.min_delta:
                raise ValueError("delta must be greater than or equal to min_delta.")
            if self.max_delta is not None and self.delta > self.max_delta:
                raise ValueError("delta must be less than or equal to max_delta.")
        return self


class TrustRuleResponse(BaseModel):
    """Trust rule used to map audit events into trust deltas."""

    id: str
    organization_id: str
    event_type: str
    dimension: str
    delta: int
    min_delta: int
    max_delta: int
    enabled: bool
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class TrustThresholdCreateRequest(BaseModel):
    """Create a trust threshold for a protected action."""

    threshold_type: str = Field(min_length=1)
    target_type: str = Field(default="environment", min_length=1)
    target_id: str | None = None
    min_score: int = Field(ge=0, le=1000)
    required_tier: str = "standard"
    enabled: bool = True

    @field_validator("threshold_type", "target_type", "required_tier")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("target_id")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def _validate_tier(self) -> "TrustThresholdCreateRequest":
        if self.required_tier not in TRUST_TIERS:
            raise ValueError("required_tier must be a valid trust tier.")
        return self


class TrustThresholdPatchRequest(BaseModel):
    """Patch mutable trust threshold fields."""

    threshold_type: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    min_score: int | None = Field(default=None, ge=0, le=1000)
    required_tier: str | None = None
    enabled: bool | None = None

    @field_validator("threshold_type", "target_type", "required_tier")
    @classmethod
    def _strip_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("target_id")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def _validate_tier(self) -> "TrustThresholdPatchRequest":
        if self.required_tier is not None and self.required_tier not in TRUST_TIERS:
            raise ValueError("required_tier must be a valid trust tier.")
        return self


class TrustThresholdResponse(BaseModel):
    """Persisted trust threshold configuration."""

    id: str
    organization_id: str
    environment_id: str
    threshold_type: str
    target_type: str
    target_id: str | None = None
    min_score: int
    required_tier: str
    enabled: bool
    created_at: str
    updated_at: str


class TrustThresholdResolveRequest(BaseModel):
    """Resolve the threshold that applies to a protected trust action."""

    threshold_type: str = Field(min_length=1)
    target_type: str = Field(default="environment", min_length=1)
    target_id: str | None = None
    protected: bool = True

    @field_validator("threshold_type", "target_type")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("target_id")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TrustThresholdResolution(BaseModel):
    """Result of threshold resolution for a protected action."""

    threshold_id: str | None = None
    threshold_type: str
    target_type: str
    target_id: str | None = None
    min_score: int
    required_tier: str
    resolved: bool
    fail_closed: bool = False
    reason: str


class TrustHandshakeChallengeRequest(BaseModel):
    """Request a server-issued handshake challenge."""

    source_agent_id: str = Field(min_length=1)
    target_agent_id: str = Field(min_length=1)
    purpose: str = Field(default="handoff", min_length=1)
    threshold_type: str = Field(default="handoff", min_length=1)
    target_type: str = Field(default="environment", min_length=1)
    target_id: str | None = None
    audience: str | None = None
    expires_in_seconds: int = Field(default=30, ge=5, le=300)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "source_agent_id",
        "target_agent_id",
        "purpose",
        "threshold_type",
        "target_type",
        "audience",
    )
    @classmethod
    def _strip_required_or_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("target_id")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TrustHandshakeChallengeResponse(BaseModel):
    """Server-issued canonical handshake challenge."""

    challenge_id: str
    organization_id: str
    environment_id: str
    source_agent_id: str
    source_did: str
    target_agent_id: str
    target_did: str
    purpose: str
    threshold_type: str
    target_type: str
    target_id: str | None = None
    audience: str
    nonce: str
    contract_version: str
    signature_algorithm: str = "ed25519"
    canonical_payload: str
    issued_at: str
    expires_at: str
    consumed_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrustHandshakeProof(BaseModel):
    """Signed response to a server-issued handshake challenge."""

    challenge_id: str = Field(min_length=1)
    nonce: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    environment_id: str = Field(min_length=1)
    expires_at: str = Field(min_length=1)
    signature: str = Field(min_length=1)
    public_key: str = Field(min_length=1)
    contract_version: str = "agentmesh.handshake.v1"
    signature_algorithm: str = "ed25519"

    @field_validator(
        "challenge_id",
        "nonce",
        "audience",
        "environment_id",
        "expires_at",
        "signature",
        "public_key",
        "contract_version",
        "signature_algorithm",
    )
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped


class TrustHandshakeRequest(BaseModel):
    """Request to simulate or record a trust handshake."""

    source_agent_id: str = Field(min_length=1)
    target_agent_id: str = Field(min_length=1)
    purpose: str = Field(default="handoff", min_length=1)
    threshold_type: str = Field(default="handoff", min_length=1)
    target_type: str = Field(default="environment", min_length=1)
    target_id: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    require_trust_card: bool = False
    require_active_credential: bool = False
    proof: TrustHandshakeProof | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "source_agent_id",
        "target_agent_id",
        "purpose",
        "threshold_type",
        "target_type",
    )
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("target_id")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("required_capabilities")
    @classmethod
    def _strip_capabilities(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class TrustHandshakeResponse(BaseModel):
    """Persisted trust handshake outcome."""

    id: str
    organization_id: str
    environment_id: str
    source_agent_id: str
    target_agent_id: str
    purpose: str
    threshold_type: str
    target_type: str
    target_id: str | None = None
    required_score: int
    required_tier: str
    source_score: int
    target_score: int
    result: str
    reason: str
    correlation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class TrustRecalculateRequest(BaseModel):
    """Request a trust score recalculation."""

    agent_id: str | None = None

    @field_validator("agent_id")
    @classmethod
    def _strip_agent_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TrustRecalculationRunResponse(BaseModel):
    """Trust recalculation run metadata."""

    id: str
    organization_id: str
    environment_id: str
    status: str
    started_at: str
    finished_at: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


class TrustCardIssueRequest(BaseModel):
    """Issue a trust card for an agent."""

    agent_id: str = Field(min_length=1)
    issuer: str = "ophanix-demo-issuer"
    valid_days: int = Field(default=30, ge=1, le=365)

    @field_validator("agent_id", "issuer")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped


class TrustCardResponse(BaseModel):
    """Persisted signed trust card."""

    id: str
    organization_id: str
    environment_id: str
    agent_id: str
    issuer: str
    card: dict[str, Any]
    signature: str
    status: str
    valid_from: str
    valid_until: str
    issued_at: str
    revoked_at: str | None = None
    revocation_reason: str | None = None


class TrustCardVerifyResponse(BaseModel):
    """Trust card verification result."""

    trust_card_id: str
    agent_id: str
    status: str
    verified: bool
    reason: str
    checked_at: str


class AgentTrustCardResponse(BaseModel):
    """Current trust card state for an agent."""

    agent_id: str
    card: TrustCardResponse | None = None
    warning: str | None = None


class TrustCardRevokeRequest(BaseModel):
    """Revoke a trust card with a human-readable reason."""

    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason must not be blank.")
        return stripped
