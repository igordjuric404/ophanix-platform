# SDK-AUDIT-006 Implementation Plan: Idempotency Key And Replay Contract

## Repository Changes

Create or update:

```text
packages/product-platform/src/product_platform/tool_gateway/
├── idempotency.py
├── invocation.py
├── repository.py
└── models.py
packages/product-platform/src/product_platform/db/migrations/
├── 0059_tool_gateway_idempotency.up.sql
└── 0059_tool_gateway_idempotency.down.sql
packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py
packages/product-platform/src/ophanix_tool_gateway/sdk.py
packages/product-platform/tests/test_tool_gateway_idempotency.py
packages/product-platform/tests/test_tool_gateway_sdk_idempotency.py
packages/ophanix-tool-gateway-sdk/tests/test_idempotency.py
```

## Database Migration

Add table:

```sql
CREATE TABLE tool_gateway_idempotency_keys (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  environment_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  credential_id TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  tool_version TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  request_fingerprint TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('in_progress', 'succeeded', 'denied', 'failed', 'unknown')),
  runtime_action_id TEXT,
  response_status_code INTEGER,
  response_body TEXT,
  response_headers TEXT NOT NULL DEFAULT '{}',
  error_code TEXT,
  locked_until TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (organization_id, environment_id, credential_id, tool_id, idempotency_key)
);
```

Add indexes:

- `(expires_at)`
- `(status, locked_until)`
- `(runtime_action_id)`

For PostgreSQL, use `JSONB` for `response_body` and `response_headers`.

## Server Implementation

1. Add `idempotency.py`:
   - `validate_idempotency_key(value: str | None) -> str | None`
   - `canonical_request_fingerprint(tool_id, tool_version, payload) -> str`
   - `IdempotencyReplay`
   - `IdempotencyConflict`
   - `IdempotencyInProgress`

2. Add repository methods:
   - `try_claim_idempotency_key(...)`
   - `get_idempotency_record(...)`
   - `complete_idempotency_key(...)`
   - `mark_idempotency_unknown(...)`
   - `expire_stale_idempotency_records(now)`

3. Integrate into gateway invoke route:
   - Read `Idempotency-Key`.
   - Validate before opening execution ownership.
   - Compute fingerprint after payload validation and tool lookup.
   - In a short transaction, attempt insert.
   - If duplicate with same fingerprint and completed response, return replay response.
   - If duplicate same fingerprint and `in_progress`, return `409` and `Retry-After: 2`.
   - If duplicate different fingerprint, return `409 idempotency_key_conflict`.
   - Execute upstream only for the owner request.
   - Store final sanitized response envelope before returning.

4. Add response headers:
   - `Idempotency-Key`
   - `Idempotency-Replayed: true|false`
   - `Idempotency-Status`

5. SDK updates:
   - Add optional `idempotency_key` argument to sync and async `call_tool`.
   - Validate key format client-side.
   - Add `generate_idempotency_key()` helper using `uuid.uuid4()`.
   - Do not auto-retry mutating calls by default.
   - Surface `idempotency_in_progress` and `idempotency_key_conflict` as `ToolGatewayError` with stable codes.

## Environment Variables

- `OPHANIX_GATEWAY_IDEMPOTENCY_ENABLED=true`
- `OPHANIX_GATEWAY_IDEMPOTENCY_TTL_SECONDS=86400`
- `OPHANIX_GATEWAY_IDEMPOTENCY_IN_PROGRESS_TIMEOUT_SECONDS=120`
- `OPHANIX_GATEWAY_REQUIRE_IDEMPOTENCY_FOR_MUTATIONS=false` for first rollout, then true after SDK release.

## IAM And Security

- No new IAM permission if using PostgreSQL.
- Cleanup runs as an application command or opportunistic background cleanup using the normal database credentials.
- Stored response must be the sanitized final gateway response, not raw upstream bytes.
- Idempotency keys are not secrets, but do not log full keys; log first 8 characters plus hash.

## CI/CD Changes

- Add tests to product and standalone SDK jobs.
- Add installed-wheel live test coverage in SDK-AUDIT-019 for idempotent replay.
- Add migration apply test for `0059`.

## Rollout

1. Deploy server accepting optional keys.
2. Release SDK with optional `idempotency_key`.
3. Update docs to recommend keys for all mutating tools.
4. Add tool metadata `requires_idempotency` defaulting false.
5. After one release cycle, set mutating production tools to require keys.

## Observability

Metrics:

- `gateway.idempotency.claimed`
- `gateway.idempotency.replayed`
- `gateway.idempotency.conflict`
- `gateway.idempotency.in_progress`
- `gateway.idempotency.unknown`
- `gateway.idempotency.stale_expired`

Logs:

- request ID, agent ID, tool ID, key hash, fingerprint hash, status.

Alarms:

- conflict rate > 1% for 10 minutes.
- in-progress records older than timeout > 0.
- unknown status rate > 0.5% for 10 minutes.

## Validation

Run:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m pytest tests/test_tool_gateway_idempotency.py tests/test_tool_gateway_sdk_idempotency.py -q
cd ../ophanix-tool-gateway-sdk
PYTHONPATH=src python3 -m pytest tests/test_idempotency.py -q
```

Test cases:

- First request executes upstream exactly once.
- Identical retry replays stored response.
- Same key with different payload returns conflict.
- Concurrent duplicate returns in-progress and does not call upstream twice.
- Denied decision replays.
- Upstream failure stores deterministic failure if no side effect occurred.
- Timeout after upstream dispatch stores `unknown`.

## Rollback

- Disable with `OPHANIX_GATEWAY_IDEMPOTENCY_ENABLED=false`.
- Keep table in place for replay during rollback window.
- SDK remains backward compatible because the argument is optional.
- If a migration rollback is required, first wait until no in-progress records exist, then drop table.

## Acceptance Criteria

- Server implements a documented idempotency contract.
- Mutating calls can be retried safely when an idempotency key is supplied.
- Duplicate concurrent requests do not duplicate upstream execution.
- Completed retries return the same sanitized response envelope.
- SDK exposes key support without forcing automatic mutation retries.
