from __future__ import annotations

import json
import time
import unittest
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from product_platform import create_app
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.api.auth import AuthService
from product_platform.api.settings import Settings


class OIDCTestKey:
    def __init__(self, *, kid: str = "kid-1") -> None:
        self.kid = kid
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(RSAAlgorithm.to_jwk(self.private_key.public_key()))
        jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
        self.jwks_json = json.dumps({"keys": [jwk]})

    def token(self, claims: dict[str, Any], *, kid: str | None = None) -> str:
        return jwt.encode(
            claims,
            self.private_key,
            algorithm="RS256",
            headers={"kid": kid or self.kid},
        )


def _oidc_settings(key: OIDCTestKey) -> Settings:
    return Settings(
        app_name="Ophanix Test Platform",
        environment="test",
        build_sha="test-sha",
        build_time="2026-05-19T00:00:00Z",
        enable_dev_login=False,
        session_secret="test-secret",
        idp_issuer_url="https://idp.example.com/oauth2/default",
        idp_audience="api://ophanix-product-platform",
        idp_jwks_json=key.jwks_json,
        idp_group_role_map_json=json.dumps({"policy-team": ["Policy Admin"]}),
    )


def _claims(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": "https://idp.example.com/oauth2/default",
        "aud": "api://ophanix-product-platform",
        "sub": "user-123",
        "email": "policy@example.com",
        "name": "Policy User",
        "groups": ["policy-team"],
        "ophanix_environment_ids": ["env_default"],
        "exp": now + 600,
        "iat": now,
        "jti": "jwt-123",
    }
    claims.update(overrides)
    return claims


class AuthRemediationPhase1Tests(unittest.TestCase):
    def test_oidc_jwks_validation_rejects_bad_claims(self) -> None:
        key = OIDCTestKey()
        service = AuthService(_oidc_settings(key))

        valid = service.verify_token(key.token(_claims()))
        self.assertIsNotNone(valid)
        assert valid is not None
        self.assertEqual(valid.email, "policy@example.com")
        self.assertEqual(valid.roles, ["Policy Admin"])
        self.assertEqual(valid.environment_ids, ["env_default"])
        self.assertEqual(valid.idp_subject, "user-123")

        self.assertIsNone(service.verify_token(key.token(_claims(iss="https://evil.example.com"))))
        self.assertIsNone(service.verify_token(key.token(_claims(aud="api://wrong"))))
        self.assertIsNone(service.verify_token(key.token(_claims(exp=int(time.time()) - 60))))
        self.assertIsNone(service.verify_token(key.token(_claims(), kid="missing-kid")))

        tampered_parts = key.token(_claims()).split(".")
        tampered_parts[-1] = "invalid-signature"
        self.assertIsNone(service.verify_token(".".join(tampered_parts)))

    def test_oidc_claims_authorize_only_claimed_environments(self) -> None:
        key = OIDCTestKey()
        app = create_app(_oidc_settings(key))
        client = TestClient(app, raise_server_exceptions=False)
        token = key.token(_claims())

        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        allowed = client.post(
            "/api/v1/policies",
            headers={"Authorization": f"Bearer {token}", "X-Environment-ID": "env_default"},
        )
        denied = client.post(
            "/api/v1/policies",
            headers={"Authorization": f"Bearer {token}", "X-Environment-ID": "env_other"},
        )

        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["roles"], ["Policy Admin"])
        self.assertEqual(me.json()["environment_ids"], ["env_default"])
        self.assertEqual(allowed.status_code, 201, allowed.text)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["message"], "Environment access is denied.")

    def test_production_config_requires_enterprise_idp_and_rejects_dev_auth(self) -> None:
        key = OIDCTestKey()
        production_settings = {
            "environment": "production",
            "database_url": "postgresql://ophanix:secret@db.example.com:5432/ophanix",
            "session_secret": "production-test-secret",
            "secret_manager_ref": "env",
            "gateway_token_hash_pepper": "gateway-pepper",
            "api_key_hash_pepper": "api-key-pepper",
            "tool_gateway_upstream_host_allowlist": ["*.example.com"],
        }

        with self.assertRaisesRegex(ValueError, "OPHANIX_IDP_ISSUER_URL"):
            create_app(Settings(**production_settings))

        with self.assertRaisesRegex(ValueError, "Development login"):
            create_app(
                Settings(
                    **production_settings,
                    enable_dev_login=True,
                    idp_issuer_url="https://idp.example.com/oauth2/default",
                    idp_audience="api://ophanix-product-platform",
                    idp_jwks_json=key.jwks_json,
                )
            )

    def test_human_user_without_environment_membership_is_denied(self) -> None:
        app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-19T00:00:00Z",
                dev_login_allowed_emails=["policy@example.com"],
                session_secret="test-secret",
            )
        )
        client = TestClient(app, raise_server_exceptions=False)
        login = client.post(
            "/api/v1/auth/dev-login",
            json={"email": "policy@example.com", "roles": ["Policy Admin"], "environment_ids": []},
        )
        self.assertEqual(login.status_code, 200, login.text)

        response = client.post(
            "/api/v1/policies",
            headers={
                "Authorization": f"Bearer {login.json()['access_token']}",
                "X-Environment-ID": "env_default",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["message"], "Environment access is denied.")

    def test_break_glass_environment_access_requires_reason_and_is_audited(self) -> None:
        app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-19T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            )
        )
        client = TestClient(app, raise_server_exceptions=False)
        login = client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Platform Admin"], "environment_ids": []},
        )
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["access_token"]

        missing_reason = client.post(
            "/api/v1/policies",
            headers={"Authorization": f"Bearer {token}", "X-Environment-ID": "env_default"},
        )
        allowed = client.post(
            "/api/v1/policies",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Environment-ID": "env_default",
                "X-Break-Glass-Reason": "incident-response",
                "X-Request-ID": "req-break-glass",
            },
        )

        self.assertEqual(missing_reason.status_code, 403)
        self.assertEqual(allowed.status_code, 201, allowed.text)
        events = AuditEventRepository(app.state.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                event_type="auth.environment_break_glass",
                limit=10,
            )
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].decision, "allow")
        self.assertEqual(events[0].trace_id, "req-break-glass")
        self.assertEqual(events[0].payload_json["reason"], "incident-response")


if __name__ == "__main__":
    unittest.main()
