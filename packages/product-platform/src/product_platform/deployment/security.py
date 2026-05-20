"""Cloud deployment security configuration checks."""

from __future__ import annotations

from dataclasses import dataclass

from product_platform.api.settings import Settings


@dataclass(frozen=True)
class SecurityCheck:
    key: str
    status: str
    detail: str


def cloud_security_checks(settings: Settings) -> list[SecurityCheck]:
    """Return IdP, TLS, network, and CORS configuration status."""

    idp_configured = bool(
        settings.idp_issuer_url
        and settings.idp_audience
        and (settings.idp_jwks_url or settings.idp_jwks_json)
    )
    return [
        SecurityCheck(
            key="identity_provider",
            status="healthy" if idp_configured else "missing",
            detail="Identity provider issuer, audience, and JWKS are configured."
            if idp_configured
            else (
                "OPHANIX_IDP_ISSUER_URL, OPHANIX_IDP_AUDIENCE, and "
                "OPHANIX_IDP_JWKS_URL or OPHANIX_IDP_JWKS_JSON are required."
            ),
        ),
        SecurityCheck(
            key="tls",
            status="healthy" if settings.tls_certificate_ref else "missing",
            detail="TLS certificate reference is configured."
            if settings.tls_certificate_ref
            else "OPHANIX_TLS_CERTIFICATE_REF is required.",
        ),
        SecurityCheck(
            key="internal_network",
            status="healthy" if settings.internal_cidrs else "missing",
            detail="Internal service CIDR allow-list is configured."
            if settings.internal_cidrs
            else "OPHANIX_INTERNAL_CIDRS is required.",
        ),
        SecurityCheck(
            key="cors",
            status="healthy" if settings.cors_origins else "missing",
            detail="Frontend CORS origins are configured."
            if settings.cors_origins
            else "CORS_ALLOWED_ORIGINS must include the frontend domain.",
        ),
    ]
