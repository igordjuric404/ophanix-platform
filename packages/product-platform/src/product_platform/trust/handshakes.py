"""Trust threshold resolution and handshake evaluation helpers."""

from __future__ import annotations

from product_platform.db.postgres import Row

from product_platform.agents.credentials import AgentCredentialRepository
from product_platform.agents.repository import AgentRegistryRepository
from product_platform.trust.cards import TrustCardRepository
from product_platform.trust.models import (
    TrustHandshakeRequest,
    TrustHandshakeResponse,
    TrustThresholdResolveRequest,
    TrustThresholdResolution,
)
from product_platform.trust.repository import (
    TrustRepository,
    calculate_trust_tier,
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


class TrustHandshakeService:
    """Evaluate and persist trust handshake outcomes."""

    def __init__(self, repository: TrustRepository) -> None:
        self.repository = repository

    def evaluate_and_record(
        self,
        body: TrustHandshakeRequest,
        *,
        correlation_id: str | None,
        mode: str,
    ) -> TrustHandshakeResponse:
        """Evaluate a handshake request and persist the resulting event."""

        self.repository.seed_default_thresholds()
        source_agent = self.repository._require_agent(body.source_agent_id)
        target_agent = self.repository._require_agent(body.target_agent_id)
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
        metadata = {
            **body.metadata,
            "mode": mode,
            "threshold_resolution": resolution.model_dump(),
            "required_capabilities": body.required_capabilities,
        }

        failure_reason = self._first_failure_reason(
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
