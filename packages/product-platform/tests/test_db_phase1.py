from __future__ import annotations

import unittest

from product_platform.api.settings import Settings
from product_platform.db.migrator import (
    MigrationRunner,
    connect_database,
    database_backend_from_url,
    is_supported_database_url,
)
from product_platform.db.repositories import OrganizationRepository
from product_platform.db.seed import DEMO_ENV_ID, DEMO_ORG_ID, DEMO_ADMIN_USER_ID, seed_demo_data
from product_platform.db.testing import (
    column_names,
    create_test_database,
    postgres_url_with_schema,
    table_names,
    test_postgres_url as _test_postgres_url,
)
from product_platform.db.time import utc_now_iso
from product_platform.tool_gateway.models import ToolDefinitionCreateRequest
from product_platform.tool_gateway.repository import ToolRegistryRepository
from product_platform.tool_gateway.runtime_audit import ToolInvocationIdempotencyRepository


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
    "0042",
    "0043",
    "0044",
    "0045",
    "0046",
    "0047",
    "0048",
    "0049",
]

FEATURE_MIGRATIONS = [
    "0050",
    "0051",
    "0052",
    "0053",
    "0054",
    "0055",
    "0056",
    "0057",
    "0058",
    "0059",
    "0060",
    "0061",
    "0062",
    "0063",
    "0064",
    "0065",
    "0066",
]

ALL_EXPECTED_MIGRATIONS = [*EXPECTED_MIGRATIONS, *FEATURE_MIGRATIONS]


class DatabaseMigrationPhase1Tests(unittest.TestCase):
    def test_database_url_parsing_supports_postgres_only(self) -> None:
        self.assertEqual(
            database_backend_from_url("postgresql://ophanix:secret@db.example.com:5432/ophanix"),
            "postgresql",
        )
        self.assertTrue(
            is_supported_database_url(
                "postgresql://ophanix:secret@db.example.com:5432/ophanix"
            )
        )

        self.assertFalse(is_supported_database_url("file:///local.db"))
        self.assertFalse(is_supported_database_url("memory://local"))
        self.assertFalse(is_supported_database_url("unsupported://db.example.com/ophanix"))
        with self.assertRaisesRegex(ValueError, "postgresql://"):
            database_backend_from_url("file:///local.db")

    def test_migration_applies_to_empty_database(self) -> None:
        database = create_test_database(migrate=False)
        connection = database.connect()
        try:
            runner = MigrationRunner(connection)

            applied = runner.apply_all()
            tables = table_names(connection)

            self.assertEqual(applied, ALL_EXPECTED_MIGRATIONS)
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
            self.assertIn("policy_evaluations", tables)
            self.assertIn("audit_exports", tables)
            self.assertIn("control_frameworks", tables)
            self.assertIn("controls", tables)
            self.assertIn("control_mappings", tables)
            self.assertIn("evidence_items", tables)
            self.assertIn("compliance_violations", tables)
            self.assertIn("compliance_reports", tables)
            self.assertIn("report_evidence_items", tables)
            self.assertIn("report_attestations", tables)
            self.assertIn("workflow_logs", tables)
            self.assertIn("artifacts", tables)
            self.assertIn("artifact_links", tables)
            self.assertIn("artifact_attestations", tables)
            self.assertIn("tool_definitions", tables)
            self.assertIn("tool_definition_versions", tables)
            self.assertIn("tool_upstream_targets", tables)
            self.assertIn("tool_upstream_health_checks", tables)
            self.assertIn("agent_tool_permissions", tables)
            self.assertIn("agent_tool_permission_history", tables)
            self.assertIn("tool_policy_decisions", tables)
            self.assertIn("tool_response_policies", tables)
            self.assertIn("tool_runtime_actions", tables)
            self.assertIn("tool_runtime_action_events", tables)
            self.assertIn("tool_invocation_idempotency_records", tables)
            self.assertIn("tool_gateway_rate_limit_windows", tables)
            self.assertIn("tool_gateway_circuit_breaker_state", tables)
            upstream_columns = column_names(connection, "tool_upstream_targets")
            self.assertIn("auth_config_json", upstream_columns)
            self.assertIn("query_parameter_allowlist_json", upstream_columns)
            self.assertEqual(runner.applied_versions(), ALL_EXPECTED_MIGRATIONS)
        finally:
            database.close()

    def test_migration_can_be_rolled_back(self) -> None:
        database = create_test_database(migrate=False)
        connection = database.connect()
        try:
            runner = MigrationRunner(connection)
            runner.apply_all()

            for index, migration in enumerate(reversed(FEATURE_MIGRATIONS), start=1):
                rolled_back = runner.rollback_last()
                tables = table_names(connection)

                self.assertEqual(rolled_back, migration)
                self.assertEqual(
                    runner.applied_versions(),
                    ALL_EXPECTED_MIGRATIONS[:-index],
                )
                if migration == "0058":
                    upstream_columns = column_names(connection, "tool_upstream_targets")
                    self.assertNotIn("auth_config_json", upstream_columns)
                    self.assertNotIn("query_parameter_allowlist_json", upstream_columns)
                if migration == "0059":
                    self.assertNotIn("tool_invocation_idempotency_records", tables)
                if migration == "0060":
                    self.assertNotIn("tool_gateway_rate_limit_windows", tables)
                    self.assertNotIn("tool_gateway_circuit_breaker_state", tables)
                if migration == "0051":
                    self.assertNotIn("tool_upstream_targets", tables)
                    self.assertNotIn("tool_upstream_health_checks", tables)
                    self.assertIn("tool_definitions", tables)
                    self.assertIn("tool_definition_versions", tables)
                if migration == "0052":
                    self.assertNotIn("agent_tool_permissions", tables)
                    self.assertNotIn("agent_tool_permission_history", tables)
                    self.assertIn("tool_upstream_targets", tables)
                    self.assertIn("tool_upstream_health_checks", tables)
                if migration == "0053":
                    self.assertNotIn("tool_policy_decisions", tables)
                    self.assertIn("agent_tool_permissions", tables)
                    self.assertIn("agent_tool_permission_history", tables)
                if migration == "0054":
                    self.assertNotIn("tool_response_policies", tables)
                    self.assertIn("tool_policy_decisions", tables)
                if migration == "0055":
                    self.assertNotIn("tool_runtime_actions", tables)
                    self.assertNotIn("tool_runtime_action_events", tables)
                    self.assertIn("tool_response_policies", tables)
                if migration == "0050":
                    self.assertNotIn("tool_definitions", tables)
                    self.assertNotIn("tool_definition_versions", tables)
                    self.assertIn("artifacts", tables)
                    self.assertIn("artifact_links", tables)

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0049")
            self.assertNotIn("artifact_attestations", tables)
            self.assertIn("artifacts", tables)
            self.assertIn("artifact_links", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-1])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0048")
            self.assertNotIn("artifacts", tables)
            self.assertNotIn("artifact_links", tables)
            self.assertIn("workflow_logs", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-2])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0047")
            self.assertNotIn("workflow_logs", tables)
            self.assertIn("workflow_runs", tables)
            self.assertIn("compliance_reports", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-3])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0046")
            self.assertNotIn("compliance_reports", tables)
            self.assertNotIn("report_evidence_items", tables)
            self.assertNotIn("report_attestations", tables)
            self.assertIn("compliance_violations", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-4])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0045")
            self.assertNotIn("compliance_violations", tables)
            self.assertIn("evidence_items", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-5])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0044")
            self.assertNotIn("control_frameworks", tables)
            self.assertNotIn("controls", tables)
            self.assertNotIn("control_mappings", tables)
            self.assertNotIn("evidence_items", tables)
            self.assertIn("audit_exports", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-6])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0043")
            self.assertNotIn("audit_exports", tables)
            self.assertIn("policy_evaluations", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-7])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0042")
            self.assertNotIn("policy_evaluations", tables)
            self.assertIn("demo_reset_runs", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-8])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0041")
            self.assertNotIn("demo_reset_runs", tables)
            self.assertIn("demo_runs", tables)
            self.assertIn("demo_step_runs", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-9])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0040")
            self.assertNotIn("demo_runs", tables)
            self.assertNotIn("demo_step_runs", tables)
            self.assertIn("demo_scenarios", tables)
            self.assertIn("demo_steps", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-10])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0039")
            self.assertNotIn("demo_scenarios", tables)
            self.assertNotIn("demo_steps", tables)
            self.assertIn("workflow_definitions", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-11])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0038")
            self.assertNotIn("workflow_definitions", tables)
            self.assertIn("integration_health_checks", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-12])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0037")
            self.assertNotIn("integration_health_checks", tables)
            self.assertIn("provider_credentials", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-13])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0036")
            self.assertNotIn("provider_credentials", tables)
            self.assertIn("framework_agents", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-14])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0035")
            self.assertNotIn("framework_agents", tables)
            self.assertIn("integration_instances", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-15])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0034")
            self.assertNotIn("integration_instances", tables)
            self.assertIn("integrations", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-16])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0033")
            self.assertNotIn("integrations", tables)
            self.assertIn("rollout_events", tables)
            self.assertIn("rollouts", tables)
            self.assertEqual(runner.applied_versions(), EXPECTED_MIGRATIONS[:-17])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

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
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0006")
            self.assertNotIn("policies", tables)
            self.assertIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(runner.applied_versions(), ["0001", "0002", "0003", "0004", "0005"])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0005")
            self.assertNotIn("discovery_findings", tables)
            self.assertIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(runner.applied_versions(), ["0001", "0002", "0003", "0004"])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0004")
            self.assertNotIn("discovery_targets", tables)
            self.assertIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(runner.applied_versions(), ["0001", "0002", "0003"])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0003")
            self.assertNotIn("agent_credentials", tables)
            self.assertIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(runner.applied_versions(), ["0001", "0002"])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0002")
            self.assertNotIn("agents", tables)
            self.assertIn("organizations", tables)
            self.assertEqual(runner.applied_versions(), ["0001"])

            rolled_back = runner.rollback_last()
            tables = table_names(connection)

            self.assertEqual(rolled_back, "0001")
            self.assertNotIn("organizations", tables)
            self.assertNotIn("schema_migrations", tables)
        finally:
            database.close()

    def test_local_postgres_database_can_be_created_and_migrated(self) -> None:
        database = create_test_database(migrate=False)
        try:
            runner = MigrationRunner.from_settings(Settings(database_url=database.database_url))

            applied = runner.apply_all()
            runner.connection.close()
            reopened = connect_database(database.database_url)
            try:
                count = reopened.execute(
                    "SELECT COUNT(*) AS count FROM schema_migrations"
                ).fetchone()["count"]
            finally:
                reopened.close()
        finally:
            database.close()

        self.assertEqual(applied, ALL_EXPECTED_MIGRATIONS)
        self.assertEqual(count, len(ALL_EXPECTED_MIGRATIONS))

    def test_postgres_database_can_be_created_migrated_and_used(self) -> None:
        database_url = _test_postgres_url()
        schema_name = "ophanix_test_explicit_schema"
        create_url = postgres_url_with_schema(database_url, schema_name)
        database = create_test_database(migrate=False)
        try:
            self.assertIn(schema_name, create_url)
            applied = database.migrate()
            with database.transaction() as connection:
                seed_demo_data(connection)
                now = utc_now_iso()
                connection.execute(
                    """
                    INSERT INTO agents (
                        id, organization_id, environment_id, name, description,
                        framework, runtime_type, endpoint_url, owner_user_id,
                        sponsor_user_id, status, trust_score, trust_tier,
                        credential_status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "agent_postgres",
                        DEMO_ORG_ID,
                        DEMO_ENV_ID,
                        "Postgres Test Agent",
                        "Postgres backend verification fixture.",
                        "test",
                        "http",
                        None,
                        DEMO_ADMIN_USER_ID,
                        DEMO_ADMIN_USER_ID,
                        "active",
                        90,
                        "trusted",
                        "issued",
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO agent_credentials (
                        id, agent_id, credential_type, token_hash, issuer,
                        status, issued_at, expires_at, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "cred_postgres",
                        "agent_postgres",
                        "gateway_token",
                        "postgres-token-hash",
                        "test",
                        "active",
                        now,
                        "2099-01-01T00:00:00+00:00",
                        "{}",
                    ),
                )
                tool = ToolRegistryRepository(
                    connection, DEMO_ORG_ID, DEMO_ENV_ID
                ).create_tool(
                    ToolDefinitionCreateRequest(
                        name="postgres.lookup",
                        display_name="Postgres Lookup",
                        owner_team="platform",
                        required_scope="tools:postgres.lookup",
                    ),
                    created_by=DEMO_ADMIN_USER_ID,
                )
                idempotency = ToolInvocationIdempotencyRepository(
                    connection, DEMO_ORG_ID, DEMO_ENV_ID
                )
                created, idempotency_row = idempotency.begin_invocation(
                    credential_id="cred_postgres",
                    tool_id=tool["id"],
                    idempotency_key="postgres-test-key",
                    request_hash="request-hash",
                    request_id="req_postgres",
                    correlation_id=None,
                )
                completed = idempotency.complete_invocation(
                    idempotency_row["id"],
                    response_status_code=200,
                    response_body={"ok": True},
                )

            row = OrganizationRepository(database.connect()).get(DEMO_ORG_ID)
            migration_count = database.connect().execute(
                "SELECT COUNT(*) AS count FROM schema_migrations"
            ).fetchone()["count"]
            response_policy = ToolRegistryRepository(
                database.connect(), DEMO_ORG_ID, DEMO_ENV_ID
            ).get_response_policy(tool["id"])
            upstream_columns = column_names(database.connect(), "tool_upstream_targets")
        finally:
            database.close()

        self.assertEqual(applied, ALL_EXPECTED_MIGRATIONS)
        self.assertEqual(migration_count, len(ALL_EXPECTED_MIGRATIONS))
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "Ophanix Demo")
        self.assertIsNotNone(response_policy)
        self.assertTrue(created)
        self.assertEqual(completed["response_status_code"], 200)
        self.assertIn("auth_config_json", upstream_columns)
        self.assertIn("query_parameter_allowlist_json", upstream_columns)
if __name__ == "__main__":
    unittest.main()
