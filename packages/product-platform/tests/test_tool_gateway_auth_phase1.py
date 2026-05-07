from __future__ import annotations

import unittest

from product_platform.tool_gateway.auth import (
    GatewayAuthenticationError,
    hash_gateway_token,
    parse_bearer_authorization,
)


class ToolGatewayAuthPhase1Tests(unittest.TestCase):
    def test_unit_missing_header_returns_gateway_auth_error(self) -> None:
        with self.assertRaises(GatewayAuthenticationError) as context:
            parse_bearer_authorization(None)

        self.assertEqual(context.exception.reason_code, "missing_authorization")

    def test_unit_non_bearer_header_returns_gateway_auth_error(self) -> None:
        with self.assertRaises(GatewayAuthenticationError) as context:
            parse_bearer_authorization("Basic abc123")

        self.assertEqual(context.exception.reason_code, "invalid_authorization_scheme")

    def test_unit_empty_token_returns_gateway_auth_error(self) -> None:
        with self.assertRaises(GatewayAuthenticationError) as context:
            parse_bearer_authorization("Bearer   ")

        self.assertEqual(context.exception.reason_code, "empty_bearer_token")

    def test_unit_oversized_token_returns_gateway_auth_error_without_token_material(self) -> None:
        token = "secret-token-value" * 300

        with self.assertRaises(GatewayAuthenticationError) as context:
            parse_bearer_authorization(f"Bearer {token}")

        self.assertEqual(context.exception.reason_code, "token_too_large")
        self.assertNotIn(token, str(context.exception))

    def test_unit_presented_token_is_hashed_for_lookup(self) -> None:
        token = "gateway-token"

        token_hash = hash_gateway_token(token)

        self.assertNotEqual(token_hash, token)
        self.assertEqual(len(token_hash), 64)
        self.assertEqual(parse_bearer_authorization(f"Bearer {token}"), token)


if __name__ == "__main__":
    unittest.main()
