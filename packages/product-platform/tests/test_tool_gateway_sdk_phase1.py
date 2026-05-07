from __future__ import annotations

import unittest

from product_platform.tool_gateway.sdk import OphanixToolGatewayClient, StaticTokenProvider


class ToolGatewaySdkPhase1Tests(unittest.TestCase):
    def test_client_requires_base_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "base_url is required"):
            OphanixToolGatewayClient(
                base_url="",
                token_provider=StaticTokenProvider("sdk-token"),
            )

    def test_client_applies_timeout_default_and_normalizes_base_url(self) -> None:
        client = OphanixToolGatewayClient(
            base_url="https://gateway.example.test/",
            token_provider=StaticTokenProvider("sdk-token"),
        )

        self.assertEqual(client.base_url, "https://gateway.example.test")
        self.assertEqual(client.timeout_seconds, 5.0)

    def test_static_token_provider_returns_token(self) -> None:
        provider = StaticTokenProvider("sdk-token")

        self.assertEqual(provider.get_token(), "sdk-token")

    def test_sdk_types_are_exported_from_tool_gateway_namespace(self) -> None:
        from product_platform.tool_gateway import OphanixToolGatewayClient as ExportedClient
        from product_platform.tool_gateway import StaticTokenProvider as ExportedProvider

        self.assertIs(ExportedClient, OphanixToolGatewayClient)
        self.assertIs(ExportedProvider, StaticTokenProvider)


if __name__ == "__main__":
    unittest.main()
