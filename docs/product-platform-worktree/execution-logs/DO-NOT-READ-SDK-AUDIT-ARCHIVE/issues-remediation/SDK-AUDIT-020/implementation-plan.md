# SDK-AUDIT-020 Implementation Plan: MVP Load And Multi-Worker Validation

## Repository Changes

Create:

```text
packages/product-platform/load/
├── docker-compose.load.yml
├── k6-gateway-load.js
├── mock_upstream.py
├── run_load_validation.sh
├── thresholds.json
└── README.md
packages/product-platform/tests/test_multi_worker_gateway.py
.github/workflows/nightly-load.yml
```

## Local Load Harness

`docker-compose.load.yml` services:

- `postgres`: PostgreSQL 16.
- `mock-upstream`: FastAPI app with:
  - `/ok`
  - `/slow?delay_ms=...`
  - `/large?bytes=...`
  - `/error`
  - `/mutate`
- `gateway`: product-platform running with 2 workers by default and 4 workers when `LOAD_WORKERS=4`.
- `k6`: executes `k6-gateway-load.js`.

Do not add Redis, WAF, API Gateway, ECS load runners, or AWS Distributed Load Testing for the MVP harness.

`run_load_validation.sh`:

1. `docker compose -f load/docker-compose.load.yml up -d postgres mock-upstream gateway`
2. Wait for gateway health.
3. Seed gateway fixtures.
4. Run `docker compose ... run --rm k6`.
5. Export summary JSON to `load/results/latest.json`.
6. Compare against `thresholds.json`.
7. Stop services unless `KEEP_LOAD_STACK=1`.

## Workload Scenarios

Keep traffic modest:

- `discovery_read`: 5 RPS for 1 minute.
- `invoke_success`: 10 RPS for 2 minutes.
- `invoke_slow_upstream`: 2 RPS with 1 second upstream delay.
- `invoke_denied`: 5 RPS for 1 minute.
- `invoke_rate_limited`: short burst above configured database-backed limit.
- `idempotent_replay`: repeated same key after SDK-AUDIT-006.

## Thresholds

Initial MVP pass/fail:

- overall unexpected error rate < 1%.
- success invocation p95 < 750 ms excluding slow-upstream scenario.
- discovery p95 < 300 ms.
- rate-limited scenario returns expected `429` after warmup.
- gateway container max RSS < 512 MB.
- no duplicated runtime actions for idempotent scenario.
- no DB transaction older than 2 seconds except migrations.

## Multi-Worker Test

Add `tests/test_multi_worker_gateway.py`:

- Starts gateway with 2 workers on a random port.
- Uses real HTTP client, not `TestClient`.
- Sends concurrent invocations.
- Asserts:
  - workers can authenticate with shared PostgreSQL state;
  - database-backed rate limit is shared;
  - slow upstream request does not block a discovery request;
  - runtime actions are persisted exactly once per invocation.

## Environment Variables

Load environment:

- `OPHANIX_ENVIRONMENT=test`
- `OPHANIX_DATABASE_URL=postgresql://ophanix:ophanix_load_password@postgres:5432/ophanix_product`
- `OPHANIX_GATEWAY_RATE_LIMIT_BACKEND=database`
- `OPHANIX_GATEWAY_TOKEN_HASH_PEPPER=load-test-pepper`
- `OPHANIX_GATEWAY_MAX_BODY_BYTES=1048576`
- `OPHANIX_GATEWAY_UPSTREAM_MAX_RESPONSE_BYTES=1048576`
- `OPHANIX_GATEWAY_RATE_LIMIT_MAX_REQUESTS=60`
- `OPHANIX_GATEWAY_RATE_LIMIT_WINDOW_SECONDS=60`

## Infrastructure Provisioning

No new AWS infrastructure. This plan runs against local Docker dependencies and the normal staging environment only.

Deferred scale-up:

- AWS Distributed Load Testing only after real customer traffic or formal capacity requirements.
- Dedicated load-runner ECS tasks only after local CI can no longer produce useful signal.

## IAM And Security

- No new IAM permissions.
- Test credentials are generated only for local/staging fixtures.
- Do not run load tests against production customer data.

## CI/CD Changes

- PR CI: run `test_multi_worker_gateway.py` if runtime remains acceptable; otherwise run it in nightly CI.
- Nightly CI: run local Docker Compose load harness.
- Store `load/results/latest.json` as a short-retention CI artifact.

## Observability

Capture:

- k6 summary JSON.
- gateway request latency histogram from logs or test output.
- runtime action status counts.
- DB pool active/idle/waiting counts if exposed.
- container memory and CPU from Docker stats where available.

## Validation

Run locally:

```bash
cd packages/product-platform
bash load/run_load_validation.sh
```

Run multi-worker test:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m pytest tests/test_multi_worker_gateway.py -q
```

## Rollback

- If load harness is flaky, keep it nightly-only while fixing deterministic setup.
- If a release fails the harness, investigate before shipping; do not compensate by raising thresholds unless the new threshold is justified in `thresholds.json`.

## Acceptance Criteria

- A CLI command runs a cheap production-like local load profile.
- At least one multi-worker test exists.
- The harness validates shared PostgreSQL state and database-backed rate limiting.
- No AWS load-testing infrastructure is required for MVP.
