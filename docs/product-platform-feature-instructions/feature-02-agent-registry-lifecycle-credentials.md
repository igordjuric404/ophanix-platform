# Feature 02: Agent Registry, Lifecycle, and Credentials

## Feature Goal and Expected User Outcome

Validate that an operator can register an agent draft, see it in inventory, approve and activate it, inspect lifecycle and audit state, issue credentials, rotate or revoke credentials, and run orphan detection.

The expected outcome is an agent visible on `/agents`, with persisted registry data, lifecycle transitions, and credential records available through both the UI and API.

## Implementation Surface

- Frontend route: `/agents`.
- Frontend page: `frontend/src/features/agents/AgentsPage.tsx`.
- API endpoints include:
  - `POST /api/v1/agents/registration-drafts`
  - `PATCH /api/v1/agents/registration-drafts/{draft_id}`
  - `POST /api/v1/agents/registration-drafts/{draft_id}/identity`
  - `POST /api/v1/agents/registration-drafts/{draft_id}/simulate`
  - `POST /api/v1/agents/registration-drafts/{draft_id}/submit`
  - `GET /api/v1/agents`
  - `GET /api/v1/agents/{agent_id}`
  - `POST /api/v1/agents/{agent_id}/approve`
  - `POST /api/v1/agents/{agent_id}/activate`
  - `POST /api/v1/agents/{agent_id}/suspend`
  - `POST /api/v1/agents/{agent_id}/resume`
  - `POST /api/v1/agents/{agent_id}/decommission`
  - `POST /api/v1/agents/{agent_id}/heartbeat`
  - `GET /api/v1/agents/{agent_id}/timeline`
  - `GET /api/v1/agents/{agent_id}/audit`
  - `POST /api/v1/agents/orphan-detection/run`
  - `GET /api/v1/agents/{agent_id}/credentials`
  - `POST /api/v1/agents/{agent_id}/credentials`
  - `POST /api/v1/credentials/{credential_id}/rotate`
  - `POST /api/v1/credentials/{credential_id}/revoke`
  - `POST /api/v1/credentials/{credential_id}/verify`
  - `GET /api/v1/credentials/expiring`
- Domain modules: `agents/repository.py`, `agents/lifecycle.py`, `agents/identity.py`, `agents/credentials.py`, `agents/simulation.py`.
- Migrations: `0002_agent_registry.up.sql`, `0003_agent_credentials.up.sql`.
- Tests: `test_agent_registration_*.py`, `test_agent_inventory_*.py`, `test_lifecycle_workflows.py`, `test_credential_*.py`, `frontend/src/features/agents/AgentsPage.test.tsx`.

## Prerequisites and Required Test Data

- Sign in as `admin@example.com` with `Platform Admin`.
- Confirm environment `Development` is selected.
- Start from `/agents`.
- Suggested test values:
  - Name: `Claims Assistant`
  - Owner: `owner_1`
  - Sponsor: `sponsor_1`
  - Framework: `langgraph`
  - Runtime: `service`
  - Endpoint: `https://agent.example.test`
  - Capability: `claims:read`
  - Resource: `claim`
  - Policy pack: `baseline`
  - Description: `Governed agent registration draft`

## UI Validation Steps

1. Click `Agents` in the left navigation.
2. Expected URL change: current route changes to `/agents`.
3. Confirm page title `Agents` and description `Register, inspect, operate, and credential governed agents.`
4. In `Register Agent`, confirm the wizard step labels are visible:
   - `Agent Details`
   - `Runtime And Framework`
   - `Identity`
   - `Capabilities`
   - `Policies`
   - `Bootstrap`
5. Fill the registration form:
   - `Name`: `Claims Assistant`
   - `Owner`: `owner_1`
   - `Sponsor`: `sponsor_1`
   - `Framework`: `langgraph`
   - `Runtime`: `service`
   - `Endpoint`: `https://agent.example.test`
   - `Capability`: `claims:read`
   - `Resource`: `claim`
   - `Policy pack`: `baseline`
   - `Description`: `Governed agent registration draft`
6. Click `Create draft`.
7. Expected UI response: a success message like `Registration draft <id> created`.
8. In `Inventory`, use filters if needed:
   - `Status`: leave blank or enter the created status if known.
   - `Capability`: `claims:read`
   - `Sort`: `-last_heartbeat`
   - Click `Filter`.
9. Expected UI response:
   - If the table was empty before, the empty state `No agents registered` disappears.
   - A row for `Claims Assistant` appears.
   - Columns include `Name`, `Status`, `Framework`, `Owner`, `Trust`, `Credential`, `Heartbeat`, `Capabilities`, and `Actions`.
10. Click `Open` on the `Claims Assistant` row.
11. Expected URL change: `/agents` changes to `/agents?agent_id=<agent_id>`.
12. In the detail workspace, confirm tabs:
    - `Overview`
    - `Identity`
    - `Credentials`
    - `Lifecycle`
    - `Audit`
    - `Runtime`
    - `Policies`
    - `Trust`
    - `Integrations`
13. In `Overview`, confirm values for status, owner, sponsor, framework, credential, last heartbeat, and capabilities.
14. Before clicking `Approve`, confirm the agent status is `pending_approval`.
15. Needs verification: the current UI creates a draft but does not expose the implemented identity creation and submit actions required to move a draft from `draft` to `pending_approval`. If the agent is still `draft`, run the programmatic identity and submit commands below, then refresh `/agents?agent_id=<agent_id>`.
16. Click `Approve`.
17. Expected UI response: message `Agent approved`; status changes from `pending_approval` to `provisioned`.
18. Click `Activate`.
19. Expected UI response: message `Agent activated`; inventory status becomes `active`.
20. Click the `Identity` tab.
21. Expected UI response:
    - `DID` shows either an issued identifier or `Not issued`.
    - Public key fingerprint, key type, and identity status are displayed if identity has been issued.
22. Click the `Credentials` tab.
23. If the table is empty, confirm empty state `No credentials`.
24. Click `Issue`.
25. Expected UI response:
    - A credential row appears.
    - The agent credential status updates away from `missing` or `not issued`.
    - Columns include credential, status, issuer, expiry, scopes, and actions.
26. On the credential row, click `Rotate`.
27. Expected UI response: rotation succeeds and the row remains visible with updated credential metadata.
28. In the `Revoke` form, enter reason `validation cleanup`.
29. Click `Revoke`.
30. Expected UI response: credential status changes to revoked or no longer verifies as valid.
31. Click `Lifecycle`.
32. In `Reason`, enter `validation suspend`.
33. Click `Suspend`.
34. Expected UI response: agent status changes to suspended and a lifecycle event is recorded.
35. Click `Run orphan detection`.
36. Expected UI response:
    - Orphan detection completes.
    - The `Lifecycle Workspace` `Orphan Candidates` panel either lists candidates or shows `No orphan candidates`.
37. Click `Audit`.
38. Expected UI response:
    - Audit events for registration, approval, activation, credential issuance, rotation, revocation, and lifecycle changes may be visible.
    - If no records match the selected agent, the tab shows `No audit events`.

## Expected Backend Effects

- Registration creates agent registry data in the agent tables and may create registration-draft lifecycle records.
- Approval and activation update the persisted agent status.
- Lifecycle actions write lifecycle/timeline records.
- Credential issuance creates a credential record with issuer metadata and scopes.
- Credential rotation creates a replacement or rotation event and updates credential state.
- Credential revocation updates credential status and records a reason.
- Orphan detection scans registered agents and records detection results.
- Audit events are emitted for security-sensitive actions where the implementation has audit hooks.

## Programmatic Verification

Authenticate first:

```bash
API=http://127.0.0.1:8088
COOKIE=/tmp/ophanix.cookies

curl -s -c "$COOKIE" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","roles":["Platform Admin"]}' \
  "$API/api/v1/auth/dev-login" >/dev/null
```

Create a registration draft:

```bash
DRAFT_JSON=$(curl -s -b "$COOKIE" \
  -H 'Content-Type: application/json' \
  -H 'X-Environment-ID: env_default' \
  -d '{
    "name":"Claims Assistant API",
    "description":"Governed agent registration draft",
    "framework":"langgraph",
    "runtime_type":"service",
    "endpoint_url":"https://agent.example.test",
    "owner_user_id":"owner_1",
    "sponsor_user_id":"sponsor_1"
  }' \
  "$API/api/v1/agents/registration-drafts")

echo "$DRAFT_JSON" | jq
AGENT_ID=$(echo "$DRAFT_JSON" | jq -r '.id')

curl -s -b "$COOKIE" \
  -H 'Content-Type: application/json' \
  -H 'X-Environment-ID: env_default' \
  -d '{
    "capabilities":[{"capability_name":"claims:read","resource_type":"claim"}]
  }' \
  "$API/api/v1/agents/registration-drafts/$AGENT_ID" | jq
```

Inspect the draft:

```bash
curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' \
  "$API/api/v1/agents/$AGENT_ID" | jq '{id,name,status,framework,credential_status}'
```

Create identity, submit, approve, activate, issue credentials, and inspect:

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{}' \
  "$API/api/v1/agents/registration-drafts/$AGENT_ID/identity" | jq

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{}' \
  "$API/api/v1/agents/registration-drafts/$AGENT_ID/submit" | jq '{id,status}'

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"reason":"validation approval"}' \
  "$API/api/v1/agents/$AGENT_ID/approve" | jq '{id,status}'

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"reason":"validation activation"}' \
  "$API/api/v1/agents/$AGENT_ID/activate" | jq '{id,status}'

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"issuer":"local-agentmesh","scopes":[{"scope":"claims:read","resource_type":"claim","resource_id":"claim"}]}' \
  "$API/api/v1/agents/$AGENT_ID/credentials" | jq

curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' \
  "$API/api/v1/agents/$AGENT_ID/credentials" | jq
```

Focused automated tests:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m unittest \
  tests.test_agent_registration_overall \
  tests.test_agent_inventory_phase1 \
  tests.test_lifecycle_workflows \
  tests.test_credential_overall \
  -v

cd frontend
npm test -- AgentsPage.test.tsx
```

## Edge Cases and Alternative Flows

- Missing required registration fields: leave `Name`, `Owner`, or `Sponsor` blank and click `Create draft`. Expected result is client-side or API validation and no created draft.
- Invalid endpoint: enter a non-URL endpoint. The API may reject the draft depending on schema validation.
- Empty inventory: if no agents exist, the table shows `No agents registered` and `Register Agent to create the first governed registry record.`
- Draft approval: approving a `draft` agent directly should fail with an invalid transition. Create identity and submit the draft first so status becomes `pending_approval`.
- Approve without sufficient permission: sign in as `Viewer` and open `/agents`; restricted actions should be disabled or blocked by the API.
- Credential revocation without reason: the revoke API should reject missing required reason text.
- Orphan detection with no orphaned agents: the UI should show `No orphan candidates`.

## Troubleshooting

- Created draft does not appear: clear filters, then call `GET /api/v1/agents` with `X-Environment-ID: env_default`.
- `Open` does not change the detail panel: confirm the URL includes `?agent_id=<id>` and the API returns `GET /api/v1/agents/{id}`.
- `Approve` fails after using only the registration form: create identity and submit the draft through the API, then refresh the page and retry.
- Credential issue fails: verify the agent is approved or active and the current user has a role with credential permissions.
- Lifecycle actions fail: confirm the agent status allows the transition. For example, already suspended agents may need `Resume` before another suspend flow.
- Audit tab is empty: use the global Compliance guide to query `/api/v1/audit/events` and confirm audit records were emitted for the action.
