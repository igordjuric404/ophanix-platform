from __future__ import annotations

import unittest

from product_platform.policies.linting import lint_policy_body
from product_platform.policies.models import PolicyLintRequest


VALID_POLICY = """version: "1.0"
name: lint-valid
rules:
  - name: block_shell
    condition:
      field: tool_name
      operator: eq
      value: run_shell
    action: deny
"""


class PolicyEditorPhase1LintServiceTests(unittest.TestCase):
    def test_valid_policy_has_no_errors(self) -> None:
        result = lint_policy_body(
            PolicyLintRequest(body_text=VALID_POLICY, body_format="yaml")
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.issues, [])

    def test_missing_required_field_returns_error(self) -> None:
        result = lint_policy_body(
            PolicyLintRequest(
                body_text='version: "1.0"\nname: missing-rules\n',
                body_format="yaml",
            )
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.issues[0].severity, "error")
        self.assertEqual(result.issues[0].code, "schema.missing_required_field")
        self.assertIn("rules", result.issues[0].message)
        self.assertTrue(result.issues[0].fatal)

    def test_unknown_operator_returns_structured_issue(self) -> None:
        result = lint_policy_body(
            PolicyLintRequest(
                body_text=VALID_POLICY.replace("operator: eq", "operator: around"),
                body_format="yaml",
            )
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.issues[0].code, "schema.unknown_operator")
        self.assertIn("unknown operator", result.issues[0].message)
        self.assertGreaterEqual(result.issues[0].line or 0, 1)

    def test_rego_and_cedar_formats_are_accepted(self) -> None:
        rego = lint_policy_body(
            PolicyLintRequest(
                body_format="rego",
                body_text="package agentos\nallow { input.tool_name == \"search\" }",
            )
        )
        cedar = lint_policy_body(
            PolicyLintRequest(
                body_format="cedar",
                body_text='permit(principal, action, resource);',
            )
        )

        self.assertTrue(rego.passed)
        self.assertTrue(cedar.passed)


if __name__ == "__main__":
    unittest.main()
