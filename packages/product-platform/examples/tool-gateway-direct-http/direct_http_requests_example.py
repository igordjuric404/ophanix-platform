from __future__ import annotations

import argparse
import json
import os
from typing import Any, Callable

try:
    import requests
except ImportError:  # pragma: no cover - exercised only when users run without requests installed.
    requests = None


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
    post: PostCallable | None = None,
) -> dict[str, Any]:
    post_callable = post or _requests_post()
    normalized_base_url = base_url.rstrip("/")
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
        f"{normalized_base_url}/api/v1/tools/{tool_name}/invoke",
        headers=headers,
        json=request_body,
        timeout=timeout,
    )
    response_json = response.json()
    if response.status_code == 403:
        raise ToolGatewayDirectHttpDenied(response_json)
    if response.status_code >= 400:
        response.raise_for_status()
    return response_json


def list_runtime_actions_by_correlation_id(
    *,
    base_url: str,
    user_token: str,
    correlation_id: str,
    timeout: float = 10.0,
    get: GetCallable | None = None,
) -> list[dict[str, Any]]:
    get_callable = get or _requests_get()
    normalized_base_url = base_url.rstrip("/")
    response = get_callable(
        f"{normalized_base_url}/api/v1/tool-runtime/actions",
        headers={
            "Authorization": f"Bearer {user_token}",
            "Accept": "application/json",
        },
        params={"correlation_id": correlation_id},
        timeout=timeout,
    )
    response.raise_for_status()
    actions = response.json()
    if not isinstance(actions, list):
        raise ToolGatewayDirectHttpError(
            "Tool Gateway returned an invalid runtime action response.",
            status_code=response.status_code,
            response={"result": actions},
        )
    return actions


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
