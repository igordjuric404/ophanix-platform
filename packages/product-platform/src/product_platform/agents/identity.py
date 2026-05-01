"""AgentMesh identity adapter for product registration."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization

from agentmesh.identity.agent_id import AgentIdentity

from product_platform.agents.models import AgentBootstrapMaterial


@dataclass(frozen=True)
class CreatedAgentIdentity:
    """Public identity metadata plus one-time bootstrap material."""

    did: str
    public_key: str
    verification_key_id: str
    public_key_fingerprint: str
    key_type: str
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
        capabilities: list[str] | None = None,
    ) -> CreatedAgentIdentity:
        """Create an AgentMesh identity and derive product metadata."""

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
            bootstrap=bootstrap,
        )
