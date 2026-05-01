from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.api.tenancy import Environment, TenantStore
from product_platform.audit.events import agent_lifecycle_event
from product_platform.audit.store import AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database


class AgentInventoryPhase3ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            connection.execute(
                """
                INSERT INTO environments
                    (id, organization_id, name, slug, type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "env_other",
                    "org_default",
                    "Other",
                    "other",
                    "development",
                    "2026-04-30T00:00:00+00:00",
                    "2026-04-30T00:00:00+00:00",
                ),
            )
            self._seed_agent(connection, "agent_detail", "env_default")
            self._seed_agent(connection, "agent_other", "env_other")
            AuditEventRepository(connection).insert(
                agent_lifecycle_event(
                    organization_id="org_default",
                    environment_id="env_default",
                    agent_id="agent_detail",
                    lifecycle_state="active",
                    actor_id="user_admin",
                )
            )
        tenant_store = TenantStore(
            environments=[
                Environment(
                    id="env_default",
                    organization_id="org_default",
                    name="Development",
                    slug="development",
                    type="development",
                    created_at="2026-04-30T00:00:00+00:00",
                ),
                Environment(
                    id="env_other",
                    organization_id="org_default",
                    name="Other",
                    slug="other",
                    type="development",
                    created_at="2026-04-30T00:00:00+00:00",
                ),
            ]
        )
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=["viewer@example.com"],
                session_secret="test-secret",
            ),
            tenant_store=tenant_store,
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "viewer@example.com", "roles": ["Viewer"]},
        )
        self.assertEqual(login.status_code, 200)
        self.token = login.json()["access_token"]
        admin = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "viewer@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(admin.status_code, 200)
        self.admin_token = admin.json()["access_token"]

    def _headers(self, environment_id: str = "env_default") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": environment_id,
        }

    def _seed_agent(self, connection, agent_id: str, environment_id: str) -> None:
        now = "2026-04-30T00:00:00+00:00"
        connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, endpoint_url, owner_user_id, sponsor_user_id, status,
                last_heartbeat_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                "org_default",
                environment_id,
                "Detail Agent",
                "Detailed agent",
                "langgraph",
                "service",
                "https://agents.example.test/detail",
                "owner_1",
                "sponsor_1",
                "active",
                "2026-04-30T11:00:00+00:00",
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO agent_identities
                (id, agent_id, did, public_key_fingerprint, key_type, identity_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (f"ident_{agent_id}", agent_id, f"did:mesh:{agent_id}", "abc123", "ed25519", "active", now),
        )
        connection.execute(
            """
            INSERT INTO agent_capabilities
                (id, agent_id, capability_name, resource_type, status, requested_by, approved_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (f"cap_{agent_id}", agent_id, "claims:read", "claim", "approved", "owner_1", "owner_1", now),
        )
        connection.execute(
            """
            INSERT INTO agent_protocols (id, agent_id, protocol, endpoint, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (f"proto_{agent_id}", agent_id, "http", "https://agents.example.test/detail", "active"),
        )
        connection.execute(
            """
            INSERT INTO agent_heartbeats (id, agent_id, observed_at, status, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (f"hb_{agent_id}", agent_id, "2026-04-30T11:00:00+00:00", "healthy", '{"latency_ms": 12}'),
        )
        for index, state in enumerate(["draft", "pending_approval", "active"]):
            connection.execute(
                """
                INSERT INTO agent_lifecycle_events
                    (id, agent_id, previous_state, next_state, actor_id, reason, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"life_{agent_id}_{index}",
                    agent_id,
                    None if index == 0 else "previous",
                    state,
                    "user_admin",
                    state,
                    "{}",
                    f"2026-04-30T0{index}:00:00+00:00",
                ),
            )

    def test_detail_returns_expected_sections(self) -> None:
        response = self.client.get("/api/v1/agents/agent_detail", headers=self._headers())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["id"], "agent_detail")
        self.assertEqual(payload["identity"]["did"], "did:mesh:agent_detail")
        self.assertEqual(payload["capabilities"][0]["capability_name"], "claims:read")
        self.assertEqual(payload["protocols"][0]["protocol"], "http")
        self.assertEqual(payload["latest_heartbeat"]["status"], "healthy")
        self.assertEqual(payload["lifecycle_summary"]["current_state"], "active")

    def test_inaccessible_agent_is_hidden(self) -> None:
        response = self.client.get("/api/v1/agents/agent_other", headers=self._headers())

        self.assertEqual(response.status_code, 404)

    def test_timeline_returns_ordered_events(self) -> None:
        response = self.client.get(
            "/api/v1/agents/agent_detail/timeline",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload[0]["id"], "life_agent_detail_0")
        self.assertTrue(any(event["source"] == "audit" for event in payload))
        created = [event["created_at"] for event in payload]
        self.assertEqual(created, sorted(created))

    def test_patch_updates_editable_agent_fields(self) -> None:
        response = self.client.patch(
            "/api/v1/agents/agent_detail",
            headers={
                "Authorization": f"Bearer {self.admin_token}",
                "X-Environment-ID": "env_default",
            },
            json={"description": "Updated description", "owner_user_id": "owner_2"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["description"], "Updated description")
        self.assertEqual(response.json()["owner_user_id"], "owner_2")


if __name__ == "__main__":
    unittest.main()
