from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.agents.credentials import (
    AgentCredentialRepository,
    credential_token_hash_candidates,
    hash_credential_token,
    legacy_credential_token_hash,
)
from product_platform.agents.models import CredentialScopeRequest
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class CredentialPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(connection)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com", "viewer@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.admin_token = self._login("admin@example.com", ["Platform Admin"])
        self.viewer_token = self._login("viewer@example.com", ["Viewer"])

    def _insert_agent(self, connection) -> None:
        now = "2026-04-30T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, endpoint_url, owner_user_id, sponsor_user_id, status,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "agent_credentials_demo",
                "org_default",
                "env_default",
                "Credential Demo",
                "Agent used for credential metadata tests.",
                "langgraph",
                "service",
                None,
                "user_admin",
                "user_admin",
                "active",
                now,
                now,
            ),
        )

    def _login(self, email: str, roles: list[str]) -> str:
        response = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def _headers(self, token: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token or self.admin_token}",
            "X-Environment-ID": "env_default",
        }

    def _repository(self) -> AgentCredentialRepository:
        return AgentCredentialRepository(
            self.database.connect(),
            organization_id="org_default",
            environment_id="env_default",
        )

    def test_integration_metadata_insert_persists_scopes(self) -> None:
        row = self._repository().create_metadata(
            agent_id="agent_credentials_demo",
            credential_type="bearer",
            raw_token="phase1-secret-token",
            issuer="local-agentmesh",
            expires_at="2026-05-01T00:00:00+00:00",
            scopes=[
                CredentialScopeRequest(
                    scope="claims:read",
                    resource_type="claim",
                    resource_id="claim/*",
                )
            ],
            metadata_json={"issued_for": "phase1-test"},
        )

        self.assertTrue(row["id"].startswith("cred_"))
        self.assertEqual(row["token_hash"], hash_credential_token("phase1-secret-token"))
        self.assertEqual(row["status"], "active")
        scopes = self._repository().list_scopes(row["id"])
        self.assertEqual(len(scopes), 1)
        self.assertEqual(scopes[0]["scope"], "claims:read")
        self.assertEqual(scopes[0]["resource_type"], "claim")
        self.assertEqual(scopes[0]["resource_id"], "claim/*")

    def test_security_raw_token_is_not_persisted(self) -> None:
        raw_token = "never-store-this-token"

        self._repository().create_metadata(
            agent_id="agent_credentials_demo",
            credential_type="bearer",
            raw_token=raw_token,
            issuer="local-agentmesh",
            expires_at="2026-05-01T00:00:00+00:00",
            scopes=[],
            metadata_json={"note": "safe metadata only"},
        )

        rows = self.database.connect().execute(
            "SELECT token_hash, metadata_json FROM agent_credentials"
        ).fetchall()
        persisted = json.dumps([dict(row) for row in rows], sort_keys=True)
        self.assertNotIn(raw_token, persisted)
        self.assertIn(hash_credential_token(raw_token), persisted)

    def test_security_token_hash_uses_pepper_key_id_and_previous_peppers(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPHANIX_GATEWAY_TOKEN_HASH_PEPPER": "current-pepper",
                "OPHANIX_GATEWAY_TOKEN_HASH_PEPPER_ID": "current",
                "OPHANIX_GATEWAY_TOKEN_HASH_PREVIOUS_PEPPERS": "previous:old-pepper",
                "OPHANIX_GATEWAY_TOKEN_HASH_ACCEPT_LEGACY": "false",
            },
            clear=False,
        ):
            current_hash = hash_credential_token("phase1-secret-token")
            candidates = credential_token_hash_candidates("phase1-secret-token")

        self.assertTrue(current_hash.startswith("hmac-sha256:current:"))
        self.assertTrue(any(candidate.startswith("hmac-sha256:previous:") for candidate in candidates))
        self.assertNotIn(legacy_credential_token_hash("phase1-secret-token"), candidates)

    def test_security_legacy_hash_candidate_requires_explicit_opt_in_when_peppered(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPHANIX_GATEWAY_TOKEN_HASH_PEPPER": "current-pepper",
                "OPHANIX_GATEWAY_TOKEN_HASH_ACCEPT_LEGACY": "true",
            },
            clear=False,
        ):
            candidates = credential_token_hash_candidates("phase1-secret-token")

        self.assertIn(legacy_credential_token_hash("phase1-secret-token"), candidates)

    def test_security_metadata_rejects_sensitive_keys_and_secret_like_values(self) -> None:
        repository = self._repository()
        with self.assertRaisesRegex(ValueError, "secret material"):
            repository.create_metadata(
                agent_id="agent_credentials_demo",
                credential_type="bearer",
                raw_token="phase1-secret-token",
                issuer="local-agentmesh",
                expires_at="2026-05-01T00:00:00+00:00",
                scopes=[],
                metadata_json={"apiToken": "masked-or-not-this-is-not-allowed"},
            )

        with self.assertRaisesRegex(ValueError, "secret material"):
            repository.create_metadata(
                agent_id="agent_credentials_demo",
                credential_type="bearer",
                raw_token="phase1-secret-token",
                issuer="local-agentmesh",
                expires_at="2026-05-01T00:00:00+00:00",
                scopes=[],
                metadata_json={"note": "Authorization: secret-token-value"},
            )

    def test_api_list_filters_by_status_and_hides_hashes(self) -> None:
        repository = self._repository()
        active = repository.create_metadata(
            agent_id="agent_credentials_demo",
            credential_type="bearer",
            raw_token="active-token",
            issuer="local-agentmesh",
            expires_at="2026-05-01T00:00:00+00:00",
            scopes=[CredentialScopeRequest(scope="claims:read", resource_type="claim")],
            metadata_json={},
        )
        repository.create_metadata(
            agent_id="agent_credentials_demo",
            credential_type="bearer",
            raw_token="revoked-token",
            issuer="local-agentmesh",
            expires_at="2026-05-01T00:00:00+00:00",
            scopes=[CredentialScopeRequest(scope="claims:write", resource_type="claim")],
            metadata_json={},
            status="revoked",
        )

        response = self.client.get(
            "/api/v1/agents/agent_credentials_demo/credentials?status=active",
            headers=self._headers(self.viewer_token),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([credential["id"] for credential in payload], [active["id"]])
        self.assertEqual(payload[0]["status"], "active")
        self.assertNotIn("token_hash", payload[0])
        self.assertEqual(payload[0]["scopes"][0]["scope"], "claims:read")


if __name__ == "__main__":
    unittest.main()
