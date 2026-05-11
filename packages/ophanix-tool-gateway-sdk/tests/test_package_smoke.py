from __future__ import annotations

import unittest

import ophanix_tool_gateway


class PackageSmokeTests(unittest.TestCase):
    def test_public_exports_are_available(self) -> None:
        self.assertIsNotNone(ophanix_tool_gateway.OphanixToolGatewayClient)
        self.assertIsNotNone(ophanix_tool_gateway.AsyncOphanixToolGatewayClient)
        self.assertIsNotNone(ophanix_tool_gateway.ToolGatewayError)
        self.assertIsNotNone(ophanix_tool_gateway.ToolAuthenticationError)
        self.assertIsNotNone(ophanix_tool_gateway.ToolGatewayValidationError)


if __name__ == "__main__":
    unittest.main()
