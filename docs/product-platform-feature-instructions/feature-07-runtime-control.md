# Feature 07: Runtime Control

## Feature Goal and Expected User Outcome

Validate that an operator can start runtime sessions, evaluate runtime actions against execution rings, define ring rules, create and execute sagas, test sandbox profiles, and trigger emergency kill-switch events with exact confirmation.

The expected outcome is a runtime session with decisions, a ring rule, a saga with steps and events, a sandbox test result, and a kill-switch record when explicitly triggered.

## Implementation Surface

- Frontend route: `/runtime`.
- Frontend page: `frontend/src/features/runtime/RuntimePage.tsx`.
- API endpoints include:
  - `GET /api/v1/runtime/sessions`
  - `POST /api/v1/runtime/sessions`
  - `GET /api/v1/runtime/sessions/{session_id}`
  - `POST /api/v1/runtime/sessions/{session_id}/actions`
  - `POST /api/v1/runtime/sessions/{session_id}/end`
  - `GET /api/v1/runtime/ring-decisions`
  - `GET /api/v1/runtime/ring-rules`
  - `POST /api/v1/runtime/ring-rules`
  - `GET /api/v1/runtime/sandbox-profiles`
  - `POST /api/v1/runtime/sandbox-profiles`
  - `GET /api/v1/runtime/sandbox-profiles/{profile_id}`
  - `POST /api/v1/runtime/sandbox-profiles/{profile_id}/test`
  - `POST /api/v1/runtime/kill-switch`
  - `GET /api/v1/runtime/kill-switch/events`
  - `GET /api/v1/runtime/sagas`
  - `POST /api/v1/runtime/sagas`
  - `GET /api/v1/runtime/sagas/{saga_id}`
  - `POST /api/v1/runtime/sagas/{saga_id}/steps`
  - `POST /api/v1/runtime/sagas/{saga_id}/execute`
  - `POST /api/v1/runtime/sagas/{saga_id}/cancel`
- Domain modules: `runtime/repository.py`, `runtime/rings.py`, `runtime/sagas.py`, `runtime/saga_executor.py`, `runtime/sandbox.py`, `runtime/kill_switch.py`.
- Migrations: `0018_runtime_sessions.up.sql`, `0019_runtime_ring_decisions.up.sql`, `0020_runtime_ring_rules.up.sql`.
- Tests: `test_runtime_sessions_and_rings_*.py`, `test_saga_builder_and_monitor_*.py`, `test_sandbox_profiles_and_kill_switch_*.py`, `frontend/src/features/runtime/RuntimePage.test.tsx`.

## Prerequisites and Required Test Data

- Sign in as `admin@example.com` with `Platform Admin` or `Operator`.
- Use environment `Development`.
- Create at least one active agent from Feature 02.
- Suggested agent ID variable: use the first active agent returned by `GET /api/v1/agents`.

## UI Validation Steps

1. Click `Runtime` in the left navigation.
2. Expected URL change: current route changes to `/runtime`.
3. Confirm page title `Runtime` and description `Runtime sessions, execution rings, saga orchestration, sandbox profiles, and kill switch controls.`
4. Confirm summary metrics:
   - `Active Sessions`
   - `Denied Decisions`
   - `Sandbox Profiles`
   - `Kill Switches`
5. In `Runtime Sessions`, start a session:
   - `Agent ID`: an active agent ID
   - `Ring`: `2`
   - `Sponsor`: `user_admin`
6. Click `Start`.
7. Expected UI response:
   - A session row appears.
   - Columns show agent, state, ring, started, ended, and detail.
8. Click the session detail or `Open`.
9. Expected UI response: `Session Timeline` shows metadata for agent, state, and assigned ring.
10. In the action form, enter:
    - `Action`: `claims.read`
    - `Resource`: `runtime-action`
    - `Reversibility`: `full`
    - Leave `Read only` checked if validating a low-risk action, or uncheck it for a stricter action.
    - Leave `Admin` unchecked unless validating privileged behavior.
11. Click `Evaluate`.
12. Expected UI response:
    - An action decision row appears.
    - Decision is allowed or denied with required ring, assigned ring, and reason.
13. In `Ring Decisions`, filter:
    - `Result`: leave blank or choose `allowed` or `denied`
    - `Session`: selected session ID
    - `Agent`: agent ID
    - Click `Filter`
14. Expected UI response: matching ring decisions appear, or empty state `No decisions`.
15. In `Ring Rule Editor`, enter:
    - `Pattern`: `claims.*`
    - `Required Ring`: `2`
    - `Min Trust`: `0`
    - Leave `Enabled` checked.
16. Click `Create`.
17. Expected UI response: rule row appears with pattern, ring, minimum trust, and status.
18. In `Saga Builder`, create a saga:
    - `Name`: `Claims Runtime Saga`
    - `Runtime Session`: selected session ID
    - `Correlation`: `runtime-validation`
19. Click `Create`.
20. Expected UI response: saga row appears, and the saga monitor selects it.
21. In `Saga Monitor`, add a step:
    - `Order`: leave default next order.
    - `Step Name`: `Read claim`
    - `Action`: `claims.read`
    - `Target Agent`: agent ID
    - `Capability`: `claims:read`
    - `Compensation`: `claims.rollback`
    - `Timeout`: `300`
    - `Retries`: `0`
22. Click `Add Step`.
23. Expected UI response: step appears in the steps table.
24. In `Failure Actions`, leave blank for a successful run or enter a step action to simulate failure.
25. Click `Execute / Retry`.
26. Expected UI response:
    - Saga status changes from draft to running, completed, failed, or compensated depending on execution outcome.
    - Events table records execution events.
27. In `Sandbox Profiles`, create a profile:
    - `Name`: `Validation Sandbox`
    - `Provider`: `subprocess`
    - `Allowed Imports`: leave blank or enter `json`
    - `Blocked Imports`: `os, subprocess, socket`
    - `Allowed Paths`: leave blank
    - `Network Egress`: `deny`
    - `Timeout`: `5`
    - `Memory MB`: `128`
28. Click `Create`.
29. Expected UI response:
    - Profile row appears.
    - If selected, the profile may show a provider warning because `subprocess` is not production isolation.
30. Open the profile.
31. In the test form, enter:
    - `Agent ID`: agent ID
    - `Action`: `claims.read`
    - `Sample Code`:

```python
result = {"ok": True}
```

32. Click `Test`.
33. Expected UI response: decision box shows a decision, reason, and violations if any.
34. In `Kill Switch`, prepare an explicit emergency test:
    - `Target Type`: `session`
    - `Target ID`: selected session ID
    - `Scope`: `target`
    - `Reason`: `validation emergency stop`
    - `Confirmation`: `KILL session:<session_id>`
35. Click `Trigger`.
36. Expected UI response:
    - A kill-switch event row appears.
    - Summary metric `Kill Switches` increments.
    - Trust may receive a negative `runtime.kill_switch` signal for related agents.
37. End the session:
    - In `Session Timeline`, enter `validation complete` in `End Reason`.
    - Click `End Session`.
38. Expected UI response: session state becomes ended or archived, and ended time is populated.

## Expected Backend Effects

- Starting a session creates a runtime session with assigned ring and sponsor.
- Action evaluation writes runtime action and ring decision records.
- Ring rule creation persists matching pattern, required ring, minimum trust, and enabled state.
- Saga creation persists saga metadata; adding steps persists ordered step definitions; execution writes saga events.
- Sandbox profile creation persists provider, import/path/network constraints, timeout, and memory settings.
- Sandbox tests execute or simulate code according to provider and return decision, reason, and violations.
- Kill switch validates exact confirmation format `KILL <target_type>:<target_id>`, writes an emergency event, and emits associated runtime/trust effects where implemented.

## Programmatic Verification

```bash
API=http://127.0.0.1:8088
COOKIE=/tmp/ophanix.cookies

curl -s -c "$COOKIE" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","roles":["Platform Admin"]}' \
  "$API/api/v1/auth/dev-login" >/dev/null

AGENT_ID=$(curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/agents" | jq -r '.[0].id')
```

Create a session and evaluate an action:

```bash
SESSION_JSON=$(curl -s -b "$COOKIE" \
  -H 'Content-Type: application/json' \
  -H 'X-Environment-ID: env_default' \
  -d "{\"agent_id\":\"$AGENT_ID\",\"ring\":2,\"sponsor_user_id\":\"user_admin\"}" \
  "$API/api/v1/runtime/sessions")

echo "$SESSION_JSON" | jq
SESSION_ID=$(echo "$SESSION_JSON" | jq -r '.id')

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"action_name":"claims.read","resource_type":"runtime-action","reversibility":"full","is_read_only":true,"is_admin":false}' \
  "$API/api/v1/runtime/sessions/$SESSION_ID/actions" | jq

curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/runtime/ring-decisions?session_id=$SESSION_ID" | jq
```

Create a saga, sandbox profile, and kill-switch event:

```bash
SAGA_JSON=$(curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d "{\"name\":\"Claims Runtime Saga API\",\"runtime_session_id\":\"$SESSION_ID\",\"correlation_id\":\"runtime-validation\"}" \
  "$API/api/v1/runtime/sagas")
SAGA_ID=$(echo "$SAGA_JSON" | jq -r '.id')

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d "{\"step_order\":1,\"name\":\"Read claim\",\"action_name\":\"claims.read\",\"target_agent_id\":\"$AGENT_ID\",\"required_capability\":\"claims:read\",\"compensation_action\":\"claims.rollback\",\"timeout_seconds\":300,\"retry_count\":0}" \
  "$API/api/v1/runtime/sagas/$SAGA_ID/steps" | jq

PROFILE_JSON=$(curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"name":"Validation Sandbox API","provider_type":"subprocess","allowed_imports":["json"],"blocked_imports":["os","subprocess","socket"],"allowed_paths":[],"network_policy":{"egress":"deny"},"resource_limits":{"timeout_seconds":5,"memory_mb":128},"status":"active"}' \
  "$API/api/v1/runtime/sandbox-profiles")
PROFILE_ID=$(echo "$PROFILE_JSON" | jq -r '.id')

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d "{\"agent_id\":\"$AGENT_ID\",\"action_name\":\"claims.read\",\"code\":\"result = {\\\"ok\\\": True}\"}" \
  "$API/api/v1/runtime/sandbox-profiles/$PROFILE_ID/test" | jq

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d "{\"target_type\":\"session\",\"target_id\":\"$SESSION_ID\",\"scope\":\"target\",\"reason\":\"validation emergency stop\",\"confirmation\":\"KILL session:$SESSION_ID\"}" \
  "$API/api/v1/runtime/kill-switch" | jq
```

Focused automated tests:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m unittest \
  tests.test_runtime_sessions_and_rings_overall \
  tests.test_saga_builder_and_monitor_phase3 \
  tests.test_sandbox_profiles_and_kill_switch_phase3 \
  -v

cd frontend
npm test -- RuntimePage.test.tsx
```

## Edge Cases and Alternative Flows

- Kill-switch confirmation mismatch: entering anything except `KILL <target_type>:<target_id>` should fail with a validation message.
- Read-only versus admin actions: unchecking `Read only` or checking `Admin` can increase required ring and may deny the action.
- Sandbox blocked import: include `import os` in `Sample Code`; expected result is a deny or violation for blocked import.
- Saga failure: set `Failure Actions` to a step action and execute; expected result is failed or compensated state with events.
- Ending a session twice: the second end attempt may fail or leave state unchanged.

## Integration Setup Required: Production Sandbox Isolation

Local validation uses the implemented sandbox profile provider options. The `subprocess` provider is not production isolation.

For a production-grade sandbox:

1. Choose a hardened execution provider.
2. Configure allowed imports, blocked imports, filesystem paths, network egress, timeout, and memory limits.
3. Run the profile test with safe sample code.
4. Run a blocked-import test and confirm it is denied.
5. Confirm execution logs and violations are persisted.

Needs verification: production provider configuration and isolation guarantees are environment-specific.

## Troubleshooting

- Session start fails: verify the agent ID exists and the selected role has runtime permissions.
- Decisions are all denied: inspect ring rules and trust score thresholds.
- `Add Step` is disabled: sagas only allow new steps while in draft state.
- Sandbox test fails unexpectedly: inspect provider warning, blocked imports, timeout, and sample code syntax.
- Kill switch fails: verify the confirmation text exactly matches `KILL <target_type>:<target_id>`.
