from __future__ import annotations

import json
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm


class OIDCTestKey:
    def __init__(self, *, kid: str = "kid-1") -> None:
        self.kid = kid
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(RSAAlgorithm.to_jwk(self.private_key.public_key()))
        jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
        self.jwks_json = json.dumps({"keys": [jwk]})

    def token(self, claims: dict[str, Any] | None = None, *, kid: str | None = None) -> str:
        return jwt.encode(
            oidc_claims(**(claims or {})),
            self.private_key,
            algorithm="RS256",
            headers={"kid": kid or self.kid},
        )


def oidc_claims(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": "https://idp.example.com/oauth2/default",
        "aud": "api://ophanix-product-platform",
        "sub": "user-123",
        "email": "admin@example.com",
        "name": "Admin User",
        "roles": ["Platform Admin"],
        "ophanix_environment_ids": ["env_default"],
        "exp": now + 600,
        "iat": now,
        "jti": "jwt-123",
    }
    claims.update(overrides)
    return claims


def oidc_settings_kwargs(key: OIDCTestKey) -> dict[str, str]:
    return {
        "idp_issuer_url": "https://idp.example.com/oauth2/default",
        "idp_audience": "api://ophanix-product-platform",
        "idp_jwks_json": key.jwks_json,
    }
