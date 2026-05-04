# Demo Environment Reset

## Feature Scope

Build reset behavior for the local demo environment. The reset clears scenario-generated state, reloads seed policies and fixtures, preserves admin/system configuration, and returns the UI to a known baseline.

## Existing Repo Assets To Reuse

- Seed data from scenario runner.
- Existing example policies and demo fixtures.

## Out Of Scope

- Production tenant deletion.
- Full database wipe.

## Data Model

Tables:

- `demo_reset_runs`: id, organization_id, environment_id, status, requested_by, started_at, finished_at, summary_json.
- Add `demo_run_id` or `is_demo_seed` markers to demo-created records where safe.

## API Surface

Implement:

- `POST /api/v1/demo/reset`
- `GET /api/v1/demo/reset-runs`
- `GET /api/v1/demo/reset-runs/{id}`
- `GET /api/v1/demo/baseline-status`

## UI Surface

Demo Lab -> Reset Environment.

Demo Lab -> Prerequisites.

## Implementation Phases

### Phase 1: Reset Scope Definition

Steps:

1. Define which tables are cleared for demo reset.
2. Define which records are preserved: users, orgs, environments, system settings, connector credentials unless explicitly requested.
3. Add demo markers to scenario-created resources.
4. Document reset order.

Tests:

- Unit test reset scope includes expected demo tables.
- Unit test preserved tables are excluded.
- Integration test demo marker can be queried.

### Phase 2: Reset Job

Steps:

1. Add reset job to background worker.
2. Delete or archive demo-created records in dependency order.
3. Reload seed policies, agents optional, fixtures, MCP server registration optional.
4. Emit high-level audit event.

Tests:

- Integration test reset clears demo audit events but preserves admin user.
- Integration test reset reloads seed scenario.
- Integration test reset is idempotent.

### Phase 3: Baseline Status

Steps:

1. Add baseline status endpoint.
2. Check seed policy pack, demo scenario, MCP server, sample agents, provider credential status.
3. Return missing/degraded items.
4. Use same checks in prerequisites UI.

Tests:

- API test baseline healthy after reset.
- API test missing MCP server returns degraded.
- Component test prerequisites show degraded status.

### Phase 4: UI

Steps:

1. Build reset page with scope summary.
2. Require typed confirmation.
3. Show reset progress and result summary.
4. Link to scenario catalog after reset.

Tests:

- Component test reset requires typed confirmation.
- Component test reset progress renders.
- Component test result summary shows cleared and seeded counts.

## Overall Validation

- Run demo scenario.
- Reset environment.
- Confirm scenario-generated resources are cleared.
- Confirm seed data is restored.
- Confirm admin/settings are preserved.

## Dependencies

- Scenario runner.
- Background worker.
- Database schema.

## Definition Of Done

- Sales/demo users can reliably return the environment to a known state.
