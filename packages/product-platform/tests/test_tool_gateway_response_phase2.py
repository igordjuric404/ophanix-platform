from __future__ import annotations

import unittest

from product_platform.tool_gateway.invocation import ToolExecutionError, ToolExecutionResult
from product_platform.tool_gateway.response import process_tool_execution_response


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"claim_status": {"type": "string"}},
    "required": ["claim_status"],
    "additionalProperties": False,
}


class ToolGatewayResponsePhase2Tests(unittest.TestCase):
    def _tool(self) -> dict:
        return {
            "id": "tool_response_phase2",
            "output_schema_json": '{"additionalProperties":false,"properties":{"claim_status":{"type":"string"}},"required":["claim_status"],"type":"object"}',
        }

    def _policy(self, *, strict: bool = True) -> dict:
        return {
            "max_response_bytes": 32768,
            "redaction_rules_json": {"redact_keys": ["token"], "redact_patterns": []},
            "expose_to_agent": 1,
            "strict_output_validation": 1 if strict else 0,
        }

    def test_unit_valid_output_schema_passes(self) -> None:
        result = process_tool_execution_response(
            self._tool(),
            self._policy(),
            ToolExecutionResult(status="succeeded", body={"claim_status": "open"}),
        )

        self.assertEqual(result.status, "succeeded")
        self.assertTrue(result.response_schema_valid)
        self.assertEqual(result.body, {"claim_status": "open"})

    def test_unit_invalid_output_schema_fails_in_strict_mode(self) -> None:
        with self.assertRaises(ToolExecutionError) as context:
            process_tool_execution_response(
                self._tool(),
                self._policy(strict=True),
                ToolExecutionResult(status="succeeded", body={"bad": "shape"}),
            )

        self.assertEqual(context.exception.code, "response_schema_invalid")

    def test_unit_invalid_output_schema_passes_with_warning_in_non_strict_mode(self) -> None:
        result = process_tool_execution_response(
            self._tool(),
            self._policy(strict=False),
            ToolExecutionResult(status="succeeded", body={"bad": "shape"}),
        )

        self.assertEqual(result.status, "succeeded")
        self.assertFalse(result.response_schema_valid)
        self.assertIn("response_schema_invalid", result.warnings)


if __name__ == "__main__":
    unittest.main()
