# Workflow Runner And Artifact Store Completion

## Second-Pass Status

Status: `Audit finding revised` and `Confirmed gap`.

## Implementation Status

Status: `Completed` on 2026-05-01.

Completed work:

- Added persisted `workflow.run` jobs for queued workflow runs.
- Added a workflow worker executor that transitions queued runs/jobs, emits audit events, and stores linked `workflow.output` artifacts.
- Replaced placeholder seeded adapters with deterministic checks for governance, integrity, marketplace, security scan, SBOM, and dependency-confusion workflows.
- Created linked artifact rows for audit exports and generated compliance reports.
- Surfaced linked compliance report artifacts in the compliance report preview.

Validation:

- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_workflow_runner*.py' -v`
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_compliance_phase*.py' -v`
- `node --test test/workflows.test.js test/compliance.test.js`
- `npm run typecheck`
- `npm run lint`
- `npm test`

The first-audit gap is no longer "missing entirely": `2de9148` added workflow run/log migrations, artifact and attestation migrations, workflow/artifact APIs, a frontend workspace, focused tests, and aggregate passing verification. The remaining issue is product completeness. Current workflow execution runs synchronously in the API when `run_immediately` is true, queued runs have no worker-backed executor, most seeded workflow adapters are placeholder "completed" checks instead of the existing CLI/script checks named by the original plan, and generated outputs such as compliance reports and audit exports are not yet stored as checksumed `artifacts` rows.

## Second-Pass Delta Plan

### Goal

Turn the structurally implemented workflow and artifact surfaces into end-to-end product workflows: queued runs should execute through the existing worker runtime, workflow adapters should call real product checks where available, and artifacts produced by workflows, audit exports, and compliance reports should land in the artifact store with links and attestations.

### Evidence

- Implemented: `packages/product-platform/src/product_platform/workflows/*`, `packages/product-platform/src/product_platform/artifacts/*`, migrations `0047` through `0049`, `/api/v1/workflows/*`, `/api/v1/workflow-runs/*`, `/api/v1/artifacts/*`, `frontend/src/workflows.js`, and related tests.
- Remaining gap: `create_workflow_run` in `packages/product-platform/src/product_platform/api/app.py` executes the runner inline for immediate runs and only stores queued runs for cancellation.
- Remaining gap: `build_default_workflow_runner_registry()` uses real policy linting, but governance verify, integrity, marketplace evaluate, security scan, SBOM, and dependency-confusion checks are simple placeholder adapters or print-only shell commands.
- Remaining gap: compliance reports use `compliance-report://...` and audit exports use `audit-export://...` metadata rather than creating artifact records through `ArtifactRepository`.

### Implementation Approach

1. Register a workflow job type with the existing worker runtime so queued workflow runs can be picked up, started, completed, failed, and audited outside the request path.
2. Keep a synchronous test adapter or explicit test flag only for deterministic focused tests.
3. Replace placeholder workflow adapters with real in-process calls or allowlisted CLI/script command vectors for available repo checks.
4. Allow workflow runs to emit output artifacts and automatically link them to `workflow_run`.
5. Store audit exports and generated compliance reports through `ArtifactRepository`, then link them to `audit_export` and `compliance_report` targets.
6. Surface artifact links on compliance report and audit export detail flows as well as workflow detail.

### Likely Files

- `packages/product-platform/src/product_platform/api/app.py`
- `packages/product-platform/src/product_platform/worker/runtime.py`
- `packages/product-platform/src/product_platform/worker/store.py`
- `packages/product-platform/src/product_platform/workflows/runner.py`
- `packages/product-platform/src/product_platform/workflows/repository.py`
- `packages/product-platform/src/product_platform/artifacts/repository.py`
- `packages/product-platform/src/product_platform/compliance/repository.py`
- `packages/product-platform/src/product_platform/compliance/models.py`
- `packages/product-platform/frontend/src/workflows.js`
- `packages/product-platform/frontend/src/compliance.js`
- `packages/product-platform/tests/test_workflow_runner_phase*.py`
- `packages/product-platform/tests/test_compliance_phase*.py`

### Test Plan

- Backend test that a queued workflow run is executed by the worker and transitions through queued/running/succeeded.
- Backend test that an API-created queued run does not execute inline.
- Backend tests for real adapters or allowlisted commands for each seeded command ref.
- Integration test that a workflow output artifact is stored, checksumed, linked to the run, downloadable, and attestable.
- Integration test that audit export and compliance report generation create artifact rows and links.
- Frontend tests that linked artifacts appear from workflow and compliance surfaces.
- Re-run full backend suite with localhost binding and frontend validation.

### Acceptance Criteria

- Workflow execution is worker-backed outside tests.
- Seeded workflow definitions invoke meaningful product checks, not placeholder success messages.
- Product-generated artifacts are durable, checksumed, linked, downloadable, and attestable.
- Existing workflow and artifact APIs remain backward compatible and covered by passing tests.

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
