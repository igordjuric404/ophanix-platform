# Background Worker Runtime

## Feature Scope

Create the shared worker runtime for scheduled scans, trust recalculation, credential rotation, compliance reports, workflow runs, health checks, and demo scenarios.

## Existing Repo Assets To Reuse

- Existing CLI functions in `packages/agent-compliance`.
- Discovery scanners in `packages/agent-discovery`.
- Agent SRE managers in `packages/agent-sre`.
- Marketplace evaluation functions in `packages/agent-marketplace`.

## Out Of Scope

- Implementing individual jobs. Each feature plan defines its own jobs.
- Building a full distributed scheduler. MVP can start simple.

## Data Model

Tables:

- `background_jobs`: id, organization_id, environment_id, job_type, status, payload_json, scheduled_at, started_at, finished_at, attempts, max_attempts, error_message.
- `job_runs`: id, job_id, status, logs_json, metrics_json, created_at.
- `job_schedules`: id, organization_id, environment_id, job_type, cron_expression, payload_json, enabled, last_run_at, next_run_at.

## API Surface

Implement:

- `POST /api/v1/jobs`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{id}`
- `POST /api/v1/jobs/{id}/cancel`
- `POST /api/v1/job-schedules`
- `GET /api/v1/job-schedules`
- `PATCH /api/v1/job-schedules/{id}`

## UI Surface

Shared Workflows and Settings pages:

- Job list.
- Schedule editor.
- Run logs.
- Retry and cancel actions.

## Implementation Phases

### Phase 1: Queue And Worker Process

Steps:

1. Choose Redis-backed job library or implement a minimal queue abstraction.
2. Add worker entrypoint.
3. Add job registration mechanism by job type.
4. Add graceful shutdown.

Tests:

- Unit test job registry resolves known job type.
- Integration test enqueues job and worker executes it.
- Integration test unknown job type fails with clear error.

### Phase 2: Persistent Job State

Steps:

1. Add job tables.
2. Store status transitions: queued, running, succeeded, failed, canceled.
3. Capture logs and result metadata.
4. Add retry count and max attempts.

Tests:

- Integration test job state transitions.
- Integration test failed job records error message.
- Integration test retry increments attempt count.

### Phase 3: Scheduling

Steps:

1. Add schedule table and scheduler loop.
2. Support interval and cron expressions.
3. Prevent duplicate scheduled runs.
4. Add enabled/disabled switch.

Tests:

- Unit test next-run calculation.
- Integration test disabled schedule does not enqueue.
- Integration test duplicate prevention for same schedule and time.

### Phase 4: API And UI Hooks

Steps:

1. Add job API routes.
2. Add permissions for running and canceling jobs.
3. Publish job events to audit pipeline.
4. Expose logs and result summary for UI pages.

Tests:

- API test Operator can create allowed job.
- API test Viewer cannot cancel job.
- API test job completion emits audit event.

## Overall Validation

- Run a no-op demo job from API.
- Observe job state in DB.
- Receive job audit events.
- Cancel a pending job and verify it does not execute.

## Dependencies

- Redis.
- Product database.
- Event and audit pipeline.
- Auth and RBAC.

## Definition Of Done

- Feature teams can register jobs without inventing worker infrastructure.
- Jobs are persistent, observable, retryable, and auditable.
