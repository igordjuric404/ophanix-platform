# Integrations Frontend And Demo Seed Regression Recovery

## Second-Pass Status

Status: `Obsolete follow-up`.

The first-audit regression is resolved in `2de9148`: generic seed data no longer inserts demo baseline agents/MCP fixtures by default, Demo Lab reset explicitly restores baseline fixtures, the integrations frontend exports and route are complete enough for the existing app handlers/tests, and the backend/frontend aggregate suites pass when localhost socket binding is allowed for local-demo tests. This plan is retained as historical context only.

## Feature Scope

Restore HEAD verification after `05-ecosystem-operations` and `06-demo-delivery` by fixing integration frontend completeness and isolating demo baseline seed data so it does not break earlier agent and integration tests. This plan does not add new product scope beyond making the committed features coherent and verifiable.

## Existing Repo Assets To Reuse

- `product_platform.db.seed.seed_demo_data` and Demo Lab baseline checks.
- Integration backend repositories, APIs, and tests.
- `frontend/src/integrations.js`, `frontend/src/app.js`, and `frontend/test/integrations.test.js`.
- Agent inventory/registration tests and integration connector tests that currently expose regressions.

## Out Of Scope

- Implementing workflow runner/artifact store.
- Changing product API contracts unnecessarily.
- Weakening tests by deleting meaningful assertions.

## Data Model

No new data model should be required. If seed isolation needs metadata, prefer existing demo identifiers and fixture helpers over new columns.

## API Surface

No new API surface is expected. Existing integration APIs and agent APIs should keep their contracts.

## UI Surface

Complete the existing Integrations route so it renders:

- Framework catalog.
- Connector instance form/table.
- Linked agents table/actions.
- Provider credentials table/actions.
- Health checks table/remediation.

The route should match existing `app.js` event handlers and frontend tests.

## Implementation Phases

### Phase 1: Seed Boundary Audit

Steps:

1. Identify which tests and product flows require demo baseline agents.
2. Split baseline fixture seeding from generic org/admin/policy/framework/workflow seeding when tests or non-demo code only need generic seed data.
3. Keep Demo Lab reset/baseline flows able to seed required agents/MCP fixtures explicitly.
4. Preserve idempotency.

Tests:

- Focused test proving `seed_demo_data()` no longer leaks demo agents into generic agent inventory tests, or update tests to call the narrower seed helper.
- Focused test proving Demo Lab reset still restores healthy baseline fixtures.
- Regression test for duplicate `Demo Support Agent` registration scenario.

### Phase 2: Backend Suite Regression Fixes

Steps:

1. Fix agent inventory phase 1 expectations by removing unintended demo fixture leakage, not by loosening filters.
2. Fix agent registration overall conflict with `Demo Support Agent`.
3. Fix framework connector and provider health tests that collide with seeded demo agent names.
4. Confirm tenant/environment scoping remains strict.

Tests:

- `test_agent_inventory_phase1.py`
- `test_agent_registration_overall.py`
- `test_framework_connector_registry_phase3.py`
- `test_framework_connector_registry_overall.py`
- `test_provider_secrets_health_overall.py`

### Phase 3: Integrations Frontend Completion

Steps:

1. Add or rename exports in `frontend/src/integrations.js` to satisfy current tests and `app.js` imports.
2. Render connector forms, linked agents, provider credentials, and health checks using existing frontend style.
3. Add payload helpers for connector instances, agent links, and provider credentials.
4. Avoid showing raw secret values.

Tests:

- `node --test test/integrations.test.js`
- `npm run typecheck`
- `npm run lint`

### Phase 4: Aggregate Verification

Steps:

1. Run the full backend unittest suite.
2. Run focused local demo socket tests with socket binding allowed when needed.
3. Run frontend `npm run validate`.
4. Update any execution/audit notes if the seed behavior changes how Demo Lab baseline is prepared.

Tests:

- `PYTHONPATH=src python3 -m unittest discover -s tests -v`
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_local_demo_compose_phase2.py' -v`
- `npm run validate`

## Overall Validation

- Full backend suite is green except for clearly documented environment-only constraints.
- Frontend validation is green.
- Demo Lab baseline remains healthy after reset and seed.
- Agent and integration tests no longer see accidental demo fixture state.

## Dependencies

- Demo Lab reset/baseline implementation.
- Integration backend APIs and frontend route.

## Definition Of Done

- HEAD can be verified end-to-end without demo fixture leakage or broken integration frontend imports.
