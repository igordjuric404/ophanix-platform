# Feature 03: Policy Library, Bindings, Simulator, and Evaluation Feed

## Feature Goal and Expected User Outcome

Validate that a policy administrator can import a policy, inspect and edit versions, lint policy content, activate a version, bind the policy to governed targets, simulate decisions, and inspect the evaluation feed.

The expected outcome is a persisted policy with at least one version, an active policy version, a binding, simulator output, and evaluation records visible in the UI and API.

## Implementation Surface

- Frontend route: `/policies`.
- Frontend page: `frontend/src/features/policies/PoliciesPage.tsx`.
- API endpoints include:
  - `GET /api/v1/policies`
  - `POST /api/v1/policies`
  - `GET /api/v1/policies/{policy_id}`
  - `POST /api/v1/policies/import`
  - `POST /api/v1/policies/lint`
  - `POST /api/v1/policies/{policy_id}/versions/draft`
  - `POST /api/v1/policies/{policy_id}/versions/{version_id}/lint`
  - `POST /api/v1/policies/{policy_id}/versions/{version_id}/activate`
  - `POST /api/v1/policies/{policy_id}/versions/{version_id}/rollback`
  - `POST /api/v1/policies/{policy_id}/versions/{version_id}/archive`
  - `GET /api/v1/policies/{policy_id}/export`
  - `GET /api/v1/policies/{policy_id}/affected-resources`
  - `GET /api/v1/policy-bindings`
  - `POST /api/v1/policy-bindings`
  - `PATCH /api/v1/policy-bindings/{binding_id}`
  - `DELETE /api/v1/policy-bindings/{binding_id}`
  - `POST /api/v1/policy-bindings/{binding_id}/promote`
  - `POST /api/v1/policy-bindings/{binding_id}/exceptions`
  - `GET /api/v1/policy-exceptions`
  - `POST /api/v1/policy-evaluations/simulate`
  - `POST /api/v1/policy-evaluations/evaluate`
  - `GET /api/v1/policy-evaluations`
  - `GET /api/v1/policy-evaluations/summary`
  - `GET /api/v1/policy-evaluations/stream`
- Migrations: `0006_policy_library.up.sql`, `0007_policy_lint_results.up.sql`, `0008_policy_bindings.up.sql`, `0042_policy_evaluations.up.sql`.
- Tests: `test_policy_library_*.py`, `test_policy_editor_*.py`, `test_policy_bindings_*.py`, `test_policy_evaluations_*.py`, `frontend/src/features/policies/PoliciesPage.test.tsx`.

## Prerequisites and Required Test Data

- Sign in as `admin@example.com` with `Platform Admin` or `Policy Admin`.
- Use environment `Development`.
- Create or reuse an agent from [Feature 02](feature-02-agent-registry-lifecycle-credentials.md) when binding to an agent target.
- Suggested target ID: the agent ID from Feature 02, or `agent_default` if seeded by a focused test.
- Suggested inline policy body:

```yaml
rules:
  - id: allow-read-claims
    effect: allow
    action: claims.read
```

## UI Validation Steps

1. Click `Policies` in the left navigation.
2. Expected URL change: current route changes to `/policies`.
3. Confirm page title `Policies` and description `Policy library, editor, bindings, simulator, and evaluation feed.`
4. In `Policy Library`, confirm filter fields:
   - `Scope`
   - `Status`
   - `Backend`
   - `Owner`
   - `Tag`
   - Button `Filter`
5. In the import form, enter:
   - `Name`: `Claims Read Guard`
   - `Source path`: `manual://claims-read-guard`
   - `Format`: `yaml`
   - `Scope`: `agent`
   - `Backend`: `native`
   - `Tags`: `claims, validation`
   - Body:

```yaml
rules:
  - id: allow-read-claims
    effect: allow
    action: claims.read
```

6. Click `Import`.
7. Expected UI response: success message `Imported <policy_id>`.
8. Expected URL change: `/policies` changes to `/policies?policy_id=<policy_id>`.
9. Confirm the policy appears in the library table with columns `Name`, `Scope`, `Status`, `Owner`, `Active`, and `Actions`.
10. Click `Open` if the policy is not already selected.
11. In `Version History`, confirm at least one version row appears with columns `Version`, `Backend`, `Status`, `Checksum`, and `Actions`.
12. Click `Lint` in the policy editor.
13. Expected UI response:
    - `Lint Results` updates.
    - Valid content shows a passed state or zero fatal errors.
    - Invalid content shows errors or warnings.
14. Edit the body to add a harmless comment or rule change.
15. Click `Save Version`.
16. Expected UI response: a new version appears in `Version History`.
17. On the new version row, click `Activate`.
18. Expected UI response: message `Policy version activated`; the active version indicator changes to the selected version.
19. In `Bindings`, fill:
    - `Policy`: choose `Claims Read Guard`
    - `Version`: leave `Latest active`
    - `Target Type`: `agent`
    - `Target`: enter the agent ID from Feature 02
    - `Mode`: `shadow`
    - `Rollout`: `100`
    - `Priority`: `0`
20. Click `Create Binding`.
21. Expected UI response:
    - The empty state `No bindings` disappears if this is the first binding.
    - A binding row appears in the matrix.
    - Columns include target, policy, mode, rollout, exceptions, and controls.
22. In the binding row, change promotion controls:
    - Mode: `enforce`
    - Rollout percentage: `100`
    - Reason: `validation promotion`
23. Click `Promote`.
24. Expected UI response: promotion succeeds and binding mode changes to `enforce`.
25. In the exception controls:
    - Reason: `temporary validation exception`
    - Target ID: the same agent ID
    - Target Type: `agent`
    - Leave `No expiry approved` unchecked unless you are explicitly validating permanent exceptions.
26. Click `Exception`.
27. Expected UI response: exception count or exception state for the binding updates.
28. In `Policy Simulator`, fill:
    - `Target Type`: `agent`
    - `Target`: the agent ID
    - `Agent`: the agent ID
    - `Action`: `claims.read`
    - `Resource Type`: `claim`
    - `Resource`: `claim_123`
    - `Context JSON`:

```json
{"purpose":"validation","risk":"low"}
```

29. Click the simulator action button.
30. Expected UI response:
    - A simulator result appears with a decision such as `allow` or `deny`.
    - The result includes reason, policy, matched rule, or default decision details when available.
31. In `Evaluation Feed`, use filters:
    - `Decision`: leave blank, or choose `allow` or `deny`
    - `Mode`: `simulate`
    - `Agent`: the agent ID
    - `Action`: `claims.read`
    - `Policy`: leave blank unless you know the policy ID
    - `Correlation`: leave blank
32. Click the feed filter button.
33. Expected UI response:
    - Summary cards show `Total`, `Decisions`, `Modes`, and `Actions`.
    - Evaluation rows appear.
34. Open an evaluation row.
35. Expected UI response:
    - A detail drawer opens.
    - It shows `Reason`, `Policy`, `Version`, `Matched Rule`, `Resource`, `Latency`, and raw context or metadata.

## Expected Backend Effects

- Import creates a policy and a policy version.
- Lint creates or updates lint result records.
- Activating a version updates active-version state and archives or supersedes previous state according to service rules.
- Creating a binding persists target, policy version, mode, rollout percentage, priority, and exception state.
- Promoting a binding updates binding mode and rollout.
- Creating an exception writes a policy exception associated with the binding.
- Simulator calls create evaluation records in simulate mode.
- Evaluation feed queries persisted decisions and can stream updates via `GET /api/v1/policy-evaluations/stream`.

## Programmatic Verification

```bash
API=http://127.0.0.1:8088
COOKIE=/tmp/ophanix.cookies

curl -s -c "$COOKIE" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","roles":["Policy Admin"]}' \
  "$API/api/v1/auth/dev-login" >/dev/null
```

Import a policy:

```bash
POLICY_JSON=$(curl -s -b "$COOKIE" \
  -H 'Content-Type: application/json' \
  -H 'X-Environment-ID: env_default' \
  -d '{
    "name":"Claims Read Guard API",
    "source_path":"manual://claims-read-guard-api",
    "body_format":"yaml",
    "scope":"agent",
    "backend":"native",
    "tags":["claims","validation"],
    "body_text":"rules:\n  - id: allow-read-claims\n    effect: allow\n    action: claims.read\n"
  }' \
  "$API/api/v1/policies/import")

echo "$POLICY_JSON" | jq
POLICY_ID=$(echo "$POLICY_JSON" | jq -r '.id')
VERSION_ID=$(curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' \
  "$API/api/v1/policies/$POLICY_ID" | jq -r '.versions[0].id // .active_version_id')
```

Lint and activate:

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"body_text":"rules:\n  - id: allow-read-claims\n    effect: allow\n    action: claims.read\n","body_format":"yaml","backend":"native"}' \
  "$API/api/v1/policies/lint" | jq

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"reason":"validation activation"}' \
  "$API/api/v1/policies/$POLICY_ID/versions/$VERSION_ID/activate" | jq
```

Create a binding and simulate:

```bash
AGENT_ID=$(curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/agents" | jq -r '.[0].id')

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d "{
    \"policy_id\":\"$POLICY_ID\",
    \"policy_version_id\":\"$VERSION_ID\",
    \"target_type\":\"agent\",
    \"target_id\":\"$AGENT_ID\",
    \"mode\":\"enforce\",
    \"rollout_percentage\":100,
    \"priority\":0
  }" \
  "$API/api/v1/policy-bindings" | jq

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d "{
    \"target_type\":\"agent\",
    \"target_id\":\"$AGENT_ID\",
    \"agent_id\":\"$AGENT_ID\",
    \"action\":\"claims.read\",
    \"resource_type\":\"claim\",
    \"resource_id\":\"claim_123\",
    \"context\":{\"purpose\":\"validation\",\"risk\":\"low\"}
  }" \
  "$API/api/v1/policy-evaluations/simulate" | jq

curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' \
  "$API/api/v1/policy-evaluations?mode=simulate&agent_id=$AGENT_ID" | jq
```

Focused automated tests:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m unittest \
  tests.test_policy_library_overall \
  tests.test_policy_editor_overall \
  tests.test_policy_bindings_overall \
  tests.test_policy_evaluations_phase3 \
  -v

cd frontend
npm test -- PoliciesPage.test.tsx
```

## Edge Cases and Alternative Flows

- Invalid `Context JSON`: enter a JSON array or malformed JSON in the simulator. Expected result: error text `Context JSON must be an object.` or `Context JSON is invalid.`
- Invalid policy body: enter malformed YAML, Rego, or Cedar and click `Lint`. Expected result: lint errors and `Save Version` disabled if fatal issues exist.
- Empty library: if no policies exist, the UI shows `No policies` and `Import a policy to populate the library.`
- Binding target does not exist: the API may reject the target or allow an unbound target depending on target type. Mark as needs verification for the chosen target.
- Archive active version: archiving or rolling back active versions should update version status and may affect bindings using `Latest active`.

## Integration Setup Required: OPA or Cedar Backends

The UI and API expose `Backend` options `native`, `opa`, and `cedar`. Local validation is confirmed for repository-backed policy records and simulator calls. A real external OPA server or Cedar authorization service was not confirmed as required for local UI validation.

To validate an external policy backend:

1. Provision the backend runtime.
2. Configure its endpoint and credentials in the product-platform environment or integration layer. The exact environment variable names for external OPA/Cedar execution were not confirmed in the current repository.
3. Import a policy with `Backend` set to `opa` or `cedar`.
4. Click `Lint`.
5. Run `POST /api/v1/policy-evaluations/simulate`.
6. Confirm the response identifies the external backend and not the native fallback.

Needs verification: exact external backend configuration keys and runtime decision parity.

## Troubleshooting

- Policy import succeeds but no row is selected: click `Open` on the imported row or confirm the URL has `?policy_id=<id>`.
- Binding form has no target choices: create an agent first or type a known target ID manually.
- Simulator returns an unexpected deny: inspect binding mode, target ID, active version, and policy body.
- Evaluation feed does not update: click the filter button and check `GET /api/v1/policy-evaluations/summary`.
- Version activation fails: make sure the version ID exists and the current user has policy permissions.
