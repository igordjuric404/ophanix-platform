from __future__ import annotations

import unittest

from agentmesh.trust.cards import CardRegistry, TrustedAgentCard

from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.trust.cards import (
    TrustCardIssuer,
    TrustCardRepository,
    trust_card_response,
)
from product_platform.trust.models import TrustCardIssueRequest
from product_platform.trust.repository import TrustRepository


class TrustCardManagementPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self._insert_agent_identity_capability(connection)
            TrustRepository(connection, "org_default", "env_default").upsert_score(
                agent_id="agent_card",
                score=735,
                dimensions={"policy_compliance": {"score": 735, "signal_count": 1}},
            )

    def _insert_agent_identity_capability(self, connection) -> None:
        now = "2026-05-01T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, owner_user_id, sponsor_user_id, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "agent_card",
                "org_default",
                "env_default",
                "Card Agent",
                "Handles signed card tests",
                "langgraph",
                "service",
                "owner",
                "sponsor",
                "active",
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO agent_identities (
                id, agent_id, did, public_key_fingerprint, key_type,
                identity_status, bootstrap_material_json, bootstrap_retrieved_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "ident_card",
                "agent_card",
                "did:mesh:cardagent",
                "fingerprint_card",
                "ed25519",
                "active",
                None,
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO agent_capabilities (
                id, agent_id, capability_name, resource_type, status,
                requested_by, approved_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "cap_card",
                "agent_card",
                "claims:read",
                "claim",
                "approved",
                "owner",
                "approver",
                now,
            ),
        )

    def test_card_payload_includes_did_and_capabilities(self) -> None:
        with self.database.transaction() as connection:
            row = TrustCardIssuer(connection, "org_default", "env_default").issue(
                TrustCardIssueRequest(agent_id="agent_card")
            )
            payload = trust_card_response(row)

            self.assertEqual(payload.card["agent_did"], "did:mesh:cardagent")
            self.assertEqual(payload.card["capabilities"], ["claims:read"])
            self.assertEqual(payload.card["metadata"]["trust_score"], 735)
            self.assertEqual(payload.card["metadata"]["trust_tier"], "trusted")

    def test_signature_verifies_using_card_registry(self) -> None:
        with self.database.transaction() as connection:
            row = TrustCardIssuer(connection, "org_default", "env_default").issue(
                TrustCardIssueRequest(agent_id="agent_card")
            )
            card = TrustedAgentCard.from_dict(trust_card_response(row).card)
            registry = CardRegistry()

            self.assertEqual(registry.register(card), True)
            self.assertEqual(registry.is_verified("did:mesh:cardagent"), True)

    def test_issued_card_is_persisted(self) -> None:
        with self.database.transaction() as connection:
            row = TrustCardIssuer(connection, "org_default", "env_default").issue(
                TrustCardIssueRequest(agent_id="agent_card", issuer="ophanix-demo")
            )
            repository = TrustCardRepository(connection, "org_default", "env_default")
            cards = repository.list_cards(agent_id="agent_card")

            self.assertTrue(row["id"].startswith("tcard_"))
            self.assertEqual(len(cards), 1)
            self.assertEqual(cards[0]["issuer"], "ophanix-demo")
            self.assertEqual(cards[0]["status"], "active")


if __name__ == "__main__":
    unittest.main()
