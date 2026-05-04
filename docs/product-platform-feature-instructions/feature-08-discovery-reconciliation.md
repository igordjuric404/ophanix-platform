# Feature 08: Discovery and Reconciliation

## Feature Goal and Expected User Outcome

Validate that an operator can run discovery scans, inspect shadow-agent findings, assign owners, reconcile scan runs, register governed agents from findings, suppress findings, and mark findings decommissioned.

The expected outcome is discovery target and run state, finding records with risk and evidence, and reconciliation actions that either create agent registration drafts or update finding status.

## Implementation Surface

- Frontend route: `/discovery`.
- Frontend page: `frontend/src/features/discovery/DiscoveryPage.tsx`.
- API endpoints include:
  - `GET /api/v1/discovery/scanners`
  - `GET /api/v1/discovery/targets`
  - `POST /api/v1/discovery/targets`
  - `PATCH /api/v1/discovery/targets/{target_id}/schedule`
  - `GET /api/v1/discovery/runs`
  - `POST /api/v1/discovery/runs`
  - `GET /api/v1/discovery/runs/{run_id}`
  - `POST /api/v1/discovery/reconcile-run/{run_id}`
  - `GET /api/v1/discovery/findings`
  - `GET /api/v1/discovery/findings/{finding_id}`
  - `POST /api/v1/discovery/findings/{finding_id}/assign-owner`
  - `POST /api/v1/discovery/findings/{finding_id}/register-agent`
  - `POST /api/v1/discovery/findings/{finding_id}/suppress`
  - `POST /api/v1/discovery/findings/{finding_id}/mark-decommissioned`
- Domain modules: `discovery/runner.py`, `discovery/repository.py`, `discovery/findings.py`, `discovery/registry.py`.
- Migrations: `0004_discovery_scan_runner.up.sql`, `0005_discovery_findings_reconciliation.up.sql`.
- Tests: `test_discovery_scan_runner_*.py`, `test_discovery_reconciliation_*.py`, `frontend/src/features/discovery/DiscoveryPage.test.tsx`.

## Prerequisites and Required Test Data

- Sign in as `admin@example.com` with `Platform Admin` or `Operator`.
- Use environment `Development`.
- Use the built-in process, config, or GitHub scanner cards shown on the page.
- Suggested target:
  - `Scanner`: choose an available scanner from the UI.
  - `Source`: `agentmesh.yaml` or a repository/config path supported by the scanner.
  - `Schedule`: manual or hourly depending on UI controls available for the target.

## UI Validation Steps

1. Click `Discovery` in the left navigation.
2. Expected URL change: current route changes to `/discovery`.
3. Confirm page title `Discovery` and description `Run scans, reconcile shadow agents, and turn findings into governed registry work.`
4. Confirm `Scanners` cards are visible and describe built-in process, config, and GitHub scanner availability.
5. In `Targets`, inspect existing targets.
6. If no targets exist, the table shows `No targets`.
7. For an existing target, click `Run now`.
8. Expected UI response:
   - Success message `Discovery run started`.
   - A new row appears in `Scan Runs`.
9. For the same target, click `Hourly`.
10. Expected UI response: success message `Schedule updated`; target schedule or next-run value changes.
11. In `Scan Runs`, open the newest run.
12. Expected UI response:
   - Run table shows run, status, findings, high-risk count, duration, and error.
   - Run detail shows raw findings, or the empty state `No raw findings`.
13. Select a run and click `Reconcile selected`.
14. Expected UI response: success message `Run reconciled`.
15. In `Findings`, set filters:
   - `Risk`: `any`, `critical`, `high`, `medium`, or `low`
   - `Status`: `any`, `shadow_candidate`, `manual_review`, `registered`, or `suppressed`
   - `Source`: `agentmesh.yaml`
   - `Owner`: leave blank or enter `team-a`
   - `Registry`: `any`, `matched`, or `unmatched`
   - `Suppressed`: leave unchecked to see active findings
16. Click `Filter findings`.
17. Expected UI response:
   - Matching findings appear in the table.
   - If none match, the empty state `No active findings` is visible.
18. Open a finding row.
19. Expected UI response:
   - Detail shows risk factors and evidence.
   - Action controls appear for owner assignment, registration, suppression, and decommissioning.
20. In owner assignment, enter:
   - Owner: `owner_1`
21. Click `Assign`.
22. Expected UI response: success message `Owner assigned`; finding owner updates.
23. Click `Register Agent`.
24. Expected UI response:
   - Intended success message is `Registration draft created`.
   - Finding status changes toward registered or linked state.
   - A new agent draft or registry record is available under `/agents`.
   - Needs verification: the current API model requires `sponsor_user_id`, while the current UI action only sends `owner_user_id`. If the UI returns a validation error, use the programmatic verification command below with both owner and sponsor.
25. To validate suppression on a different finding, open an unsuppressed finding.
26. Enter:
   - `Reason`: `validation suppression`
   - `Confirm`: the confirmation value required by the UI
27. Click `Suppress`.
28. Expected UI response: success message `Finding suppressed`; finding leaves active results unless suppressed filter is enabled.
29. To validate decommissioning on a different finding, click `Mark decommissioned`.
30. Expected UI response: success message `Finding decommissioned`; finding status updates.

## Expected Backend Effects

- Running a target creates a discovery run record.
- Scanner execution records raw findings and normalized findings when detected.
- Scheduling updates target recurrence metadata.
- Reconciliation compares findings against registered agents and updates matched/unmatched state.
- Owner assignment updates finding owner metadata.
- Registering a finding creates an agent registration draft or registry-linked work item.
- Suppression records reason and suppressed status; the current UI also requires a `Confirm` field before submitting.
- Marking decommissioned updates finding lifecycle state.

## Programmatic Verification

```bash
API=http://127.0.0.1:8088
COOKIE=/tmp/ophanix.cookies

curl -s -c "$COOKIE" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","roles":["Platform Admin"]}' \
  "$API/api/v1/auth/dev-login" >/dev/null
```

List scanners, create a target if needed, and run a target:

```bash
curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/discovery/scanners" | jq
SCANNER_TYPE=$(curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/discovery/scanners" | jq -r '.[0].scanner_type')

curl -s -b "$COOKIE" \
  -H 'Content-Type: application/json' \
  -H 'X-Environment-ID: env_default' \
  -d "{\"scanner_type\":\"$SCANNER_TYPE\",\"target_type\":\"config\",\"target_value\":\"agentmesh.yaml\",\"enabled\":true,\"config_json\":{}}" \
  "$API/api/v1/discovery/targets" | jq

TARGET_ID=$(curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/discovery/targets" | jq -r '.[0].id')

RUN_JSON=$(curl -s -b "$COOKIE" \
  -H 'Content-Type: application/json' \
  -H 'X-Environment-ID: env_default' \
  -d "{\"target_id\":\"$TARGET_ID\"}" \
  "$API/api/v1/discovery/runs")

echo "$RUN_JSON" | jq
RUN_ID=$(echo "$RUN_JSON" | jq -r '.id')

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{}' "$API/api/v1/discovery/reconcile-run/$RUN_ID" | jq
```

Inspect and act on findings:

```bash
curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/discovery/findings" | jq

FINDING_ID=$(curl -s -b "$COOKIE" -H 'X-Environment-ID: env_default' "$API/api/v1/discovery/findings" | jq -r '.[0].id')

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"owner_user_id":"owner_1"}' \
  "$API/api/v1/discovery/findings/$FINDING_ID/assign-owner" | jq

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -H 'X-Environment-ID: env_default' \
  -d '{"owner_user_id":"owner_1","sponsor_user_id":"user_admin"}' \
  "$API/api/v1/discovery/findings/$FINDING_ID/register-agent" | jq
```

Focused automated tests:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m unittest \
  tests.test_discovery_scan_runner_overall \
  tests.test_discovery_reconciliation_overall \
  -v

cd frontend
npm test -- DiscoveryPage.test.tsx
```

## Edge Cases and Alternative Flows

- No targets: use API or seed data to create a target before running scans. The current UI primarily operates on listed targets.
- Scanner unavailable: scanner card should indicate availability; runs may fail with an error in `Scan Runs`.
- No findings: successful scans can still produce no findings. Validate empty states and run detail.
- Suppressed findings hidden: enable the suppressed filter to find them again.
- Registering an already matched finding: expected behavior is to reject duplicate registration or link to existing agent; verify response before claiming a new draft.

## Integration Setup Required: GitHub or External Source Scanner

Built-in scanner cards are visible locally. External scanners require source access:

1. Configure credentials for the source system, such as a GitHub token, through the deployment or integration secret system.
2. Add or seed a discovery target pointing at the repository, config path, process list, or source URL.
3. Run the target manually.
4. Confirm the run status is successful.
5. Confirm raw findings include source evidence.
6. Reconcile the run and confirm findings are matched or unmatched against the agent registry.

Needs verification: exact credential variable names and scanner source formats for production GitHub scans were not confirmed from the current UI alone.

## Troubleshooting

- `Run now` does nothing visible: refresh `Scan Runs` and query `GET /api/v1/discovery/runs`.
- Findings do not appear: clear filters, include suppressed findings, and inspect the selected run detail.
- Register Agent fails: assign an owner first and confirm sponsor/owner IDs are valid.
- Register Agent fails from the UI with a validation error: this likely means the backend required `sponsor_user_id`; retry the API command that includes both `owner_user_id` and `sponsor_user_id`.
- Reconciliation result seems wrong: compare finding evidence to existing `/agents` records and check registry match status.
