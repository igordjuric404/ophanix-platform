from __future__ import annotations

import unittest

from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.trust.handshakes import TrustThresholdResolver
from product_platform.trust.models import (
    TrustThresholdCreateRequest,
    TrustThresholdResolveRequest,
)
from product_platform.trust.repository import TrustRepository


class HandshakesThresholdsPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)

    def test_tool_specific_threshold_overrides_default(self) -> None:
        with self.database.transaction() as connection:
            repository = TrustRepository(connection, "org_default", "env_default")
            repository.seed_default_thresholds()
            specific = repository.create_threshold(
                TrustThresholdCreateRequest(
                    threshold_type="mcp_tool_use",
                    target_type="mcp_tool",
                    target_id="claims.read",
                    min_score=820,
                    required_tier="trusted",
                )
            )

            resolution = TrustThresholdResolver(repository).resolve(
                TrustThresholdResolveRequest(
                    threshold_type="mcp_tool_use",
                    target_type="mcp_tool",
                    target_id="claims.read",
                )
            )

            self.assertEqual(resolution.threshold_id, specific["id"])
            self.assertEqual(resolution.min_score, 820)
            self.assertEqual(resolution.required_tier, "trusted")
            self.assertEqual(resolution.reason, "target_threshold")

    def test_disabled_threshold_is_ignored(self) -> None:
        with self.database.transaction() as connection:
            repository = TrustRepository(connection, "org_default", "env_default")
            repository.seed_default_thresholds()
            repository.create_threshold(
                TrustThresholdCreateRequest(
                    threshold_type="mcp_tool_use",
                    target_type="mcp_tool",
                    target_id="claims.read",
                    min_score=950,
                    required_tier="verified_partner",
                    enabled=False,
                )
            )

            resolution = TrustThresholdResolver(repository).resolve(
                TrustThresholdResolveRequest(
                    threshold_type="mcp_tool_use",
                    target_type="mcp_tool",
                    target_id="claims.read",
                )
            )

            self.assertEqual(resolution.min_score, 650)
            self.assertEqual(resolution.target_type, "environment")
            self.assertEqual(resolution.reason, "environment_default")

    def test_missing_protected_threshold_fails_closed(self) -> None:
        with self.database.transaction() as connection:
            repository = TrustRepository(connection, "org_default", "env_default")

            resolution = TrustThresholdResolver(repository).resolve(
                TrustThresholdResolveRequest(
                    threshold_type="protocol_bridge_use",
                    target_type="bridge",
                    target_id="bridge_alpha",
                )
            )

            self.assertEqual(resolution.resolved, False)
            self.assertEqual(resolution.fail_closed, True)
            self.assertEqual(resolution.reason, "missing_required_threshold")


if __name__ == "__main__":
    unittest.main()
