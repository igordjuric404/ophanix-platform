from __future__ import annotations

import py_compile
import unittest
from pathlib import Path

import ophanix_tool_gateway


class PackageSmokeTests(unittest.TestCase):
    def test_public_exports_are_available(self) -> None:
        self.assertIsNotNone(ophanix_tool_gateway.OphanixToolGatewayClient)
        self.assertIsNotNone(ophanix_tool_gateway.AsyncOphanixToolGatewayClient)
        self.assertIsNotNone(ophanix_tool_gateway.ToolGatewayError)
        self.assertIsNotNone(ophanix_tool_gateway.ToolAuthenticationError)
        self.assertIsNotNone(ophanix_tool_gateway.ToolGatewayValidationError)

    def test_examples_compile(self) -> None:
        package_root = Path(__file__).resolve().parents[1]
        examples = sorted((package_root / "examples").glob("*.py"))
        self.assertGreater(len(examples), 0)
        for example in examples:
            with self.subTest(example=example.name):
                py_compile.compile(str(example), doraise=True)


if __name__ == "__main__":
    unittest.main()
