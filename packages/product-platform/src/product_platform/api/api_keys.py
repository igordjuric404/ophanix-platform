"""Scoped API key lifecycle and verification."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from pydantic import BaseModel, Field

from product_platform.api.auth import UserPrincipal
from product_platform.db.postgres import Connection, Row


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
        key_id = _key_id_from_secret(secret)
        if key_id is None:
            return None
        return self._records.get(key_id)


class DatabaseApiKeyStore(ApiKeyStore):
    """Database-backed API key lifecycle and verification."""

    def __init__(self, connection: Connection, secret_pepper: str) -> None:
        super().__init__(secret_pepper)
        self.connection = connection

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
        self.connection.execute(
            """
            INSERT INTO api_keys (
                id, organization_id, name, hashed_secret, scopes_json, kind,
                expires_at, last_used_at, revoked_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key_id,
                organization_id,
                name,
                self.hash_secret(secret),
                json.dumps(list(scopes), sort_keys=True),
                kind,
                _serialize_timestamp(expires_at),
                None,
                None,
                str(now),
                str(now),
            ),
        )
        return self._get_record(key_id), secret

    def list_keys(self, organization_id: str) -> list[ApiKeyRecord]:
        rows = self.connection.execute(
            """
            SELECT *
            FROM api_keys
            WHERE organization_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (organization_id,),
        ).fetchall()
        return [_record_from_row(row) for row in rows]

    def revoke(self, key_id: str, organization_id: str) -> bool:
        now = str(int(time.time()))
        row = self.connection.execute(
            """
            UPDATE api_keys
            SET revoked_at = COALESCE(revoked_at, ?), updated_at = ?
            WHERE id = ? AND organization_id = ?
            RETURNING *
            """,
            (now, now, key_id, organization_id),
        ).fetchone()
        return row is not None

    def authenticate(self, secret: str) -> UserPrincipal | None:
        key_id = _key_id_from_secret(secret)
        if key_id is None:
            return None
        row = self.connection.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,)).fetchone()
        if row is None:
            return None
        record = _record_from_row(row)
        now = int(time.time())
        if record.revoked_at is not None:
            return None
        if record.expires_at is not None and record.expires_at < now:
            return None
        if not self.verify_secret(secret, record.hashed_secret):
            return None
        self.connection.execute(
            "UPDATE api_keys SET last_used_at = ?, updated_at = ? WHERE id = ?",
            (str(now), str(now), record.id),
        )
        return UserPrincipal(
            id=record.id,
            email=f"api-key-{record.id}@keys.ophanix.ai",
            display_name=record.name,
            roles=[],
            scopes=list(record.scopes),
            organization_id=record.organization_id,
            actor_type="api_key",
        )

    def _get_record(self, key_id: str) -> ApiKeyRecord:
        row = self.connection.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,)).fetchone()
        if row is None:
            raise KeyError(f"API key not found: {key_id}")
        return _record_from_row(row)


def _key_id_from_secret(secret: str) -> str | None:
    prefix, separator, rest = secret.partition("_")
    if prefix != "opx" or not separator:
        return None
    key_id, separator, _ = rest.partition("_")
    if not separator:
        return None
    return key_id


def _record_from_row(row: Row) -> ApiKeyRecord:
    return ApiKeyRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        name=row["name"],
        hashed_secret=row["hashed_secret"],
        scopes=list(json.loads(row["scopes_json"] or "[]")),
        kind=row["kind"],
        expires_at=_parse_timestamp(row["expires_at"]),
        last_used_at=_parse_timestamp(row["last_used_at"]),
        revoked_at=_parse_timestamp(row["revoked_at"]),
        created_at=_parse_timestamp(row["created_at"]) or 0,
    )


def _serialize_timestamp(value: int | None) -> str | None:
    return None if value is None else str(int(value))


def _parse_timestamp(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except ValueError:
        return None
