"""AgentMesh identity adapter for product registration."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization

from agentmesh.identity.agent_id import AgentIdentity

from product_platform.agents.models import AgentBootstrapMaterial, AgentIdentityProofRequest
from product_platform.db.time import utc_now_iso

SUPPORTED_IDENTITY_PROOF_TYPES = frozenset({"agentmesh-local", "spiffe", "jwt", "x509", "kms"})
DEFAULT_TRUST_ROOT_ID = "local-agentmesh"
DEFAULT_TRUST_ROOT_VERSION = "v1"
DEFAULT_TRUSTED_ISSUER = "local-agentmesh"


@dataclass(frozen=True)
class VerifiedAgentIdentityProof:
    """Validated workload identity proof metadata."""

    proof_type: str
    issuer: str
    audience: str
    subject: str | None
    environment_binding: str
    trusted_root_id: str
    trusted_root_version: str
    key_reference: str | None
    certificate_chain: list[str]
    proof_metadata: dict
    verified_at: str


@dataclass(frozen=True)
class CreatedAgentIdentity:
    """Public identity metadata plus one-time bootstrap material."""

    did: str
    public_key: str
    verification_key_id: str
    public_key_fingerprint: str
    key_type: str
    proof: VerifiedAgentIdentityProof
    bootstrap: AgentBootstrapMaterial


class AgentIdentityAdapter:
    """Adapter around AgentMesh identity creation."""

    key_type = "ed25519"

    def create_identity(
        self,
        *,
        name: str,
        sponsor_email: str,
        organization: str,
        description: str,
        environment_id: str = "env_default",
        proof: AgentIdentityProofRequest | None = None,
        capabilities: list[str] | None = None,
    ) -> CreatedAgentIdentity:
        """Create an AgentMesh identity and derive product metadata."""

        verified_proof = self.verify_identity_proof(
            proof or AgentIdentityProofRequest(),
            organization_id=organization,
            environment_id=environment_id,
        )
        identity = AgentIdentity.create(
            name=name,
            sponsor=sponsor_email,
            capabilities=capabilities or [],
            organization=organization,
            description=description,
        )
        private_key = identity._private_key
        if private_key is None:
            raise RuntimeError("AgentMesh identity did not return local private key material.")
        private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii")
        did = str(identity.did)
        fingerprint = hashlib.sha256(identity.public_key.encode("utf-8")).hexdigest()
        bootstrap = AgentBootstrapMaterial(
            did=did,
            public_key=identity.public_key,
            verification_key_id=identity.verification_key_id,
            private_key_pem=private_key_pem,
        )
        return CreatedAgentIdentity(
            did=did,
            public_key=identity.public_key,
            verification_key_id=identity.verification_key_id,
            public_key_fingerprint=fingerprint,
            key_type=self.key_type,
            proof=verified_proof,
            bootstrap=bootstrap,
        )

    def verify_identity_proof(
        self,
        proof: AgentIdentityProofRequest,
        *,
        organization_id: str,
        environment_id: str,
    ) -> VerifiedAgentIdentityProof:
        """Validate identity proof metadata against supported trust roots."""

        proof_type = proof.proof_type.strip().lower()
        if proof_type not in SUPPORTED_IDENTITY_PROOF_TYPES:
            supported = ", ".join(sorted(SUPPORTED_IDENTITY_PROOF_TYPES))
            raise ValueError(f"Identity proof_type must be one of: {supported}.")
        trusted_root_id = proof.trusted_root_id.strip()
        if trusted_root_id != DEFAULT_TRUST_ROOT_ID:
            raise ValueError(f"Identity trusted root is not configured: {trusted_root_id}.")
        issuer = proof.issuer.strip()
        if issuer != DEFAULT_TRUSTED_ISSUER:
            raise ValueError(f"Identity issuer is not trusted for {trusted_root_id}: {issuer}.")
        audience = (proof.audience or environment_id).strip()
        allowed_audiences = {
            environment_id,
            f"ophanix:{organization_id}:{environment_id}",
        }
        if audience not in allowed_audiences:
            raise ValueError(f"Identity audience is not valid for environment {environment_id}.")
        trusted_root_version = proof.trusted_root_version.strip() or DEFAULT_TRUST_ROOT_VERSION
        return VerifiedAgentIdentityProof(
            proof_type=proof_type,
            issuer=issuer,
            audience=audience,
            subject=proof.subject,
            environment_binding=f"{organization_id}:{environment_id}",
            trusted_root_id=trusted_root_id,
            trusted_root_version=trusted_root_version,
            key_reference=proof.key_reference,
            certificate_chain=proof.certificate_chain,
            proof_metadata=proof.proof_metadata,
            verified_at=utc_now_iso(),
        )
