"""Scoped API key lifecycle and verification."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator

from product_platform.api.auth import UserPrincipal
from product_platform.db.postgres import Connection, Row


class ApiKeyCreateRequest(BaseModel):
    """Create a scoped API key."""

    name: str
    scopes: list[str] = Field(default_factory=list)
    kind: str = "agent"
    expires_at: int | None = None
    environment_ids: list[str] = Field(default_factory=list)

    @field_validator("environment_ids")
    @classmethod
    def _normalize_environment_ids(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for environment_id in value:
            stripped = environment_id.strip()
            if stripped and stripped not in normalized:
                normalized.append(stripped)
        return normalized


class ApiKeyRevokeRequest(BaseModel):
    """Revoke an API key with durable reason evidence."""

    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def _normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) > 240:
            raise ValueError("API key revoke reason must be 240 characters or fewer.")
        return normalized or None


class ApiKeyRotateRequest(BaseModel):
    """Rotate an API key and atomically revoke the previous key."""

    name: str | None = None
    expires_at: int | None = None
    environment_ids: list[str] | None = None
    reason: str | None = None

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return normalized

    @field_validator("environment_ids")
    @classmethod
    def _normalize_environment_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized: list[str] = []
        for environment_id in value:
            stripped = environment_id.strip()
            if stripped and stripped not in normalized:
                normalized.append(stripped)
        return normalized

    @field_validator("reason")
    @classmethod
    def _normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) > 240:
            raise ValueError("API key rotation reason must be 240 characters or fewer.")
        return normalized or None


class ApiKeyResponse(BaseModel):
    """API key metadata returned to clients."""

    id: str
    organization_id: str
    name: str
    scopes: list[str]
    kind: str
    environment_ids: list[str]
    expires_at: int | None
    last_used_at: int | None
    revoked_at: int | None
    created_at: int
    created_by: str | None = None
    revoked_by: str | None = None
    revoked_reason: str | None = None
    rotated_from_key_id: str | None = None
    rotated_to_key_id: str | None = None


class ApiKeyCreateResponse(BaseModel):
    """API key creation response with one-time secret."""

    key: ApiKeyResponse
    secret: str


class ApiKeyRotationResponse(BaseModel):
    """API key rotation response with the replacement one-time secret."""

    previous_key: ApiKeyResponse
    replacement_key: ApiKeyResponse
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
    environment_ids: list[str]
    expires_at: int | None
    last_used_at: int | None
    revoked_at: int | None
    created_at: int
    created_by: str | None = None
    revoked_by: str | None = None
    revoked_reason: str | None = None
    rotated_from_key_id: str | None = None
    rotated_to_key_id: str | None = None

    def to_response(self) -> ApiKeyResponse:
        return ApiKeyResponse(
            id=self.id,
            organization_id=self.organization_id,
            name=self.name,
            scopes=list(self.scopes),
            kind=self.kind,
            environment_ids=list(self.environment_ids),
            expires_at=self.expires_at,
            last_used_at=self.last_used_at,
            revoked_at=self.revoked_at,
            created_at=self.created_at,
            created_by=self.created_by,
            revoked_by=self.revoked_by,
            revoked_reason=self.revoked_reason,
            rotated_from_key_id=self.rotated_from_key_id,
            rotated_to_key_id=self.rotated_to_key_id,
        )


@dataclass(frozen=True)
class ApiKeyAuthenticationResult:
    """API key authentication result with a safe denial reason."""

    principal: UserPrincipal | None
    record: ApiKeyRecord | None
    reason_code: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.principal is not None


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
        environment_ids: list[str] | None = None,
        expires_at: int | None = None,
        created_by: str | None = None,
        rotated_from_key_id: str | None = None,
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
            environment_ids=list(environment_ids or []),
            expires_at=expires_at,
            last_used_at=None,
            revoked_at=None,
            created_at=now,
            created_by=created_by,
            revoked_by=None,
            revoked_reason=None,
            rotated_from_key_id=rotated_from_key_id,
            rotated_to_key_id=None,
        )
        self._records[key_id] = record
        return record, secret

    def list_keys(self, organization_id: str) -> list[ApiKeyRecord]:
        return [
            record
            for record in self._records.values()
            if record.organization_id == organization_id
        ]

    def get_key(self, key_id: str, organization_id: str | None = None) -> ApiKeyRecord | None:
        record = self._records.get(key_id)
        if record is None:
            return None
        if organization_id is not None and record.organization_id != organization_id:
            return None
        return record

    def revoke_key(
        self,
        key_id: str,
        organization_id: str,
        *,
        revoked_by: str | None = None,
        revoked_reason: str | None = None,
        rotated_to_key_id: str | None = None,
        require_active: bool = False,
    ) -> ApiKeyRecord | None:
        record = self.get_key(key_id, organization_id)
        if record is None:
            return None
        if require_active and record.revoked_at is not None:
            return None
        now = int(time.time())
        if record.revoked_at is None:
            record.revoked_at = now
        if record.revoked_by is None:
            record.revoked_by = revoked_by
        if record.revoked_reason is None:
            record.revoked_reason = revoked_reason
        if record.rotated_to_key_id is None:
            record.rotated_to_key_id = rotated_to_key_id
        return record

    def revoke(self, key_id: str, organization_id: str) -> bool:
        return self.revoke_key(
            key_id,
            organization_id,
            revoked_reason="revoked via API",
        ) is not None

    def rotate_key(
        self,
        key_id: str,
        organization_id: str,
        *,
        name: str,
        environment_ids: list[str],
        expires_at: int,
        actor_id: str | None,
        reason: str,
    ) -> tuple[ApiKeyRecord, ApiKeyRecord, str] | None:
        previous = self.get_key(key_id, organization_id)
        if previous is None or previous.revoked_at is not None:
            return None
        replacement, secret = self.create_key(
            organization_id=organization_id,
            name=name,
            scopes=list(previous.scopes),
            kind=previous.kind,
            environment_ids=environment_ids,
            expires_at=expires_at,
            created_by=actor_id,
            rotated_from_key_id=previous.id,
        )
        revoked = self.revoke_key(
            previous.id,
            organization_id,
            revoked_by=actor_id,
            revoked_reason=reason,
            rotated_to_key_id=replacement.id,
            require_active=True,
        )
        if revoked is None:
            self._records.pop(replacement.id, None)
            return None
        return revoked, replacement, secret

    def authenticate(self, secret: str) -> UserPrincipal | None:
        return self.authenticate_with_result(secret).principal

    def authenticate_with_result(self, secret: str) -> ApiKeyAuthenticationResult:
        record = self._record_for_secret(secret)
        if record is None:
            return ApiKeyAuthenticationResult(None, None, "api_key_not_found")
        if not self.verify_secret(secret, record.hashed_secret):
            return ApiKeyAuthenticationResult(None, record, "api_key_invalid_secret")
        now = int(time.time())
        if record.revoked_at is not None:
            return ApiKeyAuthenticationResult(None, record, "api_key_revoked")
        if record.expires_at is not None and record.expires_at < now:
            return ApiKeyAuthenticationResult(None, record, "api_key_expired")
        record.last_used_at = now
        return ApiKeyAuthenticationResult(_principal_from_record(record), record)

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


def _principal_from_record(record: ApiKeyRecord) -> UserPrincipal:
    return UserPrincipal(
        id=record.id,
        email=f"api-key-{record.id}@keys.ophanix.ai",
        display_name=record.name,
        roles=[],
        scopes=list(record.scopes),
        organization_id=record.organization_id,
        environment_ids=list(record.environment_ids),
        actor_type="api_key",
    )


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
        environment_ids: list[str] | None = None,
        expires_at: int | None = None,
        created_by: str | None = None,
        rotated_from_key_id: str | None = None,
    ) -> tuple[ApiKeyRecord, str]:
        key_id = secrets.token_hex(8)
        secret = f"opx_{key_id}_{secrets.token_urlsafe(24)}"
        now = int(time.time())
        self.connection.execute(
            """
            INSERT INTO api_keys (
                id, organization_id, name, hashed_secret, scopes_json, kind,
                environment_ids_json,
                expires_at, last_used_at, revoked_at, created_at, updated_at,
                created_by, revoked_by, revoked_reason, rotated_from_key_id,
                rotated_to_key_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key_id,
                organization_id,
                name,
                self.hash_secret(secret),
                json.dumps(list(scopes), sort_keys=True),
                kind,
                json.dumps(list(environment_ids or []), sort_keys=True),
                _serialize_timestamp(expires_at),
                None,
                None,
                str(now),
                str(now),
                created_by,
                None,
                None,
                rotated_from_key_id,
                None,
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

    def get_key(self, key_id: str, organization_id: str | None = None) -> ApiKeyRecord | None:
        if organization_id is None:
            row = self.connection.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,)).fetchone()
        else:
            row = self.connection.execute(
                "SELECT * FROM api_keys WHERE id = ? AND organization_id = ?",
                (key_id, organization_id),
            ).fetchone()
        return _record_from_row(row) if row is not None else None

    def revoke_key(
        self,
        key_id: str,
        organization_id: str,
        *,
        revoked_by: str | None = None,
        revoked_reason: str | None = None,
        rotated_to_key_id: str | None = None,
        require_active: bool = False,
    ) -> ApiKeyRecord | None:
        now = str(int(time.time()))
        active_clause = "AND revoked_at IS NULL" if require_active else ""
        row = self.connection.execute(
            f"""
            UPDATE api_keys
            SET revoked_at = COALESCE(revoked_at, ?),
                revoked_by = COALESCE(revoked_by, ?),
                revoked_reason = COALESCE(revoked_reason, ?),
                rotated_to_key_id = COALESCE(rotated_to_key_id, ?),
                updated_at = ?
            WHERE id = ? AND organization_id = ? {active_clause}
            RETURNING *
            """,
            (now, revoked_by, revoked_reason, rotated_to_key_id, now, key_id, organization_id),
        ).fetchone()
        return _record_from_row(row) if row is not None else None

    def revoke(self, key_id: str, organization_id: str) -> bool:
        return self.revoke_key(
            key_id,
            organization_id,
            revoked_reason="revoked via API",
        ) is not None

    def rotate_key(
        self,
        key_id: str,
        organization_id: str,
        *,
        name: str,
        environment_ids: list[str],
        expires_at: int,
        actor_id: str | None,
        reason: str,
    ) -> tuple[ApiKeyRecord, ApiKeyRecord, str] | None:
        previous = self.get_key(key_id, organization_id)
        if previous is None or previous.revoked_at is not None:
            return None
        replacement, secret = self.create_key(
            organization_id=organization_id,
            name=name,
            scopes=list(previous.scopes),
            kind=previous.kind,
            environment_ids=environment_ids,
            expires_at=expires_at,
            created_by=actor_id,
            rotated_from_key_id=previous.id,
        )
        revoked = self.revoke_key(
            previous.id,
            organization_id,
            revoked_by=actor_id,
            revoked_reason=reason,
            rotated_to_key_id=replacement.id,
            require_active=True,
        )
        if revoked is None:
            raise RuntimeError("API key rotation lost the active key update.")
        return revoked, replacement, secret

    def authenticate(self, secret: str) -> UserPrincipal | None:
        return self.authenticate_with_result(secret).principal

    def authenticate_with_result(self, secret: str) -> ApiKeyAuthenticationResult:
        key_id = _key_id_from_secret(secret)
        if key_id is None:
            return ApiKeyAuthenticationResult(None, None, "api_key_not_found")
        row = self.connection.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,)).fetchone()
        if row is None:
            return ApiKeyAuthenticationResult(None, None, "api_key_not_found")
        record = _record_from_row(row)
        if not self.verify_secret(secret, record.hashed_secret):
            return ApiKeyAuthenticationResult(None, record, "api_key_invalid_secret")
        now = int(time.time())
        if record.revoked_at is not None:
            return ApiKeyAuthenticationResult(None, record, "api_key_revoked")
        if record.expires_at is not None and record.expires_at < now:
            return ApiKeyAuthenticationResult(None, record, "api_key_expired")
        self.connection.execute(
            "UPDATE api_keys SET last_used_at = ?, updated_at = ? WHERE id = ?",
            (str(now), str(now), record.id),
        )
        record.last_used_at = now
        return ApiKeyAuthenticationResult(_principal_from_record(record), record)

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
        environment_ids=list(json.loads(row["environment_ids_json"] or "[]")),
        expires_at=_parse_timestamp(row["expires_at"]),
        last_used_at=_parse_timestamp(row["last_used_at"]),
        revoked_at=_parse_timestamp(row["revoked_at"]),
        created_at=_parse_timestamp(row["created_at"]) or 0,
        created_by=_optional_row_value(row, "created_by"),
        revoked_by=_optional_row_value(row, "revoked_by"),
        revoked_reason=_optional_row_value(row, "revoked_reason"),
        rotated_from_key_id=_optional_row_value(row, "rotated_from_key_id"),
        rotated_to_key_id=_optional_row_value(row, "rotated_to_key_id"),
    )


def _optional_row_value(row: Row, key: str) -> str | None:
    if key not in row:
        return None
    value = row[key]
    return str(value) if value is not None else None


def _serialize_timestamp(value: int | None) -> str | None:
    return None if value is None else str(int(value))


def _parse_timestamp(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except ValueError:
        return None
