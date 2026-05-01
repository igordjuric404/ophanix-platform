"""Scoped API key lifecycle and verification."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

from pydantic import BaseModel, Field

from product_platform.api.auth import UserPrincipal


class ApiKeyCreateRequest(BaseModel):
    """Create a scoped API key."""

    name: str
    scopes: list[str] = Field(default_factory=list)
    kind: str = "agent"
    expires_at: int | None = None


class ApiKeyResponse(BaseModel):
    """API key metadata returned to clients."""

    id: str
    organization_id: str
    name: str
    scopes: list[str]
    kind: str
    expires_at: int | None
    last_used_at: int | None
    revoked_at: int | None
    created_at: int


class ApiKeyCreateResponse(BaseModel):
    """API key creation response with one-time secret."""

    key: ApiKeyResponse
    secret: str


@dataclass
class ApiKeyRecord:
    """Stored API key record. Raw secret is never stored."""

    id: str
    organization_id: str
    name: str
    hashed_secret: str
    scopes: list[str]
    kind: str
    expires_at: int | None
    last_used_at: int | None
    revoked_at: int | None
    created_at: int

    def to_response(self) -> ApiKeyResponse:
        return ApiKeyResponse(
            id=self.id,
            organization_id=self.organization_id,
            name=self.name,
            scopes=list(self.scopes),
            kind=self.kind,
            expires_at=self.expires_at,
            last_used_at=self.last_used_at,
            revoked_at=self.revoked_at,
            created_at=self.created_at,
        )


class ApiKeyStore:
    """In-memory API key store used until the canonical DB phase."""

    def __init__(self, secret_pepper: str) -> None:
        self._secret_pepper = secret_pepper
        self._records: dict[str, ApiKeyRecord] = {}

    @property
    def records(self) -> dict[str, ApiKeyRecord]:
        return self._records

    def create_key(
        self,
        *,
        organization_id: str,
        name: str,
        scopes: list[str],
        kind: str,
        expires_at: int | None = None,
    ) -> tuple[ApiKeyRecord, str]:
        key_id = secrets.token_hex(8)
        secret = f"opx_{key_id}_{secrets.token_urlsafe(24)}"
        now = int(time.time())
        record = ApiKeyRecord(
            id=key_id,
            organization_id=organization_id,
            name=name,
            hashed_secret=self.hash_secret(secret),
            scopes=list(scopes),
            kind=kind,
            expires_at=expires_at,
            last_used_at=None,
            revoked_at=None,
            created_at=now,
        )
        self._records[key_id] = record
        return record, secret

    def list_keys(self, organization_id: str) -> list[ApiKeyRecord]:
        return [
            record
            for record in self._records.values()
            if record.organization_id == organization_id
        ]

    def revoke(self, key_id: str, organization_id: str) -> bool:
        record = self._records.get(key_id)
        if record is None or record.organization_id != organization_id:
            return False
        record.revoked_at = int(time.time())
        return True

    def authenticate(self, secret: str) -> UserPrincipal | None:
        record = self._record_for_secret(secret)
        if record is None:
            return None
        now = int(time.time())
        if record.revoked_at is not None:
            return None
        if record.expires_at is not None and record.expires_at < now:
            return None
        if not self.verify_secret(secret, record.hashed_secret):
            return None
        record.last_used_at = now
        return UserPrincipal(
            id=record.id,
            email=f"api-key-{record.id}@keys.ophanix.ai",
            display_name=record.name,
            roles=[],
            scopes=list(record.scopes),
            organization_id=record.organization_id,
            actor_type="api_key",
        )

    def hash_secret(self, secret: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            (self._secret_pepper + secret).encode(),
            salt,
            120_000,
        )
        return f"{base64.urlsafe_b64encode(salt).decode()}:{base64.urlsafe_b64encode(digest).decode()}"

    def verify_secret(self, secret: str, hashed_secret: str) -> bool:
        salt_part, _, digest_part = hashed_secret.partition(":")
        if not salt_part or not digest_part:
            return False
        salt = base64.urlsafe_b64decode(salt_part.encode())
        expected = base64.urlsafe_b64decode(digest_part.encode())
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            (self._secret_pepper + secret).encode(),
            salt,
            120_000,
        )
        return hmac.compare_digest(actual, expected)

    def _record_for_secret(self, secret: str) -> ApiKeyRecord | None:
        prefix, separator, rest = secret.partition("_")
        if prefix != "opx" or not separator:
            return None
        key_id, separator, _ = rest.partition("_")
        if not separator:
            return None
        return self._records.get(key_id)
