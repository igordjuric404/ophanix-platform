from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from product_platform.api.settings import Settings
from product_platform.db.migrator import MigrationRunner, connect_database


EXPECTED_MIGRATIONS = [
    "0001",
    "0002",
    "0003",
    "0004",
    "0005",
    "0006",
    "0007",
    "0008",
    "0009",
    "0010",
    "0011",
    "0012",
    "0013",
    "0014",
    "0015",
    "0016",
    "0017",
    "0018",
    "0019",
    "0020",
    "0021",
    "0022",
    "0023",
    "0024",
    "0025",
    "0026",
    "0027",
    "0028",
    "0029",
    "0030",
    "0031",
    "0032",
    "0033",
    "0034",
    "0035",
    "0036",
    "0037",
    "0038",
    "0039",
    "0040",
    "0041",
]


class DatabaseMigrationPhase1Tests(unittest.TestCase):
    def test_migration_applies_to_empty_database(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            connection.row_factory = sqlite3.Row
            runner = MigrationRunner(connection)

            applied = runner.apply_all()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(applied, EXPECTED_MIGRATIONS)
            self.assertIn("organizations", tables)
            self.assertIn("environments", tables)
            self.assertIn("api_keys", tables)
            self.assertIn("audit_events", tables)
            self.assertIn("agents", tables)
            self.assertIn("agent_lifecycle_events", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("credential_scopes", tables)
            self.assertIn("credential_rotations", tables)
            self.assertIn("credential_issuers", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("discovery_runs", tables)
            self.assertIn("discovery_raw_findings", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_evidence", tables)
            self.assertIn("discovery_suppressions", tables)
            self.assertIn("reconciliation_actions", tables)
            self.assertIn("policies", tables)
            self.assertIn("policy_versions", tables)
            self.assertIn("policy_imports", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policy_bindings", tables)
            self.assertIn("policy_exceptions", tables)
            self.assertIn("policy_rollout_events", tables)
            self.assertIn("trust_scores", tables)
            self.assertIn("trust_events", tables)
            self.assertIn("trust_rules", tables)
            self.assertIn("trust_recalculation_runs", tables)
            self.assertIn("trust_cards", tables)
            self.assertIn("trust_card_revocations", tables)
            self.assertIn("trust_thresholds", tables)
            self.assertIn("handshake_events", tables)
            self.assertIn("mesh_messages", tables)
            self.assertIn("mesh_handoffs", tables)
            self.assertIn("mesh_topology_snapshots", tables)
            self.assertIn("protocol_bridges", tables)
            self.assertIn("protocol_bridge_routes", tables)
            self.assertIn("protocol_bridge_health_checks", tables)
            self.assertIn("mcp_servers", tables)
            self.assertIn("mcp_tools", tables)
            self.assertIn("mcp_tool_versions", tables)
            self.assertIn("mcp_scan_runs", tables)
            self.assertIn("mcp_findings", tables)
            self.assertIn("mcp_scan_baselines", tables)
            self.assertIn("mcp_tool_calls", tables)
            self.assertIn("mcp_approvals", tables)
            self.assertIn("mcp_rate_limits", tables)
            self.assertIn("runtime_sessions", tables)
            self.assertIn("runtime_actions", tables)
            self.assertIn("runtime_ring_decisions", tables)
            self.assertIn("runtime_ring_rules", tables)
            self.assertIn("sagas", tables)
            self.assertIn("saga_steps", tables)
            self.assertIn("saga_events", tables)
            self.assertIn("sandbox_profiles", tables)
            self.assertIn("sandbox_decisions", tables)
            self.assertIn("kill_switch_events", tables)
            self.assertIn("plugins", tables)
            self.assertIn("plugin_versions", tables)
            self.assertIn("plugin_policy_results", tables)
            self.assertIn("plugin_installations", tables)
            self.assertIn("plugin_reviews", tables)
            self.assertIn("plugin_signing_keys", tables)
            self.assertIn("plugin_quality_assessments", tables)
            self.assertIn("plugin_trust_events", tables)
            self.assertIn("slo_objectives", tables)
            self.assertIn("slo_measurements", tables)
            self.assertIn("cost_budgets", tables)
            self.assertIn("cost_events", tables)
            self.assertIn("incidents", tables)
            self.assertIn("chaos_experiments", tables)
            self.assertIn("chaos_runs", tables)
            self.assertIn("rollouts", tables)
            self.assertIn("rollout_events", tables)
            self.assertIn("integrations", tables)
            self.assertIn("integration_instances", tables)
            self.assertIn("framework_agents", tables)
            self.assertIn("provider_credentials", tables)
            self.assertIn("integration_health_checks", tables)
            self.assertIn("workflow_definitions", tables)
            self.assertIn("demo_scenarios", tables)
            self.assertIn("demo_steps", tables)
            self.assertIn("demo_runs", tables)
            self.assertIn("demo_step_runs", tables)
            self.assertIn("demo_reset_runs", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS)
        finally:
            connection.close()

    def test_migration_can_be_rolled_back(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            connection.row_factory = sqlite3.Row
            runner = MigrationRunner(connection)
            runner.apply_all()

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0041")
            self.assertNotIn("demo_reset_runs", tables)
            self.assertIn("demo_runs", tables)
            self.assertIn("demo_step_runs", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-1])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0040")
            self.assertNotIn("demo_runs", tables)
            self.assertNotIn("demo_step_runs", tables)
            self.assertIn("demo_scenarios", tables)
            self.assertIn("demo_steps", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-2])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0039")
            self.assertNotIn("demo_scenarios", tables)
            self.assertNotIn("demo_steps", tables)
            self.assertIn("workflow_definitions", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-3])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0038")
            self.assertNotIn("workflow_definitions", tables)
            self.assertIn("integration_health_checks", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-4])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0037")
            self.assertNotIn("integration_health_checks", tables)
            self.assertIn("provider_credentials", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-5])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0036")
            self.assertNotIn("provider_credentials", tables)
            self.assertIn("framework_agents", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-6])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0035")
            self.assertNotIn("framework_agents", tables)
            self.assertIn("integration_instances", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-7])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0034")
            self.assertNotIn("integration_instances", tables)
            self.assertIn("integrations", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-8])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0033")
            self.assertNotIn("integrations", tables)
            self.assertIn("rollout_events", tables)
            self.assertIn("rollouts", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-9])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0032")
            self.assertNotIn("rollout_events", tables)
            self.assertNotIn("rollouts", tables)
            self.assertIn("chaos_runs", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                    "0016",
                    "0017",
                    "0018",
                    "0019",
                    "0020",
                    "0021",
                    "0022",
                    "0023",
                    "0024",
                    "0025",
                    "0026",
                    "0027",
                    "0028",
                    "0029",
                    "0030",
                    "0031",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0031")
            self.assertNotIn("chaos_runs", tables)
            self.assertIn("chaos_experiments", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                    "0016",
                    "0017",
                    "0018",
                    "0019",
                    "0020",
                    "0021",
                    "0022",
                    "0023",
                    "0024",
                    "0025",
                    "0026",
                    "0027",
                    "0028",
                    "0029",
                    "0030",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0030")
            self.assertNotIn("chaos_experiments", tables)
            self.assertIn("incidents", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                    "0016",
                    "0017",
                    "0018",
                    "0019",
                    "0020",
                    "0021",
                    "0022",
                    "0023",
                    "0024",
                    "0025",
                    "0026",
                    "0027",
                    "0028",
                    "0029",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0029")
            self.assertNotIn("incidents", tables)
            self.assertIn("cost_budgets", tables)
            self.assertIn("cost_events", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                    "0016",
                    "0017",
                    "0018",
                    "0019",
                    "0020",
                    "0021",
                    "0022",
                    "0023",
                    "0024",
                    "0025",
                    "0026",
                    "0027",
                    "0028",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0028")
            self.assertNotIn("cost_budgets", tables)
            self.assertNotIn("cost_events", tables)
            self.assertIn("slo_objectives", tables)
            self.assertIn("slo_measurements", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                    "0016",
                    "0017",
                    "0018",
                    "0019",
                    "0020",
                    "0021",
                    "0022",
                    "0023",
                    "0024",
                    "0025",
                    "0026",
                    "0027",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0027")
            self.assertNotIn("slo_objectives", tables)
            self.assertNotIn("slo_measurements", tables)
            self.assertIn("plugin_reviews", tables)
            self.assertIn("plugin_signing_keys", tables)
            self.assertIn("plugin_quality_assessments", tables)
            self.assertIn("plugin_trust_events", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                    "0016",
                    "0017",
                    "0018",
                    "0019",
                    "0020",
                    "0021",
                    "0022",
                    "0023",
                    "0024",
                    "0025",
                    "0026",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0026")
            self.assertNotIn("plugin_reviews", tables)
            self.assertNotIn("plugin_signing_keys", tables)
            self.assertNotIn("plugin_quality_assessments", tables)
            self.assertNotIn("plugin_trust_events", tables)
            self.assertIn("plugin_installations", tables)
            self.assertIn("plugin_policy_results", tables)
            self.assertIn("plugins", tables)
            self.assertIn("plugin_versions", tables)
            self.assertIn("sandbox_profiles", tables)
            self.assertIn("sandbox_decisions", tables)
            self.assertIn("kill_switch_events", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                    "0016",
                    "0017",
                    "0018",
                    "0019",
                    "0020",
                    "0021",
                    "0022",
                    "0023",
                    "0024",
                    "0025",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0025")
            self.assertNotIn("plugin_installations", tables)
            self.assertIn("plugin_policy_results", tables)
            self.assertIn("plugins", tables)
            self.assertIn("plugin_versions", tables)
            self.assertIn("sandbox_profiles", tables)
            self.assertIn("sandbox_decisions", tables)
            self.assertIn("kill_switch_events", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                    "0016",
                    "0017",
                    "0018",
                    "0019",
                    "0020",
                    "0021",
                    "0022",
                    "0023",
                    "0024",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0024")
            self.assertNotIn("plugin_policy_results", tables)
            self.assertIn("plugins", tables)
            self.assertIn("plugin_versions", tables)
            self.assertIn("sandbox_profiles", tables)
            self.assertIn("sandbox_decisions", tables)
            self.assertIn("kill_switch_events", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                    "0016",
                    "0017",
                    "0018",
                    "0019",
                    "0020",
                    "0021",
                    "0022",
                    "0023",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0023")
            self.assertNotIn("plugins", tables)
            self.assertNotIn("plugin_versions", tables)
            self.assertIn("sandbox_profiles", tables)
            self.assertIn("sandbox_decisions", tables)
            self.assertIn("kill_switch_events", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                    "0016",
                    "0017",
                    "0018",
                    "0019",
                    "0020",
                    "0021",
                    "0022",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0022")
            self.assertNotIn("sandbox_profiles", tables)
            self.assertNotIn("sandbox_decisions", tables)
            self.assertNotIn("kill_switch_events", tables)
            self.assertIn("sagas", tables)
            self.assertIn("saga_steps", tables)
            self.assertIn("saga_events", tables)
            self.assertIn("runtime_ring_rules", tables)
            self.assertIn("runtime_ring_decisions", tables)
            self.assertIn("runtime_sessions", tables)
            self.assertIn("runtime_actions", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                    "0016",
                    "0017",
                    "0018",
                    "0019",
                    "0020",
                    "0021",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0021")
            self.assertNotIn("sagas", tables)
            self.assertNotIn("saga_steps", tables)
            self.assertNotIn("saga_events", tables)
            self.assertIn("runtime_ring_rules", tables)
            self.assertIn("runtime_ring_decisions", tables)
            self.assertIn("runtime_sessions", tables)
            self.assertIn("runtime_actions", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                    "0016",
                    "0017",
                    "0018",
                    "0019",
                    "0020",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0020")
            self.assertNotIn("runtime_ring_rules", tables)
            self.assertIn("runtime_ring_decisions", tables)
            self.assertIn("runtime_sessions", tables)
            self.assertIn("runtime_actions", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                    "0016",
                    "0017",
                    "0018",
                    "0019",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0019")
            self.assertNotIn("runtime_ring_decisions", tables)
            self.assertIn("runtime_sessions", tables)
            self.assertIn("runtime_actions", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                    "0016",
                    "0017",
                    "0018",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0018")
            self.assertNotIn("runtime_sessions", tables)
            self.assertNotIn("runtime_actions", tables)
            self.assertIn("mcp_tool_calls", tables)
            self.assertIn("mcp_approvals", tables)
            self.assertIn("mcp_rate_limits", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                    "0016",
                    "0017",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0017")
            self.assertNotIn("mcp_tool_calls", tables)
            self.assertNotIn("mcp_approvals", tables)
            self.assertNotIn("mcp_rate_limits", tables)
            self.assertIn("mcp_scan_runs", tables)
            self.assertIn("mcp_findings", tables)
            self.assertIn("mcp_scan_baselines", tables)
            self.assertIn("mcp_tools", tables)
            self.assertIn("mcp_tool_versions", tables)
            self.assertIn("mcp_servers", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                    "0016",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0016")
            self.assertNotIn("mcp_scan_runs", tables)
            self.assertNotIn("mcp_findings", tables)
            self.assertNotIn("mcp_scan_baselines", tables)
            self.assertIn("mcp_tools", tables)
            self.assertIn("mcp_tool_versions", tables)
            self.assertIn("mcp_servers", tables)
            self.assertIn("protocol_bridges", tables)
            self.assertIn("protocol_bridge_routes", tables)
            self.assertIn("protocol_bridge_health_checks", tables)
            self.assertIn("mesh_messages", tables)
            self.assertIn("mesh_handoffs", tables)
            self.assertIn("mesh_topology_snapshots", tables)
            self.assertIn("trust_thresholds", tables)
            self.assertIn("trust_cards", tables)
            self.assertIn("trust_scores", tables)
            self.assertIn("policy_bindings", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                    "0015",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0015")
            self.assertNotIn("mcp_tools", tables)
            self.assertNotIn("mcp_tool_versions", tables)
            self.assertIn("mcp_servers", tables)
            self.assertIn("protocol_bridges", tables)
            self.assertIn("protocol_bridge_routes", tables)
            self.assertIn("protocol_bridge_health_checks", tables)
            self.assertIn("mesh_messages", tables)
            self.assertIn("mesh_handoffs", tables)
            self.assertIn("mesh_topology_snapshots", tables)
            self.assertIn("trust_thresholds", tables)
            self.assertIn("trust_cards", tables)
            self.assertIn("trust_scores", tables)
            self.assertIn("policy_bindings", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                    "0014",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0014")
            self.assertNotIn("mcp_servers", tables)
            self.assertIn("protocol_bridges", tables)
            self.assertIn("protocol_bridge_routes", tables)
            self.assertIn("protocol_bridge_health_checks", tables)
            self.assertIn("mesh_messages", tables)
            self.assertIn("mesh_handoffs", tables)
            self.assertIn("mesh_topology_snapshots", tables)
            self.assertIn("trust_thresholds", tables)
            self.assertIn("trust_cards", tables)
            self.assertIn("trust_scores", tables)
            self.assertIn("policy_bindings", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                    "0013",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0013")
            self.assertNotIn("protocol_bridges", tables)
            self.assertNotIn("protocol_bridge_routes", tables)
            self.assertNotIn("protocol_bridge_health_checks", tables)
            self.assertIn("mesh_messages", tables)
            self.assertIn("mesh_handoffs", tables)
            self.assertIn("mesh_topology_snapshots", tables)
            self.assertIn("trust_thresholds", tables)
            self.assertIn("trust_cards", tables)
            self.assertIn("trust_scores", tables)
            self.assertIn("policy_bindings", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                    "0012",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0012")
            self.assertNotIn("mesh_messages", tables)
            self.assertNotIn("mesh_handoffs", tables)
            self.assertNotIn("mesh_topology_snapshots", tables)
            self.assertIn("trust_thresholds", tables)
            self.assertIn("trust_cards", tables)
            self.assertIn("trust_scores", tables)
            self.assertIn("policy_bindings", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                ],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0011")
            self.assertNotIn("trust_thresholds", tables)
            self.assertNotIn("handshake_events", tables)
            self.assertIn("trust_cards", tables)
            self.assertIn("trust_scores", tables)
            self.assertIn("policy_bindings", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                ["0001", "0002", "0003", "0004", "0005", "0006", "0007", "0008", "0009", "0010"],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0010")
            self.assertNotIn("trust_cards", tables)
            self.assertIn("trust_scores", tables)
            self.assertIn("policy_bindings", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                ["0001", "0002", "0003", "0004", "0005", "0006", "0007", "0008", "0009"],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0009")
            self.assertNotIn("trust_scores", tables)
            self.assertIn("policy_bindings", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                ["0001", "0002", "0003", "0004", "0005", "0006", "0007", "0008"],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0008")
            self.assertNotIn("policy_bindings", tables)
            self.assertIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                ["0001", "0002", "0003", "0004", "0005", "0006", "0007"],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0007")
            self.assertNotIn("policy_lint_results", tables)
            self.assertIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(
                runner.applied_versions(),
                ["0001", "0002", "0003", "0004", "0005", "0006"],
            )

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0006")
            self.assertNotIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(runner.applied_versions(), ["0001", "0002", "0003", "0004", "0005"])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0005")
            self.assertNotIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(runner.applied_versions(), ["0001", "0002", "0003", "0004"])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0004")
            self.assertNotIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(runner.applied_versions(), ["0001", "0002", "0003"])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0003")
            self.assertNotIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(runner.applied_versions(), ["0001", "0002"])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0002")
            self.assertNotIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(runner.applied_versions(), ["0001"])

            rolled_back = runner.rollback_last()
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

            self.assertEqual(rolled_back, "0001")
            self.assertNotIn("organizations", tables)
            self.assertNotIn("schema_migrations", tables)
        finally:
            connection.close()

    def test_local_test_database_can_be_created_and_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = os.path.join(tmpdir, "test_product.db")
            settings = Settings(database_url=f"sqlite:///{database_path}")
            runner = MigrationRunner.from_settings(settings)

            applied = runner.apply_all()
            runner.connection.close()
            reopened = connect_database(f"sqlite:///{database_path}")
            try:
                count = reopened.execute(
                    "SELECT COUNT(*) AS count FROM schema_migrations"
                ).fetchone()["count"]
            finally:
                reopened.close()

        self.assertEqual(applied, EXPECTED_MIGRATIONS)
        self.assertEqual(count, len(EXPECTED_MIGRATIONS))


if __name__ == "__main__":
    unittest.main()
