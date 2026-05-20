from __future__ import annotations

import json
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.auth import AuthService, DevLoginRequest, SESSION_COOKIE_NAME
from product_platform.api.settings import Settings
from product_platform.deployment.security import cloud_security_checks

from oidc_test_utils import OIDCTestKey, oidc_claims


PACKAGE_DIR = Path(__file__).resolve().parents[1]


def _enterprise_settings(key: OIDCTestKey) -> Settings:
    return Settings(
        app_name="Ophanix Test Platform",
        environment="test",
        build_sha="test-sha",
        build_time="2026-05-20T00:00:00Z",
        enable_dev_login=False,
        session_secret="test-secret",
        idp_issuer_url="https://idp.example.com/oauth2/default",
        idp_audience="api://ophanix-product-platform",
        idp_jwks_json=key.jwks_json,
        idp_group_role_map_json=json.dumps({"policy-team": ["Policy Admin"]}),
    )


class TestsDocsProductionReadinessPhase2Tests(unittest.TestCase):
    def test_enterprise_oidc_rbac_session_lifecycle(self) -> None:
        key = OIDCTestKey()
        settings = _enterprise_settings(key)
        service = AuthService(settings)
        token = key.token(
            oidc_claims(
                roles=[],
                groups=["policy-team"],
                email="policy@example.com",
                name="Policy User",
                sub="policy-user",
                ophanix_environment_ids=["env_default"],
                jti="enterprise-session-1",
            )
        )

        principal = service.verify_token(token)
        self.assertIsNotNone(principal)
        assert principal is not None
        self.assertEqual(principal.roles, ["Policy Admin"])
        self.assertEqual(principal.environment_ids, ["env_default"])
        self.assertEqual(principal.token_id, "enterprise-session-1")

        client = TestClient(create_app(settings), raise_server_exceptions=False)
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        allowed = client.post(
            "/api/v1/policies",
            headers={"Authorization": f"Bearer {token}", "X-Environment-ID": "env_default"},
        )
        denied = client.post(
            "/api/v1/policies",
            headers={"Authorization": f"Bearer {token}", "X-Environment-ID": "env_other"},
        )
        bad_audience = client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": "Bearer "
                + key.token(oidc_claims(aud="api://wrong", roles=[], groups=["policy-team"]))
            },
        )
        expired = client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": "Bearer "
                + key.token(
                    oidc_claims(
                        exp=int(time.time()) - 60,
                        roles=[],
                        groups=["policy-team"],
                    )
                )
            },
        )

        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["roles"], ["Policy Admin"])
        self.assertEqual(me.json()["environment_ids"], ["env_default"])
        self.assertEqual(allowed.status_code, 201, allowed.text)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["message"], "Environment access is denied.")
        self.assertEqual(bad_audience.status_code, 401)
        self.assertEqual(expired.status_code, 401)

        expired_local = AuthService(Settings(session_secret="test-secret", session_ttl_seconds=-1))
        local_login = expired_local.login(DevLoginRequest(email="admin@example.com"))
        self.assertIsNone(expired_local.verify_token(local_login.access_token))

        local_client = TestClient(
            create_app(Settings(session_secret="test-secret")),
            raise_server_exceptions=False,
        )
        local_login = local_client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com"},
        )
        self.assertEqual(local_login.status_code, 200, local_login.text)
        logout = local_client.post("/api/v1/auth/logout")
        self.assertEqual(logout.status_code, 200)
        self.assertIn(f"{SESSION_COOKIE_NAME}=", logout.headers["set-cookie"])
        self.assertIn("Max-Age=0", logout.headers["set-cookie"])

        production_settings = {
            "environment": "production",
            "database_url": "postgresql://ophanix:secret@db.example.com:5432/ophanix",
            "session_secret": "production-test-secret",
            "secret_manager_ref": "env",
            "gateway_token_hash_pepper": "gateway-pepper",
            "api_key_hash_pepper": "api-key-pepper",
            "tool_gateway_upstream_host_allowlist": ["*.example.com"],
            "idp_issuer_url": "https://idp.example.com/oauth2/default",
            "idp_audience": "api://ophanix-product-platform",
        }
        with self.assertRaisesRegex(ValueError, "OPHANIX_IDP_JWKS_URL"):
            create_app(Settings(**production_settings))

    def test_cloud_security_docs_and_checks_match_oidc_jwks_contract(self) -> None:
        missing_jwks = Settings(
            deployment_mode="cloud",
            idp_issuer_url="https://idp.example.com/oauth2/default",
            idp_audience="api://ophanix-product-platform",
            session_secret="test-secret",
        )
        healthy = Settings(
            deployment_mode="cloud",
            idp_issuer_url="https://idp.example.com/oauth2/default",
            idp_audience="api://ophanix-product-platform",
            idp_jwks_url="https://idp.example.com/oauth2/default/keys",
            session_secret="test-secret",
        )

        missing_checks = {check.key: check for check in cloud_security_checks(missing_jwks)}
        healthy_checks = {check.key: check for check in cloud_security_checks(healthy)}
        docs = (PACKAGE_DIR / "deploy/cloud/security.md").read_text()

        self.assertEqual(missing_checks["identity_provider"].status, "missing")
        self.assertIn("OPHANIX_IDP_JWKS_URL", missing_checks["identity_provider"].detail)
        self.assertEqual(healthy_checks["identity_provider"].status, "healthy")
        self.assertIn("OPHANIX_IDP_JWKS_URL", docs)
        self.assertIn("OPHANIX_IDP_GROUP_ROLE_MAP_JSON", docs)
        self.assertIn("SAML and SCIM are not implemented", docs)


if __name__ == "__main__":
    unittest.main()
