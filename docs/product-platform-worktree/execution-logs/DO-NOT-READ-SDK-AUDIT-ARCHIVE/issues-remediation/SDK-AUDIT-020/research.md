# SDK-AUDIT-020 Research: MVP Load And Multi-Worker Validation

## Problem

The gateway has functional tests but no validation that it behaves correctly with multiple workers, slow upstreams, PostgreSQL, and rate-limit pressure. For an MVP, the goal is not to prove massive scale. The goal is to catch obvious concurrency and resource bugs before early customers see them.

Current limitations:

- No multi-worker ASGI smoke test.
- No concurrent slow-upstream scenario.
- No p95/p99 baseline for startup-scale traffic.
- No memory growth check.
- No validation that database-backed rate limits work across workers.

## Industry Pattern

Early-stage products usually use lightweight performance gates:

- Local Docker Compose dependencies.
- A real ASGI server with 2 to 4 workers.
- k6 or Locust with modest traffic.
- Pass/fail thresholds that catch regressions, not enterprise capacity claims.
- Manual or scheduled staging runs only before important releases.

Large AWS distributed load testing is useful later, but it is overkill for MVP validation.

## Options

### Option A: Unit Tests Only

Benefits:

- Fast and cheap.

Tradeoffs:

- Does not catch worker isolation, DB contention, or slow-upstream amplification.

Decision: insufficient.

### Option B: Local k6 Harness With Docker Compose

Benefits:

- Cheap.
- Runs locally and in CI.
- Exercises real processes and sockets.
- Good enough for MVP confidence.

Tradeoffs:

- Does not prove cloud-region-scale behavior.
- CI runner performance varies.

Decision: adopt.

### Option C: AWS Distributed Load Testing

Benefits:

- Useful for high-scale staging validation later.

Tradeoffs:

- Adds cost, provisioning, and report-management overhead.
- Not needed for an MVP with low expected traffic.

Decision: explicitly defer.

## Final Architecture

Implement a local/CI load harness:

1. Docker Compose starts PostgreSQL, mock upstreams, and gateway with 2 to 4 workers.
2. k6 drives modest workloads:
   - discovery;
   - successful invocation;
   - slow upstream;
   - denied invocation;
   - rate-limited invocation;
   - idempotency replay when SDK-AUDIT-006 is done.
3. The harness fails on clear regressions:
   - high error rate;
   - extreme latency;
   - memory growth;
   - duplicated runtime actions;
   - ineffective shared rate limits.

No AWS load-testing infrastructure is required for MVP.

## AWS Fit

AWS is only needed for the normal staging app and database. Do not provision AWS Distributed Load Testing, extra ECS load runners, WAF, API Gateway, ElastiCache, or dedicated S3 report storage for this issue during MVP.

Deferred trigger for AWS load testing:

- signed customer pilot requires formal load evidence;
- expected traffic exceeds the local harness by at least 10x;
- a performance incident occurs;
- investors/customers require a capacity report.
