"""Trust threshold resolution and handshake evaluation helpers."""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from agentmesh.trust.handshake import (
    CANONICAL_HANDSHAKE_CONTRACT_VERSION,
    canonical_handshake_payload,
)
from cryptography.hazmat.primitives.asymmetric import ed25519
from product_platform.db.postgres import Row

from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.repository import AgentRegistryRepository
from product_platform.trust.cards import TrustCardRepository
from product_platform.trust.models import (
    TrustHandshakeChallengeRequest,
    TrustHandshakeChallengeResponse,
    TrustHandshakeRequest,
    TrustHandshakeResponse,
    TrustThresholdResolveRequest,
    TrustThresholdResolution,
)
from product_platform.trust.repository import (
    TrustRepository,
    calculate_trust_tier,
    trust_handshake_challenge_response,
    trust_handshake_response,
)


PROTECTED_THRESHOLD_TYPES = {
    "handoff",
    "mcp_tool_use",
    "privileged_runtime_action",
    "marketplace_install",
    "protocol_bridge_use",
}


class TrustThresholdResolver:
    """Resolve the most-specific enabled threshold for a protected action."""

    def __init__(self, repository: TrustRepository) -> None:
        self.repository = repository

    def resolve(self, body: TrustThresholdResolveRequest) -> TrustThresholdResolution:
        """Resolve exact target first, then environment default, then fail closed."""

        exact = self.repository.find_enabled_threshold(body)
        if exact is not None:
            return _threshold_resolution(exact, reason="target_threshold")

        fallback = None
        if body.target_type != "environment" or body.target_id is not None:
            fallback = self.repository.find_enabled_threshold(
                TrustThresholdResolveRequest(
                    threshold_type=body.threshold_type,
                    target_type="environment",
                    target_id=None,
                    protected=body.protected,
                )
            )
        if fallback is not None:
            return _threshold_resolution(fallback, reason="environment_default")

        if body.protected or body.threshold_type in PROTECTED_THRESHOLD_TYPES:
            return TrustThresholdResolution(
                threshold_id=None,
                threshold_type=body.threshold_type,
                target_type=body.target_type,
                target_id=body.target_id,
                min_score=1000,
                required_tier="verified_partner",
                resolved=False,
                fail_closed=True,
                reason="missing_required_threshold",
            )
        return TrustThresholdResolution(
            threshold_id=None,
            threshold_type=body.threshold_type,
            target_type=body.target_type,
            target_id=body.target_id,
            min_score=0,
            required_tier="untrusted",
            resolved=False,
            fail_closed=False,
            reason="threshold_not_configured",
    )


TRUST_TIER_RANK = {
    "untrusted": 0,
    "probationary": 1,
    "standard": 2,
    "trusted": 3,
    "verified_partner": 4,
}


@dataclass(frozen=True)
class TrustHandshakeProofResult:
    """Result of validating signed handshake proof."""

    valid: bool
    reason: str | None
    evidence: dict
    challenge_id: str | None = None
    consumed: bool = False


class TrustHandshakeService:
    """Evaluate and persist trust handshake outcomes."""

    def __init__(self, repository: TrustRepository) -> None:
        self.repository = repository

    def issue_challenge(
        self,
        body: TrustHandshakeChallengeRequest,
    ) -> TrustHandshakeChallengeResponse:
        """Issue a canonical challenge that must be signed before record."""

        source_agent = self.repository.require_operational_agent(body.source_agent_id)
        target_agent = self.repository.require_operational_agent(body.target_agent_id)
        source_identity = self._active_identity(body.source_agent_id)
        target_identity = self._active_identity(body.target_agent_id)
        if source_identity is None:
            raise ValueError("Source agent identity is required before issuing a challenge.")
        if target_identity is None:
            raise ValueError("Target agent identity is required before issuing a challenge.")

        issued_at = _utc_now()
        expires_at = issued_at + timedelta(seconds=body.expires_in_seconds)
        row = self.repository.create_handshake_challenge(
            source_agent_id=body.source_agent_id,
            source_did=source_identity["did"],
            target_agent_id=body.target_agent_id,
            target_did=target_identity["did"],
            purpose=body.purpose,
            threshold_type=body.threshold_type,
            target_type=body.target_type,
            target_id=body.target_id,
            audience=body.audience or self.repository.environment_id,
            nonce=secrets.token_urlsafe(32),
            contract_version=CANONICAL_HANDSHAKE_CONTRACT_VERSION,
            issued_at=issued_at.isoformat(),
            expires_at=expires_at.isoformat(),
            metadata={
                **body.metadata,
                "source_agent_status": source_agent["status"],
                "target_agent_status": target_agent["status"],
                "signature_algorithm": "ed25519",
            },
        )
        return trust_handshake_challenge_response(row)

    def evaluate_and_record(
        self,
        body: TrustHandshakeRequest,
        *,
        correlation_id: str | None,
        mode: str,
    ) -> TrustHandshakeResponse:
        """Evaluate a handshake request and persist the resulting event."""

        self.repository.seed_default_thresholds()
        source_agent = self.repository.require_operational_agent(body.source_agent_id)
        target_agent = self.repository.require_operational_agent(body.target_agent_id)
        resolution = TrustThresholdResolver(self.repository).resolve(
            TrustThresholdResolveRequest(
                threshold_type=body.threshold_type,
                target_type=body.target_type,
                target_id=body.target_id,
            )
        )
        source_score = self._score_for_agent(body.source_agent_id, source_agent)
        target_score = self._score_for_agent(body.target_agent_id, target_agent)
        result = "allowed"
        reason = "trust_threshold_satisfied"
        proof_result = self._verify_handshake_proof(body) if mode == "record" else None
        metadata = {
            **body.metadata,
            "mode": mode,
            "handshake_contract": {
                "contract_version": CANONICAL_HANDSHAKE_CONTRACT_VERSION,
                "proof_required": mode == "record",
                "dev_only": mode == "simulate",
                "proof": proof_result.evidence if proof_result is not None else None,
            },
            "threshold_resolution": resolution.model_dump(),
            "required_capabilities": body.required_capabilities,
        }

        failure_reason = proof_result.reason if proof_result and not proof_result.valid else None
        failure_reason = failure_reason or self._first_failure_reason(
            body,
            resolution=resolution,
            source_score=source_score,
            target_score=target_score,
        )
        if failure_reason is not None:
            result = "denied"
            reason = failure_reason

        row = self.repository.create_handshake_event(
            source_agent_id=body.source_agent_id,
            target_agent_id=body.target_agent_id,
            purpose=body.purpose,
            threshold_type=body.threshold_type,
            target_type=body.target_type,
            target_id=body.target_id,
            required_score=resolution.min_score,
            required_tier=resolution.required_tier,
            source_score=source_score,
            target_score=target_score,
            result=result,
            reason=reason,
            correlation_id=correlation_id,
            metadata=metadata,
        )
        if proof_result is not None and proof_result.consumed and proof_result.challenge_id:
            self.repository.attach_handshake_challenge_event(proof_result.challenge_id, row["id"])
        return trust_handshake_response(row)

    def _score_for_agent(self, agent_id: str, agent: Row) -> int:
        score = self.repository.get_score(agent_id)
        if score is not None:
            return int(score["score"])
        if agent["trust_score"] is not None:
            return int(agent["trust_score"])
        return 500

    def _first_failure_reason(
        self,
        body: TrustHandshakeRequest,
        *,
        resolution: TrustThresholdResolution,
        source_score: int,
        target_score: int,
    ) -> str | None:
        if resolution.fail_closed:
            return resolution.reason
        if not self._has_active_identity(body.source_agent_id):
            return "missing_identity"
        if not self._has_active_identity(body.target_agent_id):
            return "missing_identity"
        if body.require_trust_card:
            card_reason = self._trust_card_failure_reason(body.target_agent_id)
            if card_reason is not None:
                return card_reason
        if body.require_active_credential:
            credential_reason = self._credential_failure_reason(body.target_agent_id)
            if credential_reason is not None:
                return credential_reason
        missing = self._missing_capabilities(body.target_agent_id, body.required_capabilities)
        if missing:
            return "missing_capability"
        if self._below_threshold(source_score, resolution) or self._below_threshold(target_score, resolution):
            return "low_trust"
        return None

    def _has_active_identity(self, agent_id: str) -> bool:
        identity = AgentRegistryRepository(
            self.repository.connection,
            self.repository.organization_id,
            self.repository.environment_id,
        ).get_identity(agent_id)
        return identity is not None and identity["identity_status"] == "active"

    def _active_identity(self, agent_id: str) -> Row | None:
        identity = AgentRegistryRepository(
            self.repository.connection,
            self.repository.organization_id,
            self.repository.environment_id,
        ).get_identity(agent_id)
        if identity is None or identity["identity_status"] != "active":
            return None
        return identity

    def _verify_handshake_proof(self, body: TrustHandshakeRequest) -> TrustHandshakeProofResult:
        proof = body.proof
        if proof is None:
            return TrustHandshakeProofResult(
                valid=False,
                reason="missing_handshake_proof",
                evidence={"verified": False, "reason": "missing_handshake_proof"},
            )
        evidence = {
            "verified": False,
            "challenge_id": proof.challenge_id,
            "contract_version": proof.contract_version,
            "signature_algorithm": proof.signature_algorithm,
        }
        if proof.contract_version != CANONICAL_HANDSHAKE_CONTRACT_VERSION:
            return TrustHandshakeProofResult(
                valid=False,
                reason="unsupported_handshake_contract",
                evidence={**evidence, "reason": "unsupported_handshake_contract"},
                challenge_id=proof.challenge_id,
            )
        if proof.signature_algorithm != "ed25519":
            return TrustHandshakeProofResult(
                valid=False,
                reason="unsupported_signature_algorithm",
                evidence={**evidence, "reason": "unsupported_signature_algorithm"},
                challenge_id=proof.challenge_id,
            )
        challenge = self.repository.get_handshake_challenge(proof.challenge_id)
        if challenge is None:
            return TrustHandshakeProofResult(
                valid=False,
                reason="unknown_challenge",
                evidence={**evidence, "reason": "unknown_challenge"},
                challenge_id=proof.challenge_id,
            )
        evidence = {
            **evidence,
            "source_did": challenge["source_did"],
            "target_did": challenge["target_did"],
            "audience": challenge["audience"],
            "environment_id": challenge["environment_id"],
            "expires_at": challenge["expires_at"],
            "consumed_at": challenge["consumed_at"],
        }
        mismatch_reason = self._challenge_mismatch_reason(body, proof, challenge)
        if mismatch_reason is not None:
            return TrustHandshakeProofResult(
                valid=False,
                reason=mismatch_reason,
                evidence={**evidence, "reason": mismatch_reason},
                challenge_id=proof.challenge_id,
            )
        if challenge["consumed_at"] is not None:
            return TrustHandshakeProofResult(
                valid=False,
                reason="replayed_challenge",
                evidence={**evidence, "reason": "replayed_challenge"},
                challenge_id=proof.challenge_id,
            )
        if _parse_datetime(challenge["expires_at"]) <= _utc_now():
            return TrustHandshakeProofResult(
                valid=False,
                reason="expired_challenge",
                evidence={**evidence, "reason": "expired_challenge"},
                challenge_id=proof.challenge_id,
            )

        consumed = self.repository.consume_handshake_challenge(proof.challenge_id)
        if not consumed:
            return TrustHandshakeProofResult(
                valid=False,
                reason="replayed_challenge",
                evidence={**evidence, "reason": "replayed_challenge"},
                challenge_id=proof.challenge_id,
            )

        identity = self._active_identity(body.source_agent_id)
        if identity is None:
            return TrustHandshakeProofResult(
                valid=False,
                reason="missing_identity",
                evidence={**evidence, "reason": "missing_identity"},
                challenge_id=proof.challenge_id,
                consumed=True,
            )
        fingerprint = hashlib.sha256(proof.public_key.encode("utf-8")).hexdigest()
        if fingerprint != identity["public_key_fingerprint"]:
            return TrustHandshakeProofResult(
                valid=False,
                reason="public_key_mismatch",
                evidence={
                    **evidence,
                    "reason": "public_key_mismatch",
                    "public_key_fingerprint": fingerprint,
                    "expected_public_key_fingerprint": identity["public_key_fingerprint"],
                },
                challenge_id=proof.challenge_id,
                consumed=True,
            )
        payload = canonical_handshake_payload(
            contract_version=challenge["contract_version"],
            challenge_id=challenge["id"],
            nonce=challenge["nonce"],
            audience=challenge["audience"],
            organization_id=challenge["organization_id"],
            environment_id=challenge["environment_id"],
            source_agent_id=challenge["source_agent_id"],
            source_did=challenge["source_did"],
            target_agent_id=challenge["target_agent_id"],
            target_did=challenge["target_did"],
            purpose=challenge["purpose"],
            threshold_type=challenge["threshold_type"],
            target_type=challenge["target_type"],
            target_id=_public_challenge_target_id(challenge["target_id"]),
            expires_at=challenge["expires_at"],
        )
        if not _verify_ed25519_signature(proof.public_key, proof.signature, payload):
            return TrustHandshakeProofResult(
                valid=False,
                reason="invalid_signature",
                evidence={**evidence, "reason": "invalid_signature"},
                challenge_id=proof.challenge_id,
                consumed=True,
            )
        return TrustHandshakeProofResult(
            valid=True,
            reason=None,
            evidence={
                **evidence,
                "verified": True,
                "reason": None,
                "signed_payload_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                "public_key_fingerprint": fingerprint,
            },
            challenge_id=proof.challenge_id,
            consumed=True,
        )

    def _challenge_mismatch_reason(
        self,
        body: TrustHandshakeRequest,
        proof,
        challenge: Row,
    ) -> str | None:
        if challenge["source_agent_id"] != body.source_agent_id:
            return "wrong_source_agent"
        if challenge["target_agent_id"] != body.target_agent_id:
            return "wrong_target_agent"
        if challenge["purpose"] != body.purpose:
            return "wrong_purpose"
        if challenge["threshold_type"] != body.threshold_type:
            return "wrong_threshold_type"
        if challenge["target_type"] != body.target_type:
            return "wrong_target_type"
        if _public_challenge_target_id(challenge["target_id"]) != body.target_id:
            return "wrong_target_id"
        if challenge["nonce"] != proof.nonce:
            return "wrong_nonce"
        if challenge["audience"] != proof.audience:
            return "wrong_audience"
        if challenge["environment_id"] != proof.environment_id:
            return "wrong_environment"
        if challenge["environment_id"] != self.repository.environment_id:
            return "wrong_environment"
        if challenge["expires_at"] != proof.expires_at:
            return "wrong_expiry"
        return None

    def _trust_card_failure_reason(self, agent_id: str) -> str | None:
        cards = TrustCardRepository(
            self.repository.connection,
            self.repository.organization_id,
            self.repository.environment_id,
        )
        if cards.current_card(agent_id) is not None:
            return None
        latest = cards.list_cards(agent_id=agent_id)
        if latest and latest[0]["status"] == "revoked":
            return "revoked_trust_card"
        return "missing_trust_card"

    def _credential_failure_reason(self, agent_id: str) -> str | None:
        credentials = AgentCredentialRepository(
            self.repository.connection,
            self.repository.organization_id,
            self.repository.environment_id,
        ).list_for_agent(agent_id)
        if not credentials:
            return "missing_credential"
        active = [
            row
            for row in credentials
            if row["status"] in {"active", "expiring_soon"} and row["expires_at"] > _utc_now_for_compare()
        ]
        if active:
            return None
        return "expired_credential"

    def _missing_capabilities(self, agent_id: str, required_capabilities: list[str]) -> list[str]:
        if not required_capabilities:
            return []
        approved = {
            row["capability_name"]
            for row in AgentRegistryRepository(
                self.repository.connection,
                self.repository.organization_id,
                self.repository.environment_id,
            ).list_capabilities(agent_id)
            if row["status"] == "approved"
        }
        return sorted(set(required_capabilities) - approved)

    def _below_threshold(self, score: int, resolution: TrustThresholdResolution) -> bool:
        score_tier = calculate_trust_tier(score)
        return score < resolution.min_score or TRUST_TIER_RANK[score_tier] < TRUST_TIER_RANK[resolution.required_tier]


def _utc_now_for_compare() -> str:
    from product_platform.db.time import utc_now_iso

    return utc_now_iso()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _verify_ed25519_signature(public_key: str, signature: str, payload: str) -> bool:
    try:
        key = ed25519.Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key))
        key.verify(base64.b64decode(signature), payload.encode("utf-8"))
        return True
    except Exception:
        return False


def _public_challenge_target_id(value: str | None) -> str | None:
    return value or None


def _threshold_resolution(row: Row, *, reason: str) -> TrustThresholdResolution:
    target_id = row["target_id"] or None
    return TrustThresholdResolution(
        threshold_id=row["id"],
        threshold_type=row["threshold_type"],
        target_type=row["target_type"],
        target_id=target_id,
        min_score=int(row["min_score"]),
        required_tier=row["required_tier"],
        resolved=True,
        fail_closed=False,
        reason=reason,
    )
