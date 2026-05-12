# SDK-AUDIT-013 Implementation Plan: MVP Distributed Rate Limiting

## Repository Changes

Create or update:

```text
packages/product-platform/src/product_platform/tool_gateway/
├── rate_limit.py
└── repository.py
packages/product-platform/src/product_platform/api/app.py
packages/product-platform/src/product_platform/api/settings.py
packages/product-platform/src/product_platform/db/migrations/
├── 0060_gateway_rate_limit_buckets.up.sql
└── 0060_gateway_rate_limit_buckets.down.sql
packages/product-platform/tests/test_tool_gateway_db_rate_limit.py
packages/product-platform/tests/test_tool_gateway_rate_limit_settings.py
```

## Database Migration

Add:

```sql
CREATE TABLE gateway_rate_limit_buckets (
  rate_limit_key TEXT NOT NULL,
  window_start TEXT NOT NULL,
  window_seconds INTEGER NOT NULL,
  request_count INTEGER NOT NULL,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (rate_limit_key, window_start)
);

CREATE INDEX idx_gateway_rate_limit_buckets_expires_at
  ON gateway_rate_limit_buckets (expires_at);
```

For PostgreSQL, use `TIMESTAMPTZ` for timestamp columns.

## Implementation Steps

1. Add `rate_limit.py`:
   - `RateLimitDecision`
   - `RateLimiter` protocol
   - `InProcessRateLimiter` for local/test
   - `DatabaseFixedWindowRateLimiter` for staging/production

2. Add repository method:
   - `increment_rate_limit_bucket(key, window_start, window_seconds, limit, expires_at) -> RateLimitDecision`
   - Implement with atomic insert/update:
     - insert bucket with count 1;
     - on conflict update count only when current count is below limit;
     - return allowed/remaining/reset time.

3. Update settings:
   - `OPHANIX_GATEWAY_RATE_LIMIT_BACKEND=in_memory|database`
   - `OPHANIX_GATEWAY_RATE_LIMIT_MAX_REQUESTS`
   - `OPHANIX_GATEWAY_RATE_LIMIT_WINDOW_SECONDS`
   - `OPHANIX_GATEWAY_RATE_LIMIT_CLEANUP_ENABLED=true`

4. Production validation:
   - In non-local environments, require `OPHANIX_GATEWAY_RATE_LIMIT_BACKEND=database`.
   - Require positive max/window values.

5. Update `api/app.py`:
   - initialize limiter from settings;
   - enforce before discovery and invocation work;
   - return `429` with `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset`.

6. Add cleanup:
   - CLI command or startup-safe repository method to delete expired buckets.
   - Run cleanup opportunistically once per process every few minutes, guarded by a non-blocking lock.
   - A scheduled job can be added later if bucket volume grows.

## Environment Variables

- `OPHANIX_GATEWAY_RATE_LIMIT_BACKEND=database`
- `OPHANIX_GATEWAY_RATE_LIMIT_MAX_REQUESTS=120`
- `OPHANIX_GATEWAY_RATE_LIMIT_WINDOW_SECONDS=60`
- `OPHANIX_GATEWAY_RATE_LIMIT_CLEANUP_ENABLED=true`

## Infrastructure Provisioning

No new AWS infrastructure for MVP. The limiter uses the same PostgreSQL database introduced for SDK-AUDIT-003.

Deferred scale-up path:

- Add ElastiCache Redis/Valkey only when DB limiter writes become a measurable bottleneck.
- Add WAF/API Gateway edge throttling only when public abusive traffic reaches the app before authentication.

## IAM And Security

- No new IAM permissions.
- Rate-limit keys should be hashed or structured without raw bearer tokens.
- Do not log full credential IDs if logs are externally shared; log key hashes.

## CI/CD Changes

- Add database-backed rate limiter tests to product-platform CI.
- Add a two-process test against PostgreSQL to prove shared limits across processes.
- Keep Redis out of required CI for MVP.

## Rollout

1. Add table and database limiter.
2. Keep in-process limiter for local/test.
3. Enable database limiter in staging.
4. Verify `429` behavior with two app workers.
5. Enable in production.
6. Watch DB write rate and slow query logs for one week.

## Observability

Metrics/log counters:

- `gateway.rate_limit.allowed`
- `gateway.rate_limit.blocked`
- `gateway.rate_limit.backend_error`
- `gateway.rate_limit.cleanup_deleted`

Alert if:

- backend errors occur in production;
- rate-limit bucket table grows unexpectedly;
- DB slow query logs show limiter updates above 100 ms.

## Validation

Run:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m pytest tests/test_tool_gateway_db_rate_limit.py tests/test_tool_gateway_rate_limit_settings.py -q
```

Required cases:

- single worker enforces limit.
- two app instances share the same database bucket.
- expired windows reset allowance.
- `429` headers are deterministic.
- production settings reject `in_memory`.

## Rollback

- Switch staging/local back to `in_memory` if needed.
- For production, redeploy prior version if limiter causes unexpected failures.
- Keep the table; it is harmless and can be dropped later after rollback is stable.

## Acceptance Criteria

- Non-local deployments use shared database-backed limits.
- Multiple workers cannot multiply the configured allowance.
- No Redis, WAF, or API Gateway dependency is required for MVP.
- Response headers and error envelope are stable.
