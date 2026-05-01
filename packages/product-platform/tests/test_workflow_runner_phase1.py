from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from product_platform.workflows.runner import (
    WorkflowRunnerError,
    WorkflowRunnerRegistry,
    build_default_workflow_runner_registry,
)


class WorkflowRunnerPhase1Tests(unittest.TestCase):
    def test_unknown_workflow_cannot_execute_arbitrary_command(self) -> None:
        registry = build_default_workflow_runner_registry()

        with self.assertRaisesRegex(WorkflowRunnerError, "not allowlisted"):
            registry.run("shell:rm -rf /", {})

    def test_policy_lint_workflow_runs_in_process(self) -> None:
        registry = build_default_workflow_runner_registry()

        result = registry.run(
            "python:policy.lint",
            {
                "policy_body": """version: "1.0"
name: workflow-lint-valid
rules:
  - name: block_shell
    condition:
      field: tool_name
      operator: eq
      value: run_shell
    action: deny
""",
                "policy_format": "yaml",
            },
        )

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.summary["passed"])
        self.assertIn("policy lint passed=True", result.logs[0].message)

    def test_shell_timeout_marks_run_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = WorkflowRunnerRegistry(repo_root=Path(temp_dir))
            registry.register_shell(
                "shell:test.timeout",
                [sys.executable, "-c", "import time; time.sleep(2)"],
                cwd=Path(temp_dir),
                timeout_seconds=0.05,
            )

            result = registry.run("shell:test.timeout", {})

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.exit_code, 124)
        self.assertEqual(result.summary["error"], "timeout")

    def test_shell_working_directory_must_be_allowlisted(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            outside = Path(repo_dir).parent
            registry = WorkflowRunnerRegistry(repo_root=Path(repo_dir))

            with self.assertRaisesRegex(WorkflowRunnerError, "cwd must stay"):
                registry.register_shell(
                    "shell:outside",
                    [sys.executable, "-c", "print('nope')"],
                    cwd=outside,
                )

    def test_default_registry_covers_seeded_command_refs(self) -> None:
        registry = build_default_workflow_runner_registry()

        self.assertIn("python:governance.verify", registry.registered_command_refs())
        self.assertIn("python:policy.lint", registry.registered_command_refs())
        self.assertIn("shell:security.scan", registry.registered_command_refs())
        self.assertIn("shell:sbom.generate", registry.registered_command_refs())


if __name__ == "__main__":
    unittest.main()
