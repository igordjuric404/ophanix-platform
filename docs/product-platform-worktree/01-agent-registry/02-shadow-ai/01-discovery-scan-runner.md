# Discovery Scan Runner

## Feature Scope

Build the product workflow for configuring and running agent discovery scans. This includes scanner registration, scan targets, manual runs, scheduled runs, run status, logs, and persisted raw findings.

## Existing Repo Assets To Reuse

- Process scanner from `packages/agent-discovery/src/agent_discovery/scanners/process.py`.
- Config scanner from `packages/agent-discovery/src/agent_discovery/scanners/config.py`.
- GitHub scanner from `packages/agent-discovery/src/agent_discovery/scanners/github.py`.
- Discovery models from `packages/agent-discovery/src/agent_discovery/models.py`.

## Out Of Scope

- Reconciliation workflow. Covered by `02-discovery-findings-reconciliation.md`.
- Enterprise cloud/Kubernetes scanners.

## Data Model

Tables:

- `discovery_scanners`: id, organization_id, scanner_type, name, status, config_json.
- `discovery_targets`: id, organization_id, environment_id, scanner_id, target_type, target_value, credentials_ref, schedule_id, enabled.
- `discovery_runs`: id, scanner_id, target_id, status, started_at, finished_at, error_message, summary_json.
- `discovery_raw_findings`: id, run_id, raw_payload_json, fingerprint, created_at.

## API Surface

Implement:

- `GET /api/v1/discovery/scanners`
- `POST /api/v1/discovery/targets`
- `GET /api/v1/discovery/targets`
- `POST /api/v1/discovery/runs`
- `GET /api/v1/discovery/runs`
- `GET /api/v1/discovery/runs/{id}`

## UI Surface

Discovery -> Scan Runs:

- Scanner cards.
- Target table.
- Run history.
- Run detail with logs and raw findings.

Discovery -> Scanner Settings:

- Configure process, config path, and GitHub targets.

## Implementation Phases

### Phase 1: Scanner Registry

Steps:

1. Register built-in scanner types: process, config, GitHub.
2. Expose scanner metadata through API.
3. Validate required config per scanner type.
4. Add scanner availability status.

Tests:

- Unit test scanner registry includes expected built-ins.
- API test scanner list returns metadata.
- Unit test invalid scanner config fails validation.

### Phase 2: Scan Targets

Steps:

1. Add target creation API.
2. Validate config target path for config scanner.
3. Validate GitHub token reference for GitHub scanner.
4. Store target with environment scope.

Tests:

- API test creates config scan target.
- API test invalid target type is rejected.
- API test target is scoped to environment.

### Phase 3: Manual Run Execution

Steps:

1. Add job type for discovery scan.
2. Invoke existing scanner based on target.
3. Persist run state and raw findings.
4. Emit audit event when run starts and completes.

Tests:

- Integration test config scanner run persists findings.
- Integration test failed scan records error.
- Integration test completion emits audit event.

### Phase 4: Scheduled Runs

Steps:

1. Connect targets to background job schedules.
2. Add UI controls for daily/hourly/manual schedule.
3. Prevent overlapping runs for same target.
4. Show next run time.

Tests:

- Unit test overlapping run is skipped.
- Integration test schedule enqueues run.
- Component test target page shows next run.

### Phase 5: Scan Run UI

Steps:

1. Build scan run table.
2. Build run detail drawer/page.
3. Show raw finding count, high-risk count placeholder, duration, errors.
4. Link run to normalized findings after reconciliation feature lands.

Tests:

- Component test run table renders status.
- Component test run detail renders raw findings.
- Component test error state is visible.

## Overall Validation

- Configure a repo path scan.
- Run it from UI.
- Persist raw findings.
- Confirm run appears in scan history and audit events.

## Dependencies

- Background worker.
- Event pipeline.
- Secret store for GitHub token in MVP.

## Definition Of Done

- Discovery scans are no longer manual CLI-only actions.
- Scan runs are persistent, scheduled, auditable, and visible in the UI.
