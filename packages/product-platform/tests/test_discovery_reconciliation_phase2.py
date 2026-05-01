from __future__ import annotations

import json
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.discovery.findings import DiscoveryFindingRepository
from product_platform.discovery.models import DiscoveryTargetCreateRequest
from product_platform.discovery.repository import DiscoveryRepository


class DiscoveryReconciliationPhase2Tests(unittest.TestCase):
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
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
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

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
        }

    def _create_finding(self, payload: dict) -> str:
        with self.database.transaction() as connection:
            discovery = DiscoveryRepository(connection, "org_default", "env_default")
            discovery.persist_raw_findings(self.run["id"], [payload])
            repository = DiscoveryFindingRepository(connection, "org_default", "env_default")
            return repository.reconcile_run(self.run["id"])[0]["id"]

    def test_unit_unregistered_no_owner_finding_is_high_risk(self) -> None:
        finding_id = self._create_finding(_raw_agent("fp_high", "CrewAI Worker", owner=None))

        with self.database.transaction() as connection:
            repository = DiscoveryFindingRepository(connection, "org_default", "env_default")
            scored = repository.score_finding(finding_id)

        self.assertGreaterEqual(scored["risk_score"], 50)
        self.assertIn(scored["risk_level"], {"high", "critical"})
        self.assertIn("No assigned owner", json.loads(scored["risk_factors_json"]))

    def test_unit_registered_finding_has_lower_risk(self) -> None:
        finding_id = self._create_finding(
            _raw_agent("fp_registered", "Registered Worker", owner="team-a", did="did:mesh:abc")
        )

        with self.database.transaction() as connection:
            repository = DiscoveryFindingRepository(connection, "org_default", "env_default")
            high = repository.score_finding(finding_id)
            registered = repository.update_governance_state(
                finding_id,
                status="registered",
                owner_hint="team-a",
                registry_agent_id=None,
            )

        self.assertLess(registered["risk_score"], high["risk_score"])
        self.assertIn(registered["risk_level"], {"info", "low", "medium"})

    def test_api_finding_detail_includes_risk_factors(self) -> None:
        finding_id = self._create_finding(_raw_agent("fp_api", "API Visible Worker", owner=None))
        with self.database.transaction() as connection:
            DiscoveryFindingRepository(connection, "org_default", "env_default").score_finding(
                finding_id
            )

        response = self.client.get(
            f"/api/v1/discovery/findings/{finding_id}",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["risk_score"], 50)
        self.assertIn("No assigned owner", payload["risk_factors"])


def _raw_agent(
    fingerprint: str,
    name: str,
    *,
    owner: str | None,
    did: str | None = None,
) -> dict:
    payload = {
        "fingerprint": fingerprint,
        "name": name,
        "agent_type": "crewai",
        "description": "discovered in config",
        "owner": owner,
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


if __name__ == "__main__":
    unittest.main()
