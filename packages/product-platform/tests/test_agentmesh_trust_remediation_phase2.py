from __future__ import annotations

import base64
import hashlib
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from fastapi.testclient import TestClient

from agentmesh.trust.handshake import (
    CANONICAL_HANDSHAKE_CONTRACT_VERSION,
    canonical_handshake_payload as sdk_canonical_handshake_payload,
)
from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.trust.repository import TrustRepository


class AgentMeshTrustRemediationPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        self.source_private, self.source_public = self._new_keypair()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent(
                connection,
                "source_signed",
                "Signed Source",
                840,
                public_key=self.source_public,
            )
            self._insert_agent(connection, "target_signed", "Signed Target", 810)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-01T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]

    def _headers(self, *, correlation_id: str = "corr-handshake-phase2") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": correlation_id,
        }

    def _new_keypair(self) -> tuple[ed25519.Ed25519PrivateKey, str]:
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return private_key, base64.b64encode(public_key).decode("ascii")

    def _sign(self, payload: str) -> str:
        signature = self.source_private.sign(payload.encode("utf-8"))
        return base64.b64encode(signature).decode("ascii")

    def _insert_agent(
        self,
        connection,
        agent_id: str,
        name: str,
        score: int,
        *,
        public_key: str | None = None,
    ) -> None:
        now = "2026-05-01T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, owner_user_id, sponsor_user_id, status, trust_score,
                trust_tier, credential_status, credential_expires_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                "org_default",
                "env_default",
                name,
                "Signed handshake test agent",
                "agentmesh",
                "service",
                "owner",
                "sponsor",
                "active",
                score,
                "trusted",
                "active",
                "2030-01-01T00:00:00+00:00",
                now,
                now,
            ),
        )
        fingerprint = (
            hashlib.sha256(public_key.encode("utf-8")).hexdigest()
            if public_key is not None
            else f"fingerprint_{agent_id}"
        )
        connection.execute(
            """
            INSERT INTO agent_identities (
                id, agent_id, did, public_key_fingerprint, key_type,
                identity_status, bootstrap_material_json, bootstrap_retrieved_at,
                audience, environment_binding, trusted_root_id, trusted_root_version,
                verified_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"ident_{agent_id}",
                agent_id,
                f"did:mesh:{agent_id}",
                fingerprint,
                "ed25519",
                "active",
                None,
                now,
                "env_default",
                "org_default:env_default",
                "local-agentmesh",
                "2026.05",
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO agent_credentials (
                id, agent_id, credential_type, token_hash, issuer, status,
                issued_at, expires_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"cred_{agent_id}",
                agent_id,
                "api_key",
                f"hash_{agent_id}",
                "ophanix-test",
                "active",
                now,
                "2030-01-01T00:00:00+00:00",
                "{}",
            ),
        )
        TrustRepository(connection, "org_default", "env_default").upsert_score(
            agent_id=agent_id,
            score=score,
            dimensions={"policy_compliance": {"score": score, "signal_count": 1}},
        )

    def _issue_challenge(self) -> dict:
        response = self.client.post(
            "/api/v1/trust/handshakes/challenges",
            headers=self._headers(),
            json={
                "source_agent_id": "source_signed",
                "target_agent_id": "target_signed",
                "purpose": "handoff",
                "threshold_type": "handoff",
                "target_type": "environment",
                "audience": "env_default",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _record_payload(self, challenge: dict, *, payload: str | None = None, **proof_overrides) -> dict:
        proof = {
            "contract_version": challenge["contract_version"],
            "signature_algorithm": "ed25519",
            "challenge_id": challenge["challenge_id"],
            "nonce": challenge["nonce"],
            "audience": challenge["audience"],
            "environment_id": challenge["environment_id"],
            "expires_at": challenge["expires_at"],
            "public_key": self.source_public,
            "signature": self._sign(payload or challenge["canonical_payload"]),
        }
        proof.update(proof_overrides)
        return {
            "source_agent_id": "source_signed",
            "target_agent_id": "target_signed",
            "purpose": "handoff",
            "threshold_type": "handoff",
            "target_type": "environment",
            "proof": proof,
        }

    def test_recorded_handshake_replay_is_rejected_and_audited(self) -> None:
        challenge = self._issue_challenge()

        first = self.client.post(
            "/api/v1/trust/handshakes/record",
            headers=self._headers(correlation_id="corr-handshake-replay"),
            json=self._record_payload(challenge),
        )
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.json()["result"], "allowed")

        replay = self.client.post(
            "/api/v1/trust/handshakes/record",
            headers=self._headers(correlation_id="corr-handshake-replay"),
            json=self._record_payload(challenge),
        )

        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.json()["result"], "denied")
        self.assertEqual(replay.json()["reason"], "replayed_challenge")

        events = AuditEventRepository(self.database.connect()).query(
            AuditEventQuery(
                organization_id="org_default",
                environment_id="env_default",
                resource_type="handshake",
                correlation_id="corr-handshake-replay",
            )
        )
        self.assertEqual(events[0].decision, "deny")
        self.assertEqual(events[0].payload_json["reason"], "replayed_challenge")

    def test_wrong_audience_and_environment_are_rejected(self) -> None:
        audience_challenge = self._issue_challenge()
        wrong_audience_payload = sdk_canonical_handshake_payload(
            contract_version=audience_challenge["contract_version"],
            challenge_id=audience_challenge["challenge_id"],
            nonce=audience_challenge["nonce"],
            audience="other-audience",
            organization_id=audience_challenge["organization_id"],
            environment_id=audience_challenge["environment_id"],
            source_agent_id=audience_challenge["source_agent_id"],
            source_did=audience_challenge["source_did"],
            target_agent_id=audience_challenge["target_agent_id"],
            target_did=audience_challenge["target_did"],
            purpose=audience_challenge["purpose"],
            threshold_type=audience_challenge["threshold_type"],
            target_type=audience_challenge["target_type"],
            target_id=audience_challenge["target_id"],
            expires_at=audience_challenge["expires_at"],
        )
        wrong_audience = self.client.post(
            "/api/v1/trust/handshakes/record",
            headers=self._headers(),
            json=self._record_payload(
                audience_challenge,
                payload=wrong_audience_payload,
                audience="other-audience",
                signature=self._sign(wrong_audience_payload),
            ),
        )
        self.assertEqual(wrong_audience.status_code, 201, wrong_audience.text)
        self.assertEqual(wrong_audience.json()["result"], "denied")
        self.assertEqual(wrong_audience.json()["reason"], "wrong_audience")

        environment_challenge = self._issue_challenge()
        wrong_environment_payload = sdk_canonical_handshake_payload(
            contract_version=environment_challenge["contract_version"],
            challenge_id=environment_challenge["challenge_id"],
            nonce=environment_challenge["nonce"],
            audience=environment_challenge["audience"],
            organization_id=environment_challenge["organization_id"],
            environment_id="env_other",
            source_agent_id=environment_challenge["source_agent_id"],
            source_did=environment_challenge["source_did"],
            target_agent_id=environment_challenge["target_agent_id"],
            target_did=environment_challenge["target_did"],
            purpose=environment_challenge["purpose"],
            threshold_type=environment_challenge["threshold_type"],
            target_type=environment_challenge["target_type"],
            target_id=environment_challenge["target_id"],
            expires_at=environment_challenge["expires_at"],
        )
        wrong_environment = self.client.post(
            "/api/v1/trust/handshakes/record",
            headers=self._headers(),
            json=self._record_payload(
                environment_challenge,
                payload=wrong_environment_payload,
                environment_id="env_other",
                signature=self._sign(wrong_environment_payload),
            ),
        )
        self.assertEqual(wrong_environment.status_code, 201, wrong_environment.text)
        self.assertEqual(wrong_environment.json()["result"], "denied")
        self.assertEqual(wrong_environment.json()["reason"], "wrong_environment")

    def test_product_challenge_uses_sdk_canonical_contract(self) -> None:
        challenge = self._issue_challenge()

        sdk_payload = sdk_canonical_handshake_payload(
            contract_version=CANONICAL_HANDSHAKE_CONTRACT_VERSION,
            challenge_id=challenge["challenge_id"],
            nonce=challenge["nonce"],
            audience=challenge["audience"],
            organization_id=challenge["organization_id"],
            environment_id=challenge["environment_id"],
            source_agent_id=challenge["source_agent_id"],
            source_did=challenge["source_did"],
            target_agent_id=challenge["target_agent_id"],
            target_did=challenge["target_did"],
            purpose=challenge["purpose"],
            threshold_type=challenge["threshold_type"],
            target_type=challenge["target_type"],
            target_id=challenge["target_id"],
            expires_at=challenge["expires_at"],
        )

        self.assertEqual(challenge["contract_version"], CANONICAL_HANDSHAKE_CONTRACT_VERSION)
        self.assertEqual(challenge["canonical_payload"], sdk_payload)

        response = self.client.post(
            "/api/v1/trust/handshakes/record",
            headers=self._headers(),
            json=self._record_payload(challenge, payload=sdk_payload),
        )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["result"], "allowed")
        self.assertEqual(
            response.json()["metadata"]["handshake_contract"]["contract_version"],
            CANONICAL_HANDSHAKE_CONTRACT_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
