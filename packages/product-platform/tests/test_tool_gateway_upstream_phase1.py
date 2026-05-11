from __future__ import annotations

import os
import socket
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from product_platform.db.seed import DEMO_ADMIN_USER_ID, DEMO_ENV_ID, DEMO_ORG_ID, seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.models import (
    ToolDefinitionCreateRequest,
    ToolUpstreamTargetCreateRequest,
)
from product_platform.tool_gateway.repository import (
    DuplicateToolUpstreamTargetError,
    ToolRegistryRepository,
)


VALID_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_id": {"type": "string"}},
    "required": ["claim_id"],
}


class ToolGatewayUpstreamPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.connection = self.database.connect()
        self.repository = ToolRegistryRepository(self.connection, DEMO_ORG_ID, DEMO_ENV_ID)

    def _create_active_tool(self, *, name: str = "claims.lookup") -> str:
        tool = self.repository.create_tool(
            ToolDefinitionCreateRequest(
                name=name,
                display_name="Claims Lookup",
                owner_team="claims-platform",
                required_scope=f"{name}:read",
                input_schema_json=VALID_INPUT_SCHEMA,
            ),
            created_by=DEMO_ADMIN_USER_ID,
        )
        self.repository.activate_tool(tool["id"], actor_id=DEMO_ADMIN_USER_ID)
        return tool["id"]

    def _target_body(self) -> ToolUpstreamTargetCreateRequest:
        return ToolUpstreamTargetCreateRequest(
            base_url="https://claims.internal.example",
            path_template="/v1/claims/{claim_id}",
            method="POST",
            auth_mode="none",
            timeout_ms=2_500,
            health_url="https://claims.internal.example/health",
            expected_status=204,
        )

    def test_integration_creates_target_for_tool_with_health_check(self) -> None:
        with self.database.transaction():
            tool_id = self._create_active_tool()
            target = self.repository.create_upstream_target(tool_id, self._target_body())

        self.assertTrue(target["id"].startswith("target_"))
        self.assertEqual(target["tool_id"], tool_id)
        self.assertEqual(target["tool_name"], "claims.lookup")
        self.assertEqual(target["base_url"], "https://claims.internal.example")
        self.assertEqual(target["method"], "POST")
        self.assertEqual(target["status"], "configured")

        health = self.repository.get_upstream_health(target["id"])
        self.assertIsNotNone(health)
        self.assertEqual(health["health_url"], "https://claims.internal.example/health")
        self.assertEqual(health["expected_status"], 204)
        self.assertEqual(health["enabled"], 1)

    def test_integration_duplicate_active_target_is_rejected(self) -> None:
        with self.database.transaction():
            tool_id = self._create_active_tool()
            self.repository.create_upstream_target(tool_id, self._target_body())
            with self.assertRaisesRegex(DuplicateToolUpstreamTargetError, "already has"):
                self.repository.create_upstream_target(tool_id, self._target_body())

    def test_unit_invalid_url_is_rejected(self) -> None:
        with self.assertRaises(ValidationError) as context:
            ToolUpstreamTargetCreateRequest(
                base_url="file:///tmp/claims.sock",
                path_template="/claims",
            )

        self.assertIn("absolute http or https URL", str(context.exception))

    def test_unit_secret_backed_auth_modes_require_secret_reference(self) -> None:
        with self.assertRaises(ValidationError) as context:
            ToolUpstreamTargetCreateRequest(
                base_url="https://claims.internal.example",
                path_template="/claims",
                auth_mode="bearer",
            )

        self.assertIn("secret_ref is required", str(context.exception))

        target = ToolUpstreamTargetCreateRequest(
            base_url="https://claims.internal.example",
            path_template="/claims",
            auth_mode="bearer",
            auth_config_json={"secret_ref": "secref_upstream_claims"},
        )
        self.assertEqual(target.auth_mode, "bearer")
        self.assertEqual(target.auth_config_json, {"secret_ref": "secref_upstream_claims"})

    def test_unit_auth_config_rejects_inline_secret_material(self) -> None:
        with self.assertRaises(ValidationError) as context:
            ToolUpstreamTargetCreateRequest(
                base_url="https://claims.internal.example",
                path_template="/claims",
                auth_mode="bearer",
                auth_config_json={"secret_ref": "Bearer raw-token"},
            )

        self.assertIn("opaque secret reference", str(context.exception))

    def test_unit_auth_config_rejects_invalid_header_prefix(self) -> None:
        with self.assertRaises(ValidationError) as context:
            ToolUpstreamTargetCreateRequest(
                base_url="https://claims.internal.example",
                path_template="/claims",
                auth_mode="api_key",
                auth_config_json={
                    "secret_ref": "secref_upstream_claims",
                    "header_prefix": "Token value",
                },
            )

        self.assertIn("authentication scheme token", str(context.exception))

    def test_unit_private_ip_upstream_url_is_rejected(self) -> None:
        with self.assertRaises(ValidationError) as context:
            ToolUpstreamTargetCreateRequest(
                base_url="https://169.254.169.254",
                path_template="/claims",
            )

        self.assertIn("must not target private", str(context.exception))

    def test_unit_loopback_upstream_url_is_rejected(self) -> None:
        with self.assertRaises(ValidationError) as context:
            ToolUpstreamTargetCreateRequest(
                base_url="https://127.0.0.1:9000",
                path_template="/claims",
            )

        self.assertIn("loopback", str(context.exception))

    def test_unit_dns_resolved_private_upstream_url_is_rejected(self) -> None:
        with patch(
            "product_platform.tool_gateway.models.socket.getaddrinfo",
            return_value=[
                (
                    0,
                    0,
                    0,
                    "",
                    ("10.0.0.25", 443),
                )
            ],
        ):
            with self.assertRaises(ValidationError) as context:
                ToolUpstreamTargetCreateRequest(
                    base_url="https://claims.example.com",
                    path_template="/claims",
                )

        self.assertIn("private", str(context.exception))

    def test_unit_unresolved_dns_upstream_url_fails_closed_outside_local_envs(self) -> None:
        with patch.dict(os.environ, {"OPHANIX_ENVIRONMENT": "production"}, clear=False):
            with patch(
                "product_platform.tool_gateway.models.socket.getaddrinfo",
                side_effect=socket.gaierror("unresolved"),
            ):
                with self.assertRaises(ValidationError) as context:
                    ToolUpstreamTargetCreateRequest(
                        base_url="https://unresolved.example.com",
                        path_template="/claims",
                    )

        self.assertIn("private", str(context.exception))

    def test_unit_unresolved_host_bypass_is_ignored_outside_local_envs(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPHANIX_ENVIRONMENT": "production",
                "OPHANIX_ALLOW_UNRESOLVED_UPSTREAM_HOSTS": "true",
            },
            clear=False,
        ):
            with patch(
                "product_platform.tool_gateway.models.socket.getaddrinfo",
                side_effect=socket.gaierror("unresolved"),
            ):
                with self.assertRaises(ValidationError) as context:
                    ToolUpstreamTargetCreateRequest(
                        base_url="https://unresolved.example.com",
                        path_template="/claims",
                    )

        self.assertIn("private", str(context.exception))

    def test_unit_upstream_host_allowlist_rejects_unapproved_host(self) -> None:
        with patch.dict(
            os.environ,
            {"OPHANIX_TOOL_GATEWAY_UPSTREAM_HOST_ALLOWLIST": "*.approved.example"},
            clear=False,
        ):
            with self.assertRaises(ValidationError) as context:
                ToolUpstreamTargetCreateRequest(
                    base_url="https://claims.example.com",
                    path_template="/claims",
                )

        self.assertIn("allowlist", str(context.exception))

    def test_unit_upstream_host_allowlist_accepts_wildcard_match(self) -> None:
        with patch.dict(
            os.environ,
            {"OPHANIX_TOOL_GATEWAY_UPSTREAM_HOST_ALLOWLIST": "*.internal.example"},
            clear=False,
        ):
            target = ToolUpstreamTargetCreateRequest(
                base_url="https://claims.internal.example",
                path_template="/claims",
            )

        self.assertEqual(target.base_url, "https://claims.internal.example")

    def test_unit_plain_http_upstream_url_is_rejected_even_for_localhost(self) -> None:
        with self.assertRaises(ValidationError) as context:
            ToolUpstreamTargetCreateRequest(
                base_url="http://localhost:9000",
                path_template="/claims",
            )

        self.assertIn("must use https", str(context.exception))

    def test_repository_resolves_target_by_active_tool_name(self) -> None:
        with self.database.transaction():
            tool_id = self._create_active_tool(name="claims.lookup")
            target = self.repository.create_upstream_target(tool_id, self._target_body())

        resolved = self.repository.resolve_upstream_target_by_tool_name("claims.lookup")
        missing = self.repository.resolve_upstream_target_by_tool_name("claims.missing")

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["id"], target["id"])
        self.assertIsNone(missing)


if __name__ == "__main__":
    unittest.main()
