# SDK-AUDIT-013 Research: MVP Distributed Rate Limiting

## Problem

The gateway rate limiter is process-local. In a multi-worker deployment, each worker has its own counter, so the effective limit is multiplied by worker count. That is not ideal, but an MVP startup also should not add ElastiCache, WAF, API Gateway usage plans, and Redis Lua scripts before there is meaningful traffic.

Current limitations:

- Counters are process-local.
- Multiple workers do not share state.
- No durable audit of rate-limit decisions.
- No startup warning that process-local limits are approximate.

## Industry Pattern

Production platforms often use Redis/Valkey or edge services for high-throughput distributed rate limiting. For an MVP, the common pragmatic pattern is simpler:

- Use database-backed fixed windows for authenticated low-volume APIs.
- Keep one small table keyed by principal, route/tool, and time bucket.
- Enforce limits with a unique key and short transaction.
- Add `429` plus `Retry-After`.
- Move to Redis only when database contention or traffic justifies it.

This avoids a new always-on cache bill and still fixes the core multi-worker correctness issue for startup-scale traffic.

## Options

### Option A: Keep Process-Local Limiter

Benefits:

- No new code or infrastructure.

Tradeoffs:

- Limits are inaccurate with multiple workers.
- The audit issue remains unresolved.

Decision: keep only as local/test fallback.

### Option B: PostgreSQL Fixed-Window Limiter

Benefits:

- Reuses the MVP database.
- No additional AWS service.
- Works across workers and app instances.
- Easy to inspect and test.
- Good enough for low to moderate authenticated gateway traffic.

Tradeoffs:

- One write per limited operation.
- Hot keys can create contention at high traffic.
- Less precise than token bucket/GCRA.

Decision: adopt for MVP.

### Option C: ElastiCache Redis/Valkey Token Bucket

Benefits:

- Low latency at high request volume.
- Industry-standard for high-throughput rate limiting.
- Better fit for bursty public APIs.

Tradeoffs:

- Adds infrastructure, secrets, alarms, and cost.
- Overkill until traffic shows the DB limiter is a bottleneck.

Decision: defer. Document as the scale-up path.

## Final Architecture

Use a PostgreSQL-backed fixed-window limiter by default in non-local environments.

Rate-limit key dimensions:

- organization ID;
- environment ID;
- credential ID;
- route family: `gateway_discovery` or `gateway_invoke`;
- tool ID for invocation limits.

Table shape:

- `rate_limit_key`
- `window_start`
- `window_seconds`
- `request_count`
- `expires_at`

Algorithm:

1. Compute the current fixed window.
2. Insert the bucket row with count 1 if it does not exist.
3. Otherwise increment count only if `request_count < limit`.
4. If the update affects no row, return `429`.
5. Delete expired buckets with a scheduled cleanup command.

For MVP scale, fixed windows are acceptable. If users can exploit boundary bursts, move to a sliding window or Redis token bucket later.

## AWS Fit

AWS-managed PostgreSQL is sufficient for the MVP. No additional AWS service is required. AWS WAF/API Gateway and ElastiCache are explicitly deferred until:

- there is public unauthenticated traffic;
- p95 limiter latency is material;
- rate-limit bucket writes exceed an agreed DB budget;
- abusive traffic reaches the app before authentication.

## Consequences

- Fixes multi-worker correctness without a new cache service.
- Keeps monthly infrastructure cost lower.
- Adds one small write path to the database.
- Leaves a clear migration path to Redis/Valkey when traffic demands it.
