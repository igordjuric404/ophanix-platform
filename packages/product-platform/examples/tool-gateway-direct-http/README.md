# Tool Gateway Direct HTTP Examples

These examples show the public HTTP contract without using the Python SDK.
The tokens below are deterministic local-only placeholders created by
`seed_tool_gateway_direct_http_fixtures`; do not use them outside a local demo,
do not paste them into production configuration, and do not treat them as real
credential material. Production agents should use the Python SDK unless they
have their own equivalent payload validation, timeout, retry, and redaction
controls.

Direct HTTP callers must implement their own token refresh, payload validation,
timeouts, response-size caps, retry policy, redaction, compatibility probing,
and typed error handling before using this pattern outside a local demo.

```bash
export OPHANIX_BASE_URL="http://127.0.0.1:8000"
export OPHANIX_TOOL_GATEWAY_ALLOWED_TOKEN="ophanix-local-only-tool-gateway-allowed-token"
export OPHANIX_TOOL_GATEWAY_DENIED_TOKEN="ophanix-local-only-tool-gateway-denied-token"
```

Allowed invocation:

```bash
curl -sS -X POST "$OPHANIX_BASE_URL/api/v1/tools/claims.lookup/invoke" \
  -H "Authorization: Bearer $OPHANIX_TOOL_GATEWAY_ALLOWED_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: req-demo-direct-http-allowed" \
  -H "X-Correlation-ID: demo-direct-http-allowed" \
  --data '{"payload": {"claim_id": "claim_123"}, "correlation_id": "demo-direct-http-allowed"}'
```

Expected shape: see `expected-allowed-response.json`.

Denied invocation:

```bash
curl -sS -X POST "$OPHANIX_BASE_URL/api/v1/tools/claims.lookup/invoke" \
  -H "Authorization: Bearer $OPHANIX_TOOL_GATEWAY_DENIED_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: req-demo-direct-http-denied" \
  -H "X-Correlation-ID: demo-direct-http-denied" \
  --data '{"payload": {"claim_id": "claim_123"}, "correlation_id": "demo-direct-http-denied"}'
```

Expected shape: see `expected-denied-response.json`.

Denied responses intentionally expose only the coarse `tool_call_denied` code to
the agent. Operators can inspect policy decision and runtime action records for
the detailed internal reason.

Compatibility probe:

```bash
curl -sS "$OPHANIX_BASE_URL/api/v1/gateway/capabilities" \
  -H "Authorization: Bearer $OPHANIX_TOOL_GATEWAY_ALLOWED_TOKEN"
```

Minimal Python `requests` usage:

```bash
OPHANIX_TOOL_GATEWAY_TOKEN="$OPHANIX_TOOL_GATEWAY_ALLOWED_TOKEN" \
python3 examples/tool-gateway-direct-http/direct_http_requests_example.py \
  --base-url "$OPHANIX_BASE_URL" \
  --correlation-id demo-direct-http-python
```

Audit verification:

```bash
curl -sS "$OPHANIX_BASE_URL/api/v1/tool-runtime/actions?correlation_id=demo-direct-http-allowed" \
  -H "Authorization: Bearer $OPHANIX_OPERATOR_TOKEN" \
  -H "X-Environment-ID: env_default"
```

The response contains the runtime action for the matching invocation. Operators
can inspect the same record in Tool Gateway -> Decisions.
