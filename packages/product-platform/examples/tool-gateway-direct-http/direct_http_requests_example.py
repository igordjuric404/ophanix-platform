from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any, Callable
from urllib.parse import quote, urlparse

try:
    import requests
except ImportError:  # pragma: no cover - exercised only when users run without requests installed.
    requests = None

MAX_RESPONSE_BYTES = 1_000_000
MAX_TOKEN_LENGTH = 4096
TOOL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")


class ToolGatewayDirectHttpError(RuntimeError):
    def __init__(self, message: str, *, status_code: int, response: dict[str, Any]) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class ToolGatewayDirectHttpDenied(ToolGatewayDirectHttpError):
    def __init__(self, response: dict[str, Any]) -> None:
        error = response.get("error") if isinstance(response.get("error"), dict) else {}
        reason_code = response.get("reason_code") or error.get("code")
        message = error.get("message") or "Tool call denied by gateway policy."
        super().__init__(str(message), status_code=403, response=response)
        self.reason_code = str(reason_code) if reason_code is not None else None


PostCallable = Callable[..., Any]
GetCallable = Callable[..., Any]


def invoke_tool_direct_http(
    *,
    base_url: str,
    token: str,
    tool_name: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
    timeout: float = 10.0,
    max_response_bytes: int = MAX_RESPONSE_BYTES,
    post: PostCallable | None = None,
) -> dict[str, Any]:
    post_callable = post or _requests_post()
    normalized_base_url = _normalize_base_url(base_url)
    token = _validate_token(token)
    tool_name = _validate_tool_name(tool_name)
    _validate_payload(payload)
    request_body: dict[str, Any] = {"payload": payload}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id
        request_body["correlation_id"] = correlation_id
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    response = post_callable(
        f"{normalized_base_url}/api/v1/tools/{quote(tool_name, safe='')}/invoke",
        headers=headers,
        json=request_body,
        timeout=timeout,
    )
    response_json = _response_json(response, max_response_bytes=max_response_bytes)
    if response.status_code == 403:
        raise ToolGatewayDirectHttpDenied(response_json)
    if response.status_code >= 400:
        raise ToolGatewayDirectHttpError(
            f"Tool Gateway returned HTTP {response.status_code}.",
            status_code=response.status_code,
            response=response_json,
        )
    return response_json


def list_runtime_actions_by_correlation_id(
    *,
    base_url: str,
    user_token: str,
    correlation_id: str,
    timeout: float = 10.0,
    max_response_bytes: int = MAX_RESPONSE_BYTES,
    get: GetCallable | None = None,
) -> list[dict[str, Any]]:
    get_callable = get or _requests_get()
    normalized_base_url = _normalize_base_url(base_url)
    user_token = _validate_token(user_token)
    response = get_callable(
        f"{normalized_base_url}/api/v1/tool-runtime/actions",
        headers={
            "Authorization": f"Bearer {user_token}",
            "Accept": "application/json",
        },
        params={"correlation_id": correlation_id},
        timeout=timeout,
    )
    actions_body = _response_json(response, max_response_bytes=max_response_bytes)
    if response.status_code >= 400:
        raise ToolGatewayDirectHttpError(
            f"Tool Gateway returned HTTP {response.status_code}.",
            status_code=response.status_code,
            response=actions_body,
        )
    actions = actions_body
    if not isinstance(actions, list):
        raise ToolGatewayDirectHttpError(
            "Tool Gateway returned an invalid runtime action response.",
            status_code=response.status_code,
            response={"result": actions},
        )
    return actions


def _normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be an absolute http or https URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base_url must not include credentials, query string, or fragment.")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("plain http is allowed only for local demo hosts.")
    return normalized


def _validate_token(value: str) -> str:
    token = value.strip()
    if not token:
        raise ValueError("token is required.")
    if token.lower().startswith("bearer "):
        raise ValueError("token must be the raw token without the Bearer prefix.")
    if any(character.isspace() for character in token) or len(token) > MAX_TOKEN_LENGTH:
        raise ValueError("token contains unsupported whitespace or exceeds the maximum length.")
    return token


def _validate_tool_name(value: str) -> str:
    tool_name = value.strip()
    if not tool_name or not TOOL_NAME_PATTERN.fullmatch(tool_name):
        raise ValueError("tool_name contains unsupported characters.")
    return tool_name


def _validate_payload(value: dict[str, Any]) -> None:
    if not isinstance(value, dict):
        raise ValueError("payload must be a dictionary.")
    json.dumps(value, allow_nan=False)


def _response_json(response: Any, *, max_response_bytes: int) -> Any:
    content_length = getattr(response, "headers", {}).get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > max_response_bytes:
                raise ToolGatewayDirectHttpError(
                    "Tool Gateway response exceeds max_response_bytes.",
                    status_code=response.status_code,
                    response={"error": {"code": "response_too_large"}},
                )
        except ValueError:
            pass
    raw_text = getattr(response, "text", "")
    if isinstance(raw_text, str) and len(raw_text.encode("utf-8")) > max_response_bytes:
        raise ToolGatewayDirectHttpError(
            "Tool Gateway response exceeds max_response_bytes.",
            status_code=response.status_code,
            response={"error": {"code": "response_too_large"}},
        )
    try:
        return response.json()
    except ValueError as exc:
        raise ToolGatewayDirectHttpError(
            "Tool Gateway returned a non-JSON response.",
            status_code=response.status_code,
            response={"error": {"code": "non_json_response"}},
        ) from exc


def _requests_post() -> PostCallable:
    if requests is None:
        raise RuntimeError("Install requests to run this example: python3 -m pip install requests")
    return requests.post


def _requests_get() -> GetCallable:
    if requests is None:
        raise RuntimeError("Install requests to run this example: python3 -m pip install requests")
    return requests.get


def main() -> None:
    parser = argparse.ArgumentParser(description="Invoke a Tool Gateway tool using direct HTTP.")
    parser.add_argument("--base-url", default=os.getenv("OPHANIX_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.getenv("OPHANIX_TOOL_GATEWAY_TOKEN"))
    parser.add_argument("--tool-name", default="claims.lookup")
    parser.add_argument("--claim-id", default="claim_123")
    parser.add_argument("--correlation-id", default="demo-direct-http-python")
    parser.add_argument("--idempotency-key", default=None)
    args = parser.parse_args()
    if not args.token:
        raise SystemExit("Set OPHANIX_TOOL_GATEWAY_TOKEN or pass --token.")
    result = invoke_tool_direct_http(
        base_url=args.base_url,
        token=args.token,
        tool_name=args.tool_name,
        payload={"claim_id": args.claim_id},
        correlation_id=args.correlation_id,
        idempotency_key=args.idempotency_key,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
