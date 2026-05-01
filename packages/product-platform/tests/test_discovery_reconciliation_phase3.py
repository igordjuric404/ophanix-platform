from __future__ import annotations

import json
import unittest

from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.discovery.findings import DiscoveryFindingRepository
from product_platform.discovery.models import DiscoveryTargetCreateRequest
from product_platform.discovery.repository import DiscoveryRepository


class DiscoveryReconciliationPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            discovery = DiscoveryRepository(connection, "org_default", "env_default")
            target = discovery.create_target(
                DiscoveryTargetCreateRequest(
                    scanner_type="process",
                    target_type="host",
                    target_value="localhost",
                    config_json={},
                )
            )
            self.run = discovery.create_run(target)

    def _create_finding(self, payload: dict) -> str:
        with self.database.transaction() as connection:
            discovery = DiscoveryRepository(connection, "org_default", "env_default")
            discovery.persist_raw_findings(self.run["id"], [payload])
            repository = DiscoveryFindingRepository(connection, "org_default", "env_default")
            return repository.reconcile_run(self.run["id"])[0]["id"]

    def test_integration_finding_with_matching_did_links_to_agent(self) -> None:
        finding_id = self._create_finding(
            _raw_agent("fp_did", "Matched Agent", did="did:mesh:matched")
        )
        with self.database.transaction() as connection:
            _insert_agent(connection, "agent_match", "Governed Agent", did="did:mesh:matched")
            repository = DiscoveryFindingRepository(connection, "org_default", "env_default")
            repository.reconcile_registry()
            finding = repository.get_finding(finding_id)

        self.assertEqual(finding["status"], "registered")
        self.assertEqual(finding["registry_agent_id"], "agent_match")

    def test_integration_unmatched_finding_is_shadow_candidate(self) -> None:
        finding_id = self._create_finding(_raw_agent("fp_shadow", "Unknown Agent"))
        with self.database.transaction() as connection:
            repository = DiscoveryFindingRepository(connection, "org_default", "env_default")
            repository.reconcile_registry()
            finding = repository.get_finding(finding_id)

        self.assertEqual(finding["status"], "shadow_candidate")
        self.assertIsNone(finding["registry_agent_id"])

    def test_unit_ambiguous_match_requires_manual_review(self) -> None:
        finding_id = self._create_finding(_raw_agent("fp_ambiguous", "Ambiguous Worker"))
        with self.database.transaction() as connection:
            _insert_agent(connection, "agent_ambiguous_a", "Ambiguous Worker A")
            _insert_agent(connection, "agent_ambiguous_b", "Ambiguous Worker B")
            repository = DiscoveryFindingRepository(connection, "org_default", "env_default")
            repository.reconcile_registry()
            finding = repository.get_finding(finding_id)

        self.assertEqual(finding["status"], "manual_review")
        self.assertIsNone(finding["registry_agent_id"])


def _raw_agent(fingerprint: str, name: str, did: str | None = None) -> dict:
    payload = {
        "fingerprint": fingerprint,
        "name": name,
        "agent_type": "crewai",
        "description": "discovered in config",
        "did": did,
        "confidence": 0.95,
        "merge_keys": {"config_path": "/repo/agentmesh.yaml"},
        "first_seen_at": "2026-04-30T10:00:00+00:00",
        "last_seen_at": "2026-04-30T10:00:00+00:00",
        "evidence": [
            {
                "scanner": "config",
                "basis": "config_file",
                "source": "/repo/agentmesh.yaml",
                "detail": "Agent config file",
                "raw_data": {"path": "/repo/agentmesh.yaml"},
                "confidence": 0.95,
                "timestamp": "2026-04-30T10:00:00+00:00",
            }
        ],
    }
    return json.loads(json.dumps(payload))


def _insert_agent(connection, agent_id: str, name: str, did: str | None = None) -> None:
    now = "2026-04-30T10:00:00+00:00"
    connection.execute(
        """
        INSERT INTO agents (
            id, organization_id, environment_id, name, description, framework,
            runtime_type, endpoint_url, owner_user_id, sponsor_user_id, status,
            created_at, updated_at
        )
        VALUES (?, 'org_default', 'env_default', ?, '', 'crewai', 'service',
            NULL, 'owner_1', 'sponsor_1', 'active', ?, ?)
        """,
        (agent_id, name, now, now),
    )
    if did is not None:
        connection.execute(
            """
            INSERT INTO agent_identities (
                id, agent_id, did, public_key_fingerprint, key_type,
                identity_status, created_at
            )
            VALUES (?, ?, ?, 'fp', 'ed25519', 'active', ?)
            """,
            (f"ident_{agent_id}", agent_id, did, now),
        )


if __name__ == "__main__":
    unittest.main()
