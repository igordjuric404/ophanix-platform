from __future__ import annotations

import unittest

from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.demo.evidence import build_evidence_links
from product_platform.demo.models import DemoStepRunStatus
from product_platform.demo.repository import DemoScenarioRepository, demo_run_response
from product_platform.demo.runner import DemoScenarioRunner


class DemoLiveEvidencePhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.connection = self.database.connect()
        self.repository = DemoScenarioRepository(
            self.connection,
            "org_default",
            "env_default",
        )

    def test_unit_evidence_link_builder_creates_policy_feed_link(self) -> None:
        detail = self.repository.get_detail("customer-support-refund")
        policy_step = next(step for step in detail.steps if step.action_type == "import_policies")

        links = build_evidence_links(
            policy_step,
            {
                "resource_ids": {"policy_slugs": ["refund-limit"]},
                "correlation_id": "corr-policy",
            },
        )

        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].area, "Policies")
        self.assertEqual(links[0].resource_id, "refund-limit")
        self.assertEqual(
            links[0].route,
            "/policies?policy_slug=refund-limit&correlation_id=corr-policy",
        )

    def test_unit_correlation_id_is_stored_in_step_result(self) -> None:
        with self.database.transaction() as connection:
            repository = DemoScenarioRepository(connection, "org_default", "env_default")
            run = repository.create_run("customer-support-refund", started_by="user_admin")
            DemoScenarioRunner(repository).continue_run(run["id"], correlation_id="corr-step")

        payload = demo_run_response(self.repository, run)

        self.assertEqual(payload.step_runs[0].status, DemoStepRunStatus.SUCCEEDED)
        self.assertEqual(payload.step_runs[0].result["correlation_id"], "corr-step")
        self.assertEqual(payload.step_runs[0].evidence_links[0].correlation_id, "corr-step")

    def test_run_response_shows_expected_actual_and_proof_checklist(self) -> None:
        with self.database.transaction() as connection:
            repository = DemoScenarioRepository(connection, "org_default", "env_default")
            run = repository.create_run("customer-support-refund", started_by="user_admin")
            runner = DemoScenarioRunner(repository)
            runner.continue_run(run["id"], correlation_id="corr-proof")
            run = runner.continue_run(run["id"], correlation_id="corr-proof")

        payload = demo_run_response(self.repository, run)
        policy_step = payload.step_runs[1]

        self.assertEqual(policy_step.status, DemoStepRunStatus.SUCCEEDED)
        self.assertIn("Imported", policy_step.actual_result)
        self.assertEqual(policy_step.proof_checklist[0].status, "completed")
        self.assertEqual(
            policy_step.proof_checklist[0].expected_result,
            policy_step.step.expected_result,
        )
        self.assertEqual(
            policy_step.proof_checklist[0].actual_result,
            policy_step.actual_result,
        )
        self.assertIn("policy_slug=refund-limit", policy_step.proof_checklist[0].route)


if __name__ == "__main__":
    unittest.main()
