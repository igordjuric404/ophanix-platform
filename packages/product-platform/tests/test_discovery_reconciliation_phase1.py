from __future__ import annotations

import json
import unittest

from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.discovery.findings import DiscoveryFindingRepository
from product_platform.discovery.models import DiscoveryTargetCreateRequest
from product_platform.discovery.repository import DiscoveryRepository


class DiscoveryReconciliationPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            self.discovery = DiscoveryRepository(connection, "org_default", "env_default")
            self.target = self.discovery.create_target(
                DiscoveryTargetCreateRequest(
                    scanner_type="process",
                    target_type="host",
                    target_value="localhost",
                    config_json={},
                )
            )
            self.run = self.discovery.create_run(self.target)

    def _persist_raw(self, payloads: list[dict]) -> None:
        with self.database.transaction() as connection:
            discovery = DiscoveryRepository(connection, "org_default", "env_default")
            discovery.persist_raw_findings(self.run["id"], payloads)

    def test_unit_same_fingerprint_updates_existing_finding(self) -> None:
        first_payload = _raw_agent("fp_same", "CrewAI Worker", owner="team-a")
        second_payload = _raw_agent("fp_same", "CrewAI Worker Renamed", owner="team-b")
        self._persist_raw([first_payload])
        with self.database.transaction() as connection:
            repository = DiscoveryFindingRepository(connection, "org_default", "env_default")
            first = repository.reconcile_run(self.run["id"])[0]

        self._persist_raw([second_payload])
        with self.database.transaction() as connection:
            repository = DiscoveryFindingRepository(connection, "org_default", "env_default")
            second = repository.reconcile_run(self.run["id"])[0]
            rows = repository.list_findings()

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(second["detected_name"], "CrewAI Worker Renamed")
        self.assertEqual(second["owner_hint"], "team-b")
        self.assertEqual(first["first_seen_at"], second["first_seen_at"])

    def test_integration_evidence_is_stored_for_finding(self) -> None:
        self._persist_raw([_raw_agent("fp_evidence", "Config Agent")])

        with self.database.transaction() as connection:
            repository = DiscoveryFindingRepository(connection, "org_default", "env_default")
            finding = repository.reconcile_run(self.run["id"])[0]
            evidence = repository.list_evidence(finding["id"])

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["run_id"], self.run["id"])
        self.assertEqual(evidence[0]["evidence_type"], "config_file")
        self.assertEqual(evidence[0]["evidence_value"], "/repo/agentmesh.yaml")

    def test_unit_missing_owner_results_in_owner_hint_null(self) -> None:
        self._persist_raw([_raw_agent("fp_no_owner", "Ownerless Agent", owner=None)])

        with self.database.transaction() as connection:
            repository = DiscoveryFindingRepository(connection, "org_default", "env_default")
            finding = repository.reconcile_run(self.run["id"])[0]

        self.assertIsNone(finding["owner_hint"])


def _raw_agent(fingerprint: str, name: str, owner: str | None = None) -> dict:
    payload = {
        "fingerprint": fingerprint,
        "name": name,
        "agent_type": "crewai",
        "description": "discovered in config",
        "owner": owner,
        "confidence": 0.95,
        "merge_keys": {"config_path": "/repo/agentmesh.yaml"},
        "tags": {"root": "/repo"},
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


if __name__ == "__main__":
    unittest.main()
