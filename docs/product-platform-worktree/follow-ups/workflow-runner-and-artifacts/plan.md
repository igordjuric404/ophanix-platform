# Workflow Runner And Artifact Store Completion

## Feature Scope

Complete the unfinished workflow and artifact plans from `05-ecosystem-operations/04-workflows`. Existing workflow definitions should become executable product workflows with safe runner controls, persisted logs, audit history, UI, durable artifacts, artifact links, and attestations.

## Existing Repo Assets To Reuse

- `product_platform.workflows.catalog` and `WorkflowRepository`.
- Foundation worker runtime and `workflow_runs` audit event helper.
- Policy linting, discovery scanner, marketplace evaluation, MCP security scan, and root script command references.
- Deployment `LocalArtifactStore` as a starting adapter only.
- Frontend navigation and shared drawer patterns.

## Out Of Scope

- Distributed worker pools or air-gapped execution.
- Rewriting existing CLI tools.
- External WORM storage or external notarization.

## Data Model

Complete or add:

- `workflow_runs`: align with the plan fields: workflow_definition_id, status, inputs_json, started_by, started_at, finished_at, exit_code, summary_json.
- `workflow_logs`: id, workflow_run_id, stream, line_number, message, created_at.
- `artifacts`: id, organization_id, environment_id, artifact_type, name, content_type, storage_uri, checksum, size_bytes, created_by, created_at.
- `artifact_links`: id, artifact_id, target_type, target_id, link_type, created_at.
- `artifact_attestations`: id, artifact_id, attested_by, statement, signature_ref, created_at.

Preserve compatibility with any existing foundation `workflow_runs` table by migrating rather than replacing data destructively.

## API Surface

Implement:

- `POST /api/v1/workflows/{id}/runs`
- `GET /api/v1/workflow-runs`
- `GET /api/v1/workflow-runs/{id}`
- `POST /api/v1/workflow-runs/{id}/cancel`
- `POST /api/v1/artifacts`
- `GET /api/v1/artifacts`
- `GET /api/v1/artifacts/{id}`
- `GET /api/v1/artifacts/{id}/download`
- `POST /api/v1/artifacts/{id}/links`
- `POST /api/v1/artifacts/{id}/attest`

Keep existing `GET /api/v1/workflows`.

## UI Surface

Workflows -> Catalog:

- Workflow cards/table with input-schema driven run forms.

Workflows -> Runs:

- Run list, run detail, logs, status, cancel action.

Workflows -> Artifacts:

- Artifact table, detail, checksum, links, download, attestation history/form.

## Implementation Phases

### Phase 1: Safe Runner Interface

Steps:

1. Implement a runner registry keyed by existing workflow command refs.
2. Prefer in-process Python adapters for available product checks.
3. Shell out only through allowlisted commands with timeout and working directory controls.
4. Capture stdout/stderr line by line.

Tests:

- Unit test unknown workflow cannot execute arbitrary command.
- Integration test registered no-op or policy-lint workflow runs.
- Unit test timeout marks run failed.
- Security test working directory and command refs are allowlisted.

### Phase 2: Run State, Logs, Worker, And Audit

Steps:

1. Add or migrate workflow run/log persistence.
2. Execute runs via the existing worker runtime, with synchronous fallback only for tests.
3. Store status, exit code, summary, and logs.
4. Emit audit events for start, completion, failure, and cancellation.

Tests:

- Integration test run logs are stored in order.
- Integration test failed workflow stores non-zero exit code and summary.
- Integration test audit events are emitted with correlation id.
- API test cancel updates cancellable runs and rejects completed runs.

### Phase 3: Artifact Storage And Links

Steps:

1. Define artifact storage provider interface and local filesystem provider.
2. Calculate checksum, content type, and size before storing metadata.
3. Add artifact upload/list/detail/download APIs.
4. Link artifacts to workflow runs, plugin assessments, audit exports, compliance reports, and evidence items.

Tests:

- Unit test checksum is calculated deterministically.
- Integration test artifact is stored and downloadable.
- Security test path traversal is rejected.
- API test artifact links validate target type.

### Phase 4: Attestations

Steps:

1. Add attestation API requiring a non-empty statement.
2. Store signer user and optional signature reference.
3. Emit audit events for attestations.
4. Display attestation history.

Tests:

- API test attestation requires statement.
- API test unauthorized user cannot attest.
- Integration test attestation emits audit event.

### Phase 5: UI

Steps:

1. Replace `/workflows` placeholder with catalog, run form, runs, logs, artifacts, and attestations.
2. Generate forms from workflow input schemas.
3. Add run detail with logs and linked artifacts.
4. Add artifact detail/download/attestation controls.

Tests:

- Component test catalog renders workflows.
- Component test run form validates input schema.
- Component test run logs render.
- Component test artifact table/detail/download link render.
- Component test attestation form requires statement.
- Frontend validation passes.

## Overall Validation

- Run policy lint from the UI.
- Confirm logs and status are persisted.
- Confirm audit events are emitted.
- Produce or upload an artifact, link it to the workflow run, download it, attest it, and verify attestation audit history.

## Dependencies

- Background worker runtime.
- Event/audit pipeline.
- Compliance report follow-up for report artifact consumers.

## Definition Of Done

- Existing CLI checks are repeatable product workflows with persisted status, logs, artifacts, links, attestations, and audit history.
