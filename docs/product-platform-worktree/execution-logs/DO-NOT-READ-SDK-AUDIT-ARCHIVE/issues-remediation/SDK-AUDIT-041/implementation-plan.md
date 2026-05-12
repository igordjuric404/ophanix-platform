# SDK-AUDIT-041 Implementation Plan: Safe Regex Or Timeout-Backed Redaction

## Repository Changes

Create or update:

```text
packages/product-platform/src/product_platform/tool_gateway/
├── redaction_engine.py
├── response.py
└── models.py
packages/product-platform/tests/test_tool_gateway_redaction_engine.py
packages/product-platform/tests/fixtures/redos_patterns.json
packages/product-platform/pyproject.toml
```

## Dependencies

Add one MVP dependency:

- `regex>=2025.0.0,<2027`

Do not add `google-re2` for MVP. Add it later only if the timeout-backed implementation fails security review or customers require a linear-time engine.

## Implementation Steps

1. Add `redaction_engine.py`:
   - `RedactionEngine` protocol.
   - `TimeoutRegexRedactionEngine`.
   - `RedactionPatternError`.
   - `RedactionTimeoutError`.
   - `compile_policy_rules(policy_id, policy_version, rules)`.

2. Engine selection:
   - `OPHANIX_REDACTION_REGEX_ENGINE=timeout`
   - production default: `timeout`
   - reject any other value for MVP.

3. Validation changes in `models.py`:
   - Compile patterns with selected engine during request validation.
   - Reject pattern length > 512 chars.
   - Reject more than 50 regex rules per policy.

4. Response path changes in `response.py`:
   - Stop using `re.compile` directly.
   - Retrieve compiled rules from cache.
   - Apply timeout engine with `timeout=0.025` seconds per operation.
   - On timeout or engine error:
     - do not store full response;
     - mark response action `redaction_failed`;
     - return fail-closed gateway error unless policy explicitly says `on_redaction_failure=block`.

5. Cache:
   - Key by `(policy_id, updated_at, engine_name)`.
   - Max size 1024 policies.
   - Clear on policy update.

6. Tests:
   - Safe patterns compile and redact.
   - Timeout engine raises on known ReDoS corpus within budget.
   - Redaction failure prevents full-response persistence.
   - Compiled rules are reused across repeated responses.

## Environment Variables

- `OPHANIX_REDACTION_REGEX_ENGINE=timeout`
- `OPHANIX_REDACTION_REGEX_TIMEOUT_MS=25`
- `OPHANIX_REDACTION_MAX_PATTERN_LENGTH=512`
- `OPHANIX_REDACTION_MAX_RULES_PER_POLICY=50`
- `OPHANIX_REDACTION_FAILURE_MODE=block`

## IAM And Security

- No new AWS IAM permissions.
- Redaction failure must be treated as a data-protection event.
- Logs must include policy ID and rule ID, not raw response body.
- Add an application metric/log alert on redaction failures using the existing monitoring stack.

## CI/CD Changes

- Install redaction dependencies in product-platform CI.
- Add timeout-backed redaction tests.
- Include ReDoS corpus tests in required CI with strict timeout.

## Rollout

1. Add timeout-backed engine support.
2. Run migration script to validate existing active response policies under the timeout engine.
3. Produce a report of unsupported patterns.
4. Update or disable unsupported patterns before production switch.
5. Enable `OPHANIX_REDACTION_REGEX_ENGINE=timeout` in staging.
6. Enable in production.

## Observability

Metrics:

- `gateway.redaction.pattern_compile_failure`
- `gateway.redaction.timeout`
- `gateway.redaction.failure_blocked_response`
- `gateway.redaction.duration_ms`
- `gateway.redaction.cache_hit`

Alarms:

- any production redaction timeout.
- redaction failure rate > 0.

## Validation

Run:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m pytest tests/test_tool_gateway_redaction_engine.py -q
```

Add a benchmark assertion:

- ReDoS corpus redaction completes or times out within 50 ms per case.
- No full response is persisted on timeout.

## Rollback

- Keep `OPHANIX_REDACTION_REGEX_ENGINE=timeout`; rollback only by disabling unsafe regex policies or redeploying the prior app version.
- If redaction starts failing broadly, set affected policies to block full response storage and disable regex rules temporarily.
- Do not roll back to unsafe Python `re` in production.

## Acceptance Criteria

- Production no longer uses Python `re` for configured redaction patterns.
- Regex execution has enforced timeout.
- Redaction failures fail closed.
- Existing policies are validated before rollout.
- ReDoS tests are required in CI.
