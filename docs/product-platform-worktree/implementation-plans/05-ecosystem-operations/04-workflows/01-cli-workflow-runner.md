# CLI Workflow Runner

## Feature Scope

Turn existing CLI and script checks into product workflows. Users can run policy lint, governance verify, integrity checks, discovery scans, marketplace evaluation, SBOM generation, and security scans from the UI/API with persisted logs and status.

## Existing Repo Assets To Reuse

- `agt` CLI from `packages/agent-compliance`.
- Root scripts such as security scan, SBOM generation, dependency confusion check.
- Marketplace CLI commands.
- Discovery CLI/scanner functions.

## Out Of Scope

- Rewriting CLI tools.
- Distributed runner and air-gapped execution.

## Data Model

Tables:

- `workflow_definitions`: id, organization_id, name, workflow_type, command_ref, input_schema_json, enabled.
- `workflow_runs`: id, workflow_definition_id, status, inputs_json, started_by, started_at, finished_at, exit_code, summary_json.
- `workflow_logs`: id, workflow_run_id, stream, line_number, message, created_at.

## API Surface

Implement:

- `GET /api/v1/workflows`
- `POST /api/v1/workflows/{id}/runs`
- `GET /api/v1/workflow-runs`
- `GET /api/v1/workflow-runs/{id}`
- `POST /api/v1/workflow-runs/{id}/cancel`

## UI Surface

Workflows -> Catalog.

Workflows -> Runs.

Workflows -> Schedules.

## Implementation Phases

### Phase 1: Workflow Catalog

Steps:

1. Seed workflow definitions for governance verify, integrity, policy lint, security scan, SBOM, dependency confusion, marketplace evaluate.
2. Store input schema per workflow.
3. Add API to list workflows.

Tests:

- Integration test seed is idempotent.
- API test workflow list includes expected definitions.
- Unit test input schema validates required fields.

### Phase 2: Safe Runner Interface

Steps:

1. Implement runner interface that calls Python functions where available before shelling out.
2. Restrict command refs to registered workflows only.
3. Capture stdout/stderr line by line.
4. Set timeout and working directory allowlist.

Tests:

- Unit test unknown workflow cannot execute arbitrary command.
- Integration test no-op registered workflow runs.
- Unit test timeout marks run failed.

### Phase 3: Run State And Logs

Steps:

1. Add run and log tables.
2. Execute runs through background worker.
3. Store status, exit code, summary.
4. Emit audit event for run start/completion/failure.

Tests:

- Integration test run logs are stored.
- Integration test failed workflow stores exit code.
- Integration test audit events emitted.

### Phase 4: UI

Steps:

1. Build workflow catalog.
2. Build run form from input schema.
3. Build run detail with logs.
4. Add cancel action.

Tests:

- Component test catalog renders workflows.
- Component test run form validates input.
- Component test logs stream or refresh.

## Overall Validation

- Run policy lint workflow from UI.
- See logs and result.
- Confirm run appears in audit events.
- Use output as evidence in compliance plan later.

## Dependencies

- Background worker.
- Event pipeline.
- Artifact store for workflow outputs.

## Definition Of Done

- Existing CLI checks become repeatable product workflows with logs and audit history.
