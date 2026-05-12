# SDK-AUDIT-019 Implementation Plan: Live Installed-Wheel-To-Running-Gateway Harness

## Repository Changes

Create or update:

```text
packages/ophanix-tool-gateway-sdk/tests/live/
├── run_live_gateway_smoke.py
└── README.md
packages/product-platform/src/product_platform/testing/
├── gateway_fixture.py
└── __init__.py
.github/workflows/ci.yml
packages/ophanix-tool-gateway-sdk/scripts/validate_release.py
```

## Harness Behavior

`run_live_gateway_smoke.py` must be executable as:

```bash
python3 packages/ophanix-tool-gateway-sdk/tests/live/run_live_gateway_smoke.py
```

It performs:

1. Resolve repo root.
2. Build SDK wheel:
   - `python3 -m pip install build`
   - `python3 -m build --wheel packages/ophanix-tool-gateway-sdk`
3. Create temp venv.
4. Install the built wheel normally, not with `--no-deps`.
5. Install product-platform test/runtime dependencies in the server environment.
6. Start mock upstream server on `127.0.0.1:0`.
7. Start product-platform gateway process on `127.0.0.1:0`.
8. Poll `/api/v1/health` until ready.
9. Seed test data through a test-only fixture API or direct repository setup.
10. Run SDK script from the wheel venv against the real gateway URL.
11. Assert all responses.
12. Stop processes and delete temp directories.

## Product Test Fixture

Add `product_platform.testing.gateway_fixture` with:

- `create_live_gateway_fixture(database_url, upstream_base_url)`.
- Inserts:
  - organization;
  - environment;
  - agent;
  - gateway credential with raw test token;
  - credential scope bound to tool;
  - active tool definition;
  - active upstream target;
  - allow and deny policy cases;
  - response redaction policy.
- Returns:
  - `token`;
  - `tool_name`;
  - `denied_tool_name`;
  - expected redaction marker.

The fixture must be importable only for tests. Do not expose it through production API routes.

## SDK Smoke Assertions

The wheel-installed SDK must prove:

- `import ophanix_tool_gateway` works.
- `OphanixToolGatewayClient(base_url, EnvironmentTokenProvider(...))` works.
- `list_tools()` returns the seeded active tool only.
- `call_tool()` success returns:
  - expected `tool_name`;
  - `request_id`;
  - `decision`;
  - sanitized result.
- Denial raises `ToolDeniedError`.
- Bad payload raises `ToolGatewayError` with stable code.
- Upstream 500 raises `ToolGatewayError`.
- Redaction removes seeded secret.
- When SDK-AUDIT-006 is complete, repeated idempotent call returns replay header/result.

## Environment Variables

Harness sets:

- `OPHANIX_ENVIRONMENT=test`
- `OPHANIX_DATABASE_URL=sqlite:///<tempdir>/live_gateway.db`
- `OPHANIX_ENABLE_API_DOCS=false`
- `OPHANIX_GATEWAY_MAX_BODY_BYTES=1048576`
- `OPHANIX_GATEWAY_UPSTREAM_MAX_RESPONSE_BYTES=1048576`
- `OPHANIX_GATEWAY_RATE_LIMIT_BACKEND=in_memory`
- `OPHANIX_GATEWAY_TOKEN_HASH_PEPPER=live-test-pepper`
- `OPHANIX_LIVE_GATEWAY_FIXTURE=true`

## CI/CD Changes

Add a CI job after unit tests:

```yaml
live-sdk-gateway-smoke:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - run: python -m pip install --upgrade pip
    - run: python packages/ophanix-tool-gateway-sdk/tests/live/run_live_gateway_smoke.py
```

Make this job required before publish.

Update `validate_release.py`:

- Add `--run-live-gateway-smoke`.
- In release mode, require the live smoke unless explicitly skipped with `--skip-live-gateway-smoke` and a printed warning.

## IAM And Security

- No AWS IAM required for the local harness.
- Test token must be generated inside temp state.
- Test token must not appear in logs except as redacted.
- Mock upstream binds only to `127.0.0.1`.

## Observability

Capture artifacts on failure:

- server stdout/stderr;
- mock upstream request log;
- SDK smoke stdout/stderr;
- gateway database file for local debugging only in CI artifacts with short retention and no secrets.

## Validation

Run:

```bash
python3 packages/ophanix-tool-gateway-sdk/tests/live/run_live_gateway_smoke.py
```

Expected result:

- exit code `0`;
- printed summary of each smoke scenario;
- no child process left running.

## Rollback

- If harness is flaky, mark job non-required for one PR only and file a blocking follow-up.
- Do not remove the harness.
- Keep package release blocked until the harness is stable again.

## Acceptance Criteria

- CI builds and installs the SDK wheel into a clean venv.
- CI starts a real gateway process.
- SDK calls the gateway over real HTTP.
- Success, denial, schema failure, upstream failure, and redaction are covered.
- Publish validation can invoke the same smoke harness.
