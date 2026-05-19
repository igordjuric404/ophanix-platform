"""Trust card issuance and persistence."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from product_platform.db.postgres import Connection, Row
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from agentmesh.identity.agent_id import AgentDID, AgentIdentity
from agentmesh.trust.cards import CardRegistry, TrustedAgentCard

from product_platform.agents.lifecycle import (
    agent_non_operational_message,
    agent_non_operational_reason_code,
    is_agent_operational,
)
from product_platform.agents.repository import AgentRegistryRepository, AgentNotFoundError
from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.trust.models import (
    TrustCardIssueRequest,
    TrustCardResponse,
    TrustCardVerifyResponse,
)
from product_platform.trust.repository import TrustRepository


class TrustCardNotFoundError(ValueError):
    """Raised when a trust card is not visible in tenant scope."""


class TrustCardAgentNotOperationalError(ValueError):
    """Raised when trust-card operations target a non-operational agent."""

    def __init__(self, agent_id: str, status: str) -> None:
        self.agent_id = agent_id
        self.status = status
        self.reason_code = agent_non_operational_reason_code(status)
        super().__init__(agent_non_operational_message(status))


class TrustCardIssuer:
    """Issue signed cards from product agent state."""

    def __init__(
        self,
        connection: Connection,
        organization_id: str,
        environment_id: str,
        *,
        signing_key_provider: "DemoTrustCardSigningKeyProvider | None" = None,
    ) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id
        self.signing_key_provider = signing_key_provider or DemoTrustCardSigningKeyProvider()

    def issue(self, body: TrustCardIssueRequest) -> Row:
        """Build, sign, and persist a trust card."""

        agent_repository = AgentRegistryRepository(
            self.connection,
            self.organization_id,
            self.environment_id,
        )
        agent = agent_repository.get(body.agent_id)
        if agent is None:
            raise AgentNotFoundError("Agent not found.")
        if not is_agent_operational(agent["status"]):
            raise TrustCardAgentNotOperationalError(body.agent_id, agent["status"])
        identity = agent_repository.get_identity(body.agent_id)
        if identity is None:
            raise AgentNotFoundError("Agent identity not found.")
        capabilities = [
            row["capability_name"]
            for row in agent_repository.list_capabilities(body.agent_id)
            if row["status"] == "approved"
        ]
        trust_score = TrustRepository(
            self.connection,
            self.organization_id,
            self.environment_id,
        ).get_score(body.agent_id)
        score_points = int(trust_score["score"]) if trust_score is not None else 500
        tier = trust_score["tier"] if trust_score is not None else "standard"
        card = TrustedAgentCard(
            name=agent["name"],
            description=agent["description"],
            capabilities=capabilities,
            agent_did=identity["did"],
            trust_score=score_points / 1000,
            metadata={
                "agent_id": body.agent_id,
                "issuer": body.issuer,
                "trust_score": score_points,
                "trust_tier": tier,
                "identity_fingerprint": identity["public_key_fingerprint"],
                "capability_count": len(capabilities),
            },
        )
        signer = self.signing_key_provider.identity_for_card(
            agent_did=identity["did"],
            name=agent["name"],
            description=agent["description"],
            capabilities=capabilities,
            issuer=body.issuer,
        )
        card.sign(signer)
        valid_from = utc_now_iso()
        valid_until = (
            datetime.now(timezone.utc) + timedelta(days=body.valid_days)
        ).isoformat()
        return TrustCardRepository(
            self.connection,
            self.organization_id,
            self.environment_id,
        ).create_card(
            agent_id=body.agent_id,
            issuer=body.issuer,
            card=card.to_dict(),
            signature=card.card_signature or "",
            valid_from=valid_from,
            valid_until=valid_until,
        )


class DemoTrustCardSigningKeyProvider:
    """Ephemeral demo signing key provider for local trust cards."""

    def __init__(self) -> None:
        self._private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = self._private_key.public_key()
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.public_key = base64.b64encode(public_key_bytes).decode("ascii")
        self.verification_key_id = f"demo-{hashlib.sha256(public_key_bytes).hexdigest()[:16]}"

    def identity_for_card(
        self,
        *,
        agent_did: str,
        name: str,
        description: str,
        capabilities: list[str],
        issuer: str,
    ) -> AgentIdentity:
        """Create an AgentMesh identity wrapper preserving the product agent DID."""

        identity = AgentIdentity(
            did=AgentDID.from_string(agent_did),
            name=name,
            description=description,
            public_key=self.public_key,
            verification_key_id=self.verification_key_id,
            sponsor_email=f"{issuer}@ophanix.local",
            sponsor_verified=True,
            organization=issuer,
            capabilities=capabilities,
        )
        identity._private_key = self._private_key
        return identity


class TrustCardRepository:
    """Environment-scoped trust card repository."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create_card(
        self,
        *,
        agent_id: str,
        issuer: str,
        card: dict[str, Any],
        signature: str,
        valid_from: str,
        valid_until: str,
    ) -> Row:
        card_id = generate_id("tcard")
        issued_at = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO trust_cards (
                id, organization_id, environment_id, agent_id, issuer, card_json,
                signature, status, valid_from, valid_until, issued_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card_id,
                self.organization_id,
                self.environment_id,
                agent_id,
                issuer,
                json.dumps(card, sort_keys=True),
                signature,
                "active",
                valid_from,
                valid_until,
                issued_at,
            ),
        )
        row = self.get_card(card_id)
        if row is None:
            raise TrustCardNotFoundError("Created trust card could not be loaded.")
        return row

    def list_cards(self, *, agent_id: str | None = None) -> list[Row]:
        clauses = ["c.organization_id = ?", "c.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if agent_id is not None:
            clauses.append("c.agent_id = ?")
            values.append(agent_id)
        return self.connection.execute(
            f"""
            SELECT c.*, r.revoked_at, r.reason AS revocation_reason
            FROM trust_cards c
            LEFT JOIN trust_card_revocations r ON r.trust_card_id = c.id
            WHERE {' AND '.join(clauses)}
            ORDER BY c.issued_at DESC, c.id DESC
            """,
            values,
        ).fetchall()

    def get_card(self, card_id: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT c.*, r.revoked_at, r.reason AS revocation_reason
            FROM trust_cards c
            LEFT JOIN trust_card_revocations r ON r.trust_card_id = c.id
            WHERE c.id = ?
              AND c.organization_id = ?
              AND c.environment_id = ?
            """,
            (card_id, self.organization_id, self.environment_id),
        ).fetchone()

    def current_card(self, agent_id: str, *, now: str | None = None) -> Row | None:
        if not self._agent_is_operational(agent_id):
            return None
        timestamp = now or utc_now_iso()
        return self.connection.execute(
            """
            SELECT c.*, r.revoked_at, r.reason AS revocation_reason
            FROM trust_cards c
            LEFT JOIN trust_card_revocations r ON r.trust_card_id = c.id
            WHERE c.organization_id = ?
              AND c.environment_id = ?
              AND c.agent_id = ?
              AND c.status = 'active'
              AND c.valid_from <= ?
              AND c.valid_until > ?
              AND r.id IS NULL
            ORDER BY c.issued_at DESC, c.id DESC
            LIMIT 1
            """,
            (
                self.organization_id,
                self.environment_id,
                agent_id,
                timestamp,
                timestamp,
            ),
        ).fetchone()

    def revoke_card(self, card_id: str, *, reason: str, revoked_by: str) -> Row:
        row = self.get_card(card_id)
        if row is None:
            raise TrustCardNotFoundError("Trust card not found.")
        if row["status"] != "revoked":
            self.connection.execute(
                """
                INSERT INTO trust_card_revocations (
                    id, trust_card_id, reason, revoked_by, revoked_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (generate_id("tcrev"), card_id, reason, revoked_by, utc_now_iso()),
            )
            self.connection.execute(
                """
                UPDATE trust_cards
                SET status = ?
                WHERE id = ? AND organization_id = ? AND environment_id = ?
                """,
                ("revoked", card_id, self.organization_id, self.environment_id),
            )
        updated = self.get_card(card_id)
        if updated is None:
            raise TrustCardNotFoundError("Trust card not found.")
        return updated

    def invalidate_agent_cards(self, agent_id: str, *, reason: str, revoked_by: str) -> list[Row]:
        """Revoke active trust cards for an agent after restrictive lifecycle transitions."""

        rows = self.connection.execute(
            """
            SELECT c.*
            FROM trust_cards c
            JOIN agents a ON a.id = c.agent_id
            WHERE c.organization_id = ?
              AND c.environment_id = ?
              AND c.agent_id = ?
              AND c.status = 'active'
              AND a.deleted_at IS NULL
            ORDER BY c.issued_at ASC, c.id ASC
            """,
            (self.organization_id, self.environment_id, agent_id),
        ).fetchall()
        return [
            self.revoke_card(row["id"], reason=reason, revoked_by=revoked_by)
            for row in rows
        ]

    def verify_card(self, card_id: str) -> TrustCardVerifyResponse:
        row = self.get_card(card_id)
        if row is None:
            raise TrustCardNotFoundError("Trust card not found.")
        if row["status"] == "revoked":
            return TrustCardVerifyResponse(
                trust_card_id=row["id"],
                agent_id=row["agent_id"],
                status=row["status"],
                verified=False,
                reason="revoked",
                checked_at=utc_now_iso(),
            )
        agent = self._agent_row(row["agent_id"])
        if agent is None:
            return TrustCardVerifyResponse(
                trust_card_id=row["id"],
                agent_id=row["agent_id"],
                status=row["status"],
                verified=False,
                reason="agent_not_found",
                checked_at=utc_now_iso(),
            )
        if not is_agent_operational(agent["status"]):
            return TrustCardVerifyResponse(
                trust_card_id=row["id"],
                agent_id=row["agent_id"],
                status=row["status"],
                verified=False,
                reason=agent_non_operational_reason_code(agent["status"]),
                checked_at=utc_now_iso(),
            )
        card = TrustedAgentCard.from_dict(json.loads(row["card_json"]))
        registry = CardRegistry()
        verified = registry.register(card)
        return TrustCardVerifyResponse(
            trust_card_id=row["id"],
            agent_id=row["agent_id"],
            status=row["status"],
            verified=verified,
            reason="signature_valid" if verified else "signature_invalid",
            checked_at=utc_now_iso(),
        )

    def _agent_row(self, agent_id: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT *
            FROM agents
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND deleted_at IS NULL
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()

    def _agent_is_operational(self, agent_id: str) -> bool:
        row = self._agent_row(agent_id)
        return row is not None and is_agent_operational(row["status"])


def trust_card_response(row: Row) -> TrustCardResponse:
    """Serialize a trust card row."""

    return TrustCardResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        agent_id=row["agent_id"],
        issuer=row["issuer"],
        card=json.loads(row["card_json"]),
        signature=row["signature"],
        status=row["status"],
        valid_from=row["valid_from"],
        valid_until=row["valid_until"],
        issued_at=row["issued_at"],
        revoked_at=row["revoked_at"],
        revocation_reason=row["revocation_reason"],
    )
