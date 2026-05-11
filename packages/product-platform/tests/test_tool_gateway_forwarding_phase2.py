from __future__ import annotations

import unittest

from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.auth import GatewayPrincipal
from product_platform.tool_gateway.decision import ToolPolicyDecisionResult
from product_platform.tool_gateway.invocation import (
    HttpToolInvocationExecutor,
    ToolExecutionError,
    build_upstream_url,
)
from product_platform.tool_gateway.models import (
    ToolDefinitionCreateRequest,
    ToolUpstreamTargetCreateRequest,
)
from product_platform.tool_gateway.repository import ToolRegistryRepository


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
}


class FakeHTTPResponse:
    status_code = 200
    headers = {"content-type": "application/json"}
    text = "{}"

    def json(self):
        return {"ok": True}


class RecordingHTTPClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return FakeHTTPResponse()


class ToolGatewayForwardingPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
            connection.execute(
                """
                INSERT OR IGNORE INTO environments
                    (id, organization_id, name, slug, type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "env_forward_other",
                    DEMO_ORG_ID,
                    "Forward Other",
                    "forward-other",
                    "development",
                    "2026-05-01T00:00:00+00:00",
                    "2026-05-01T00:00:00+00:00",
                ),
            )
        self.connection = self.database.connect()
        self.repository = ToolRegistryRepository(self.connection, DEMO_ORG_ID, DEMO_ENV_ID)

    def _create_active_tool(self, repository: ToolRegistryRepository, *, name: str = "claims.lookup") -> dict:
        tool = repository.create_tool(
            ToolDefinitionCreateRequest(
                name=name,
                display_name="Claims Lookup",
                owner_team="claims-platform",
                required_scope=f"{name}:read",
                input_schema_json=VALID_INPUT_SCHEMA,
            ),
            created_by=DEMO_ADMIN_USER_ID,
        )
        return dict(repository.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID))

    def _target_body(self, *, base_url: str = "https://claims.internal.example") -> ToolUpstreamTargetCreateRequest:
        return ToolUpstreamTargetCreateRequest(
            base_url=base_url,
            path_template="/v1/claims/{claim_id}",
            method="POST",
            auth_mode="none",
            timeout_ms=1200,
            health_url=f"{base_url}/health",
        )

    def _decision(self, *, tool_id: str) -> ToolPolicyDecisionResult:
        return ToolPolicyDecisionResult(
            id="decision_forward_phase2",
            organization_id=DEMO_ORG_ID,
            environment_id=DEMO_ENV_ID,
            agent_id="agent_forward",
            tool_id=tool_id,
            permission_id="agtperm_forward",
            decision="allow",
            reason_code="allowed",
            reason_message="Tool call is allowed.",
            matched_policy_id=None,
            request_id="req-forward-target",
            correlation_id="corr-forward-target",
            payload_summary={"claim_id": "claim_123"},
            created_at="2026-05-01T00:00:00+00:00",
        )

    def _principal(self) -> GatewayPrincipal:
        return GatewayPrincipal(
            organization_id=DEMO_ORG_ID,
            environment_id=DEMO_ENV_ID,
            agent_id="agent_forward",
            credential_id="cred_forward",
            scopes=["claims.lookup:read"],
            request_id="req-forward-target",
        )

    def test_unit_target_url_is_built_from_path_template(self) -> None:
        url = build_upstream_url(
            {
                "base_url": "https://claims.internal.example",
                "path_template": "/v1/claims/{claim_id}/notes/{note_id}",
            },
            {"claim_id": "ABC 123", "note_id": "n/1"},
        )

        self.assertEqual(
            url,
            "https://claims.internal.example/v1/claims/ABC%20123/notes/n%2F1",
        )

    def test_unit_missing_target_returns_controlled_error(self) -> None:
        with self.database.transaction():
            tool = self._create_active_tool(self.repository)
            with self.assertRaises(ToolExecutionError) as context:
                HttpToolInvocationExecutor(self.repository).execute(
                    tool=tool,
                    payload={"claim_id": "claim_123"},
                    decision=self._decision(tool_id=tool["id"]),
                    principal=self._principal(),
                )

        self.assertEqual(context.exception.code, "upstream_target_missing")

    def test_unit_unhealthy_target_is_blocked_when_fail_closed_enabled(self) -> None:
        with self.database.transaction():
            tool = self._create_active_tool(self.repository)
            target = self.repository.create_upstream_target(tool["id"], self._target_body())
            self.repository.update_upstream_target(
                target["id"],
                ToolUpstreamTargetCreateRequest(
                    base_url="https://claims.internal.example",
                    path_template="/v1/claims/{claim_id}",
                    method="POST",
                    auth_mode="none",
                    timeout_ms=1200,
                    status="unhealthy",
                    health_url="https://claims.internal.example/health",
                ),
            )
            with self.assertRaises(ToolExecutionError) as context:
                HttpToolInvocationExecutor(self.repository).execute(
                    tool=tool,
                    payload={"claim_id": "claim_123"},
                    decision=self._decision(tool_id=tool["id"]),
                    principal=self._principal(),
                )

        self.assertEqual(context.exception.code, "upstream_target_unhealthy")
        self.assertEqual(context.exception.status_code, 503)

    def test_integration_environment_specific_target_is_selected(self) -> None:
        with self.database.transaction():
            default_tool = self._create_active_tool(self.repository)
            self.repository.create_upstream_target(
                default_tool["id"],
                self._target_body(base_url="https://default.internal.example"),
            )
            other_repository = ToolRegistryRepository(
                self.connection,
                DEMO_ORG_ID,
                "env_forward_other",
            )
            other_tool = self._create_active_tool(other_repository)
            other_repository.create_upstream_target(
                other_tool["id"],
                self._target_body(base_url="https://other.internal.example"),
            )

        default_target = self.repository.resolve_upstream_target_by_tool_name("claims.lookup")
        other_target = ToolRegistryRepository(
            self.connection,
            DEMO_ORG_ID,
            "env_forward_other",
        ).resolve_upstream_target_by_tool_name("claims.lookup")

        self.assertEqual(default_target["base_url"], "https://default.internal.example")
        self.assertEqual(other_target["base_url"], "https://other.internal.example")

    def test_unit_get_target_uses_query_params_instead_of_json_body(self) -> None:
        with self.database.transaction():
            tool = self._create_active_tool(self.repository)
            self.repository.create_upstream_target(
                tool["id"],
                ToolUpstreamTargetCreateRequest(
                    base_url="https://claims.internal.example",
                    path_template="/v1/claims",
                    method="GET",
                    auth_mode="none",
                    timeout_ms=1200,
                    health_url="https://claims.internal.example/health",
                ),
            )
            http_client = RecordingHTTPClient()
            HttpToolInvocationExecutor(self.repository, http_client=http_client).execute(
                tool=tool,
                payload={"claim_id": "claim_123"},
                decision=self._decision(tool_id=tool["id"]),
                principal=self._principal(),
            )

        self.assertEqual(http_client.calls[0]["method"], "GET")
        self.assertNotIn("json", http_client.calls[0])
        self.assertEqual(http_client.calls[0]["params"], {"claim_id": "claim_123"})


if __name__ == "__main__":
    unittest.main()
