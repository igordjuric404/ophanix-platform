# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ruff: noqa: UP045
"""Authentication helpers for IATP sidecar endpoints."""

import hmac
import os
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException

SERVICE_TOKEN_ENV = "IATP_SERVICE_TOKEN"
ALLOW_INSECURE_ENV = "IATP_ALLOW_INSECURE_LOCAL"


@dataclass(frozen=True)
class IATPAuthConfig:
    """Runtime auth configuration for protected IATP endpoints."""

    service_token: Optional[str]
    allow_insecure_local: bool = False

    @classmethod
    def from_env(
        cls,
        *,
        service_token: Optional[str] = None,
        allow_insecure_local: Optional[bool] = None,
    ) -> "IATPAuthConfig":
        token = service_token if service_token is not None else os.getenv(SERVICE_TOKEN_ENV)
        if allow_insecure_local is None:
            allow_insecure_local = _truthy(os.getenv(ALLOW_INSECURE_ENV), default=False)
        return cls(service_token=token, allow_insecure_local=allow_insecure_local)


def require_iatp_auth(
    *,
    authorization: Optional[str],
    x_iatp_token: Optional[str],
    config: IATPAuthConfig,
) -> None:
    """Validate service-token auth for protected IATP operations."""

    if config.allow_insecure_local:
        return
    if not config.service_token:
        raise HTTPException(
            status_code=503,
            detail=(
                "IATP service authentication is required but not configured. "
                f"Set {SERVICE_TOKEN_ENV} or enable {ALLOW_INSECURE_ENV} for local-only tests."
            ),
        )
    supplied = _bearer_token(authorization) or _clean_token(x_iatp_token)
    if supplied is None or not hmac.compare_digest(supplied, config.service_token):
        raise HTTPException(
            status_code=401,
            detail="IATP service authentication failed.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def is_user_override_confirmed(value: Optional[str]) -> bool:
    """Return whether a warning override header is an explicit affirmative."""

    return bool(value and value.strip().lower() == "true")


def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip() or None


def _clean_token(token: Optional[str]) -> Optional[str]:
    if token is None:
        return None
    token = token.strip()
    return token or None


def _truthy(raw: Optional[str], *, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
