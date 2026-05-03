# Frontend Legacy Retirement And Migration Notes

## Feature Scope

Complete the cross-cutting frontend refactor cleanup after the React/Vite migration. The active app should be unambiguously React/TypeScript, obsolete vanilla JavaScript page modules should be removed or explicitly archived, and operators/developers should have concise migration notes for local, Docker demo, and cloud frontend workflows.

## Existing Repo Assets To Reuse

- React frontend under `packages/product-platform/frontend/src/app`, `src/features`, `src/api`, `src/components`, and `src/lib`.
- Legacy vanilla modules under `packages/product-platform/frontend/src/*.js`.
- Legacy tests under `packages/product-platform/frontend/test/*.test.js`.
- `packages/product-platform/frontend/REFACTOR_PLAN.md`.
- Refactor execution logs in `docs/frontend-refactor-execution-log`.

## Out Of Scope

- Redesigning product workflows.
- Rewriting backend APIs.
- Removing product behavior that is not yet covered by React tests.
- Replacing the Vite/TanStack framework choices.

## Data Model

No data model changes.

## API Surface

No API changes. Preserve all existing endpoint paths and `credentials: "include"` session behavior.

## UI Surface

No user-visible feature changes are required. The expected user-visible result is unchanged product behavior through the React routes.

## Implementation Phases

### Phase 1: Active Reference Inventory

Steps:

1. Confirm `index.html`, Vite, Docker, and `start.sh` only activate `src/main.tsx`.
2. Use static search to find imports or runtime references to legacy modules.
3. Map each legacy test file to equivalent React/Vitest coverage or identify missing behavior.
4. Document any intentional archive decision before deleting code.

Tests:

- `npm run typecheck`.
- `npm run lint`.
- `npm test`.

### Phase 2: Move Remaining Unique Coverage

Steps:

1. Port any legacy-only behavioral assertions into focused Vitest/RTL tests.
2. Keep the tests behavior-oriented: route rendering, user actions, API paths, payload normalization, and error/empty states.
3. Avoid duplicating low-value string-rendering tests from the old modules.

Tests:

- Focused Vitest tests for affected feature pages.
- `npm run validate`.

### Phase 3: Retire Legacy Modules

Steps:

1. Delete obsolete `src/*.js` page/render/router/state modules once coverage is preserved.
2. Delete or archive legacy `frontend/test/*.test.js` files.
3. Remove or repurpose `npm run test:legacy` so default validation only exercises the active React app.
4. Ensure no generated build or Docker path expects the deleted modules.

Tests:

- `npm run validate`.
- `npm run test:e2e` with localhost binding allowed.
- `/usr/bin/env PYTHONPATH=src python3 -m unittest discover -s tests -v` from `packages/product-platform`.

### Phase 4: Migration Notes

Steps:

1. Add `packages/product-platform/frontend/MIGRATION_NOTES.md`.
2. Cover what changed, local dev commands, test commands, Docker/demo behavior, cloud frontend build behavior, and intentionally preserved limitations.
3. Link to the refactor execution log for detailed phase history.

Tests:

- Documentation links and commands are accurate against current `package.json`, `start.sh`, and Docker files.

## Overall Validation

- Active frontend source no longer contains obsolete page/render/router modules unless explicitly archived.
- React validation and browser smoke pass.
- Backend validation still passes.
- Migration notes accurately describe how to run and test the migrated app.

## Dependencies

- All main React routes should remain green before deleting legacy code.
- Policy live feed and observability chart follow-ups may add tests that should be preserved during cleanup.

## Definition Of Done

- The repository has a single active frontend architecture.
- Legacy render helpers cannot drift silently from the product UI.
- Developers can understand the migration, runtime, and test commands from concise checked-in notes.

