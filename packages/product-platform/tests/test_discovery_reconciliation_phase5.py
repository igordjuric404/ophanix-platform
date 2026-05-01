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


class DiscoveryReconciliationPhase5ApiTests(unittest.TestCase):
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
            discovery.persist_raw_findings(
                self.run["id"],
                [
                    _raw_agent("fp_critical", "Critical Shadow", owner=None, source="/repo/critical.yaml"),
                    _raw_agent("fp_owned", "Owned Shadow", owner="team-owned", source="/repo/owned.yaml"),
                    _raw_agent("fp_registered", "Registered Worker", owner="team-registry", source="/repo/registered.yaml"),
                    _raw_agent("fp_suppressed", "Suppressed Worker", owner=None, source="/repo/suppressed.yaml"),
                ],
            )
            repository = DiscoveryFindingRepository(connection, "org_default", "env_default")
            normalized = repository.reconcile_run(self.run["id"])
            by_fingerprint = {row["fingerprint"]: row for row in normalized}
            for row in normalized:
                repository.score_finding(row["id"])
            _insert_agent(connection, "agent_filter_registered", "Registered Worker")
            repository.update_governance_state(
                by_fingerprint["fp_registered"]["id"],
                status="registered",
                owner_hint="team-registry",
                registry_agent_id="agent_filter_registered",
            )
            repository.suppress(
                by_fingerprint["fp_suppressed"]["id"],
                reason="accepted test finding",
                expires_at=None,
                actor_id="user_admin",
            )
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

    def test_api_list_filters_findings_for_triage_views(self) -> None:
        critical = self.client.get(
            "/api/v1/discovery/findings",
            headers=self._headers(),
            params={"risk_level": "critical"},
        )
        owned = self.client.get(
            "/api/v1/discovery/findings",
            headers=self._headers(),
            params={"owner": "team-owned", "source": "owned.yaml"},
        )
        matched = self.client.get(
            "/api/v1/discovery/findings",
            headers=self._headers(),
            params={"registry_match": "matched"},
        )
        default_list = self.client.get("/api/v1/discovery/findings", headers=self._headers())
        suppressed = self.client.get(
            "/api/v1/discovery/findings",
            headers=self._headers(),
            params={"status": "suppressed", "include_suppressed": "true"},
        )

        self.assertEqual(critical.status_code, 200)
        self.assertEqual([finding["fingerprint"] for finding in critical.json()], ["fp_critical"])
        self.assertEqual(owned.status_code, 200)
        self.assertEqual([finding["fingerprint"] for finding in owned.json()], ["fp_owned"])
        self.assertEqual(matched.status_code, 200)
        self.assertEqual([finding["fingerprint"] for finding in matched.json()], ["fp_registered"])
        self.assertNotIn("fp_suppressed", {finding["fingerprint"] for finding in default_list.json()})
        self.assertEqual(suppressed.status_code, 200)
        self.assertEqual([finding["fingerprint"] for finding in suppressed.json()], ["fp_suppressed"])


def _raw_agent(
    fingerprint: str,
    name: str,
    *,
    owner: str | None,
    source: str,
) -> dict:
    payload = {
        "fingerprint": fingerprint,
        "name": name,
        "agent_type": "crewai",
        "description": "discovered in config",
        "owner": owner,
        "confidence": 0.95,
        "merge_keys": {"config_path": source},
        "first_seen_at": "2026-04-30T10:00:00+00:00",
        "last_seen_at": "2026-04-30T10:00:00+00:00",
        "evidence": [
            {
                "scanner": "config",
                "basis": "config_file",
                "source": source,
                "detail": "Agent config file",
                "confidence": 0.95,
                "timestamp": "2026-04-30T10:00:00+00:00",
            }
        ],
    }
    return json.loads(json.dumps(payload))


def _insert_agent(connection, agent_id: str, name: str) -> None:
    now = "2026-04-30T10:00:00+00:00"
    connection.execute(
        """
        INSERT INTO agents (
            id, organization_id, environment_id, name, description, framework,
            runtime_type, endpoint_url, owner_user_id, sponsor_user_id, status,
            created_at, updated_at
        )
        VALUES (?, 'org_default', 'env_default', ?, '', 'crewai', 'service',
            NULL, 'team-registry', 'sponsor_1', 'active', ?, ?)
        """,
        (agent_id, name, now, now),
    )


if __name__ == "__main__":
    unittest.main()
