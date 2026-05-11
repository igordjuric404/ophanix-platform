from __future__ import annotations

import math
import os
import unittest
import asyncio

import httpx

from product_platform.tool_gateway.sdk import (
    AsyncOphanixToolGatewayClient,
    EnvironmentTokenProvider,
    OphanixToolGatewayClient,
    StaticTokenProvider,
)


class ToolGatewaySdkPhase1Tests(unittest.TestCase):
    def test_client_requires_base_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "base_url is required"):
            OphanixToolGatewayClient(
                base_url="",
                token_provider=StaticTokenProvider("sdk-token"),
            )

    def test_client_rejects_non_string_base_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "base_url must be a string"):
            OphanixToolGatewayClient(
                base_url=123,  # type: ignore[arg-type]
                token_provider=StaticTokenProvider("sdk-token"),
            )

    def test_client_applies_timeout_default_and_normalizes_base_url(self) -> None:
        client = OphanixToolGatewayClient(
            base_url="https://gateway.example.test/",
            token_provider=StaticTokenProvider("sdk-token"),
        )

        self.assertEqual(client.base_url, "https://gateway.example.test")
        self.assertEqual(client.timeout_seconds, 5.0)

    def test_client_rejects_non_numeric_timeout(self) -> None:
        with self.assertRaisesRegex(ValueError, "timeout_seconds must be a number"):
            OphanixToolGatewayClient(
                base_url="https://gateway.example.test",
                token_provider=StaticTokenProvider("sdk-token"),
                timeout_seconds="5",  # type: ignore[arg-type]
            )

    def test_client_rejects_non_finite_timeout(self) -> None:
        with self.assertRaisesRegex(ValueError, "timeout_seconds must be a finite number"):
            OphanixToolGatewayClient(
                base_url="https://gateway.example.test",
                token_provider=StaticTokenProvider("sdk-token"),
                timeout_seconds=math.inf,
            )

    def test_client_rejects_invalid_max_payload_bytes(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_payload_bytes must be greater than zero"):
            OphanixToolGatewayClient(
                base_url="https://gateway.example.test",
                token_provider=StaticTokenProvider("sdk-token"),
                max_payload_bytes=0,
            )

    def test_client_rejects_invalid_cache_ttl(self) -> None:
        with self.assertRaisesRegex(ValueError, "cache_ttl_seconds must be greater than 0"):
            OphanixToolGatewayClient(
                base_url="https://gateway.example.test",
                token_provider=StaticTokenProvider("sdk-token"),
                cache_tools=True,
                cache_ttl_seconds=0,
            )

    def test_client_rejects_non_callable_token_provider(self) -> None:
        with self.assertRaisesRegex(ValueError, "token_provider must provide get_token"):
            OphanixToolGatewayClient(
                base_url="https://gateway.example.test",
                token_provider=object(),  # type: ignore[arg-type]
            )

    def test_client_rejects_non_callable_event_hook(self) -> None:
        with self.assertRaisesRegex(ValueError, "event_hook must be callable"):
            OphanixToolGatewayClient(
                base_url="https://gateway.example.test",
                token_provider=StaticTokenProvider("sdk-token"),
                event_hook="not-callable",  # type: ignore[arg-type]
            )

    def test_sync_client_rejects_async_http_client(self) -> None:
        async_client = httpx.AsyncClient()
        try:
            with self.assertRaisesRegex(ValueError, "sync client"):
                OphanixToolGatewayClient(
                    base_url="https://gateway.example.test",
                    token_provider=StaticTokenProvider("sdk-token"),
                    http_client=async_client,  # type: ignore[arg-type]
                )
        finally:
            asyncio.run(async_client.aclose())

    def test_async_client_rejects_sync_http_client(self) -> None:
        with httpx.Client() as sync_client:
            with self.assertRaisesRegex(ValueError, "async client"):
                AsyncOphanixToolGatewayClient(
                    base_url="https://gateway.example.test",
                    token_provider=StaticTokenProvider("sdk-token"),
                    http_client=sync_client,  # type: ignore[arg-type]
                )

    def test_client_rejects_non_integer_discovery_retries(self) -> None:
        with self.assertRaisesRegex(ValueError, "discovery_max_retries must be an integer"):
            OphanixToolGatewayClient(
                base_url="https://gateway.example.test",
                token_provider=StaticTokenProvider("sdk-token"),
                discovery_max_retries=True,  # type: ignore[arg-type]
            )

    def test_client_rejects_non_finite_discovery_retry_config(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "discovery_retry_backoff_seconds must be a finite number",
        ):
            OphanixToolGatewayClient(
                base_url="https://gateway.example.test",
                token_provider=StaticTokenProvider("sdk-token"),
                discovery_retry_backoff_seconds=math.nan,
            )

    def test_client_rejects_discovery_retry_jitter_above_one(self) -> None:
        with self.assertRaisesRegex(ValueError, "jitter_ratio must be less than or equal to 1"):
            OphanixToolGatewayClient(
                base_url="https://gateway.example.test",
                token_provider=StaticTokenProvider("sdk-token"),
                discovery_retry_jitter_ratio=1.1,
            )

    def test_client_rejects_non_boolean_flags(self) -> None:
        with self.assertRaisesRegex(ValueError, "allow_insecure_http must be a boolean"):
            OphanixToolGatewayClient(
                base_url="http://gateway.example.test",
                token_provider=StaticTokenProvider("sdk-token"),
                allow_insecure_http="true",  # type: ignore[arg-type]
            )

    def test_client_rejects_plain_http_for_non_local_hosts(self) -> None:
        with self.assertRaisesRegex(ValueError, "must use https"):
            OphanixToolGatewayClient(
                base_url="http://gateway.example.test",
                token_provider=StaticTokenProvider("sdk-token"),
            )

    def test_client_rejects_base_url_control_characters(self) -> None:
        with self.assertRaisesRegex(ValueError, "control characters"):
            OphanixToolGatewayClient(
                base_url="https://gateway.example.test\n.evil",
                token_provider=StaticTokenProvider("sdk-token"),
            )

    def test_client_rejects_base_url_credentials(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not include credentials"):
            OphanixToolGatewayClient(
                base_url="https://user:password@gateway.example.test",
                token_provider=StaticTokenProvider("sdk-token"),
            )

    def test_client_rejects_base_url_query_or_fragment(self) -> None:
        with self.assertRaisesRegex(ValueError, "query string or fragment"):
            OphanixToolGatewayClient(
                base_url="https://gateway.example.test?token=bad",
                token_provider=StaticTokenProvider("sdk-token"),
            )

    def test_client_allows_plain_http_for_local_development(self) -> None:
        client = OphanixToolGatewayClient(
            base_url="http://127.0.0.1:8088/",
            token_provider=StaticTokenProvider("sdk-token"),
        )

        self.assertEqual(client.base_url, "http://127.0.0.1:8088")

    def test_client_can_opt_into_plain_http_for_non_local_hosts(self) -> None:
        client = OphanixToolGatewayClient(
            base_url="http://gateway.internal.test",
            token_provider=StaticTokenProvider("sdk-token"),
            allow_insecure_http=True,
        )

        self.assertEqual(client.base_url, "http://gateway.internal.test")

    def test_client_rejects_user_agent_header_control_characters(self) -> None:
        with self.assertRaisesRegex(ValueError, "header control characters"):
            OphanixToolGatewayClient(
                base_url="https://gateway.example.test",
                token_provider=StaticTokenProvider("sdk-token"),
                user_agent="bad\nagent",
            )

    def test_client_rejects_user_agent_other_control_characters(self) -> None:
        with self.assertRaisesRegex(ValueError, "header control characters"):
            OphanixToolGatewayClient(
                base_url="https://gateway.example.test",
                token_provider=StaticTokenProvider("sdk-token"),
                user_agent="bad\x00agent",
            )

    def test_static_token_provider_returns_token(self) -> None:
        provider = StaticTokenProvider("sdk-token")

        self.assertEqual(provider.get_token(), "sdk-token")

    def test_static_token_provider_rejects_non_string_token(self) -> None:
        provider = StaticTokenProvider(123)  # type: ignore[arg-type]

        with self.assertRaisesRegex(ValueError, "token must be a string"):
            provider.get_token()

    def test_static_token_provider_repr_does_not_expose_token(self) -> None:
        provider = StaticTokenProvider("super-secret-sdk-token")

        self.assertNotIn("super-secret-sdk-token", repr(provider))
        self.assertIn("StaticTokenProvider", repr(provider))

    def test_environment_token_provider_reads_configured_environment_variable(self) -> None:
        os.environ["OPHANIX_TEST_GATEWAY_TOKEN"] = " env-token "
        try:
            provider = EnvironmentTokenProvider("OPHANIX_TEST_GATEWAY_TOKEN")

            self.assertEqual(provider.get_token(), "env-token")
        finally:
            os.environ.pop("OPHANIX_TEST_GATEWAY_TOKEN", None)

    def test_environment_token_provider_rejects_missing_token(self) -> None:
        os.environ.pop("OPHANIX_MISSING_GATEWAY_TOKEN", None)
        provider = EnvironmentTokenProvider("OPHANIX_MISSING_GATEWAY_TOKEN")

        with self.assertRaisesRegex(ValueError, "environment variable is required"):
            provider.get_token()

    def test_sdk_types_are_exported_from_tool_gateway_namespace(self) -> None:
        from ophanix_tool_gateway import __version__ as StandaloneVersion
        from ophanix_tool_gateway import AsyncOphanixToolGatewayClient as StandaloneAsyncClient
        from ophanix_tool_gateway import OphanixToolGatewayClient as StandaloneClient
        from ophanix_tool_gateway import ToolAuthenticationError as StandaloneAuthError
        from product_platform.tool_gateway import __version__ as ExportedVersion
        from product_platform.tool_gateway import (
            AsyncOphanixToolGatewayClient as ExportedAsyncClient,
        )
        from product_platform.tool_gateway import EnvironmentTokenProvider as ExportedEnvProvider
        from product_platform.tool_gateway import OphanixToolGatewayClient as ExportedClient
        from product_platform.tool_gateway import StaticTokenProvider as ExportedProvider
        from product_platform.tool_gateway import ToolAuthenticationError as ExportedAuthError

        self.assertIsInstance(StandaloneVersion, str)
        self.assertNotEqual(StandaloneVersion, "0.0.0")
        self.assertEqual(ExportedVersion, StandaloneVersion)
        self.assertIs(StandaloneClient, OphanixToolGatewayClient)
        self.assertIs(StandaloneAsyncClient, AsyncOphanixToolGatewayClient)
        self.assertIs(ExportedClient, OphanixToolGatewayClient)
        self.assertIs(ExportedAsyncClient, AsyncOphanixToolGatewayClient)
        self.assertIs(ExportedEnvProvider, EnvironmentTokenProvider)
        self.assertIs(ExportedProvider, StaticTokenProvider)
        self.assertIs(ExportedAuthError, StandaloneAuthError)


if __name__ == "__main__":
    unittest.main()
