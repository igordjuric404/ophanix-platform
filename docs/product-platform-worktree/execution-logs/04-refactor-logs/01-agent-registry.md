# 01 Agent Registry Refactor

## Phase Overview

| Phase | Goal | Status | Key Checklist Items |
| --- | --- | --- | --- |
| 00-framework-foundation | Establish React, TypeScript, Vite, TanStack Router/Query, Tailwind, shadcn-style UI primitives, Vitest, RTL, Playwright, ESLint, and Prettier as the shared frontend foundation. | Done | Framework stack, app entry, router, query client, API/auth foundation, runtime/Docker wiring. |
| 00-platform-foundation | Refactor platform shell/navigation, auth/tenant context, system status, permission-aware navigation, and shared detail drawers into React. | Done | Tenant/status shell, route RBAC, access denied, shared drawer framework, audit drawers, validation. |
| 01-agent-registry | Refactor agent registry and discovery workflows into React. | Done | Read prior logs, migrate Agents registration/inventory/detail/lifecycle/credentials, migrate Discovery scan runner/reconciliation, test, commit. |
| 02-policy-governance | Refactor policy governance workflows. | Not Started | Library, editor/linting, bindings/rollout, simulator/feed, audit/compliance evidence/reporting, tests, commit. |
| 03-trust-mesh | Refactor trust and mesh workflows. | Not Started | Trust scoring, trust cards, handshakes/thresholds, topology/message feed, protocol bridges, tests, commit. |
| 04-mcp-runtime-security | Refactor MCP and runtime security workflows. | Not Started | MCP registry/scans/proxy, runtime sessions/rings/sagas/sandbox/kill-switch, tests, commit. |
| 05-ecosystem-operations | Refactor marketplace, observability, integrations, and operational workflows. | Not Started | Plugin catalog/review/signing, SLO/cost/incidents/chaos, connectors/secrets, CLI/workflow artifacts, tests, commit. |
| 06-demo-delivery | Refactor demo delivery workflows. | Not Started | Demo scenarios, reset/run/proof flows, compose/cloud delivery support, tests, commit. |
| final-validation | Validate the complete migrated app and patch cross-cutting issues. | Not Started | Re-read logs, run full backend/frontend validation, fix failures, commit final validation fixes. |

## Detailed Checklist

- [x] Read `docs/frontend-refactor-execution-log/README.md`.
- [x] Read `docs/frontend-refactor-execution-log/00-framework-foundation.md`.
- [x] Read `docs/frontend-refactor-execution-log/00-platform-foundation.md`.
- [x] Read all `docs/product-platform-worktree/01-agent-registry` source plans.
- [x] Read all `docs/product-platform-execution-log/01-agent-registry` prior implementation logs.
- [x] Inventory legacy frontend modules/tests for agents and discovery.
- [x] Add typed React API helpers for registration drafts, agents, lifecycle, credentials, scanners, targets, runs, findings, and reconciliation actions.
- [x] Migrate `/agents` registration wizard with six planned steps and deterministic tests.
- [x] Migrate `/agents` inventory table, filters, default sort, row actions, and empty state.
- [x] Migrate agent detail tabs: Overview, Identity, Policies, Credentials, Trust, Audit, Runtime, Integrations, and lifecycle timeline.
- [x] Migrate lifecycle queue/funnel/orphan workflows with reason-confirmed actions.
- [x] Migrate credential table, rotation queue, scope review, verify/rotate/revoke flows, and inventory credential status.
- [x] Migrate `/discovery` scan runner: scanner cards, target table, schedules, run-now, run history, run detail/error states.
- [x] Migrate discovery findings reconciliation: filters, risk detail, evidence, assign/register/suppress/decommission actions, suppression review.
- [x] Add/update React Vitest coverage for agent and discovery behavior.
- [x] Update Playwright smoke to cover at least one Agents and one Discovery critical path.
- [x] Run focused frontend tests after each slice.
- [x] Run focused backend contract tests for agent/discovery APIs.
- [x] Run full frontend validation and Playwright smoke.
- [x] Update this log with every small implementation/test step.
- [x] Commit `01-agent-registry refactor`.

## Step Log

### 2026-05-02 - Phase Startup

What I am doing now:

- Starting `01-agent-registry` after committing `00-platform-foundation`.

Changes made:

- Created this execution log.

Commands run:

- `find docs/frontend-refactor-execution-log -maxdepth 1 -type f | sort`
- `find docs/product-platform-worktree/01-agent-registry -maxdepth 3 -type f | sort`
- `find docs/product-platform-execution-log/01-agent-registry -maxdepth 2 -type f | sort`
- `sed -n '1,260p' docs/frontend-refactor-execution-log/README.md`
- `sed -n '1,320p' docs/frontend-refactor-execution-log/00-framework-foundation.md`
- `sed -n '1,360p' docs/frontend-refactor-execution-log/00-platform-foundation.md`
- `sed -n '1,280p' docs/product-platform-worktree/01-agent-registry/...`
- `sed -n '1,360p' docs/product-platform-execution-log/01-agent-registry/...`

Observed output:

- Previous React refactor phases are complete and committed.
- Agent registry legacy implementation is complete across registration, inventory/detail, lifecycle, credentials, scan runner, and reconciliation.
- Prior final validation for this feature passed 152 backend tests and 62 legacy frontend tests.
- The active React app currently renders placeholders for `/agents` and `/discovery`.

Analysis:

- This phase should migrate the existing behavior into React rather than designing new product flows.
- The safest sequence is `/agents` first, then `/discovery`, because reconciliation depends on registration/inventory concepts.
- Legacy JS modules and tests remain as source-of-truth fixtures while React pages are added.

Next action:

- Inventory the legacy `agents.js`, `discovery.js`, and test coverage to define the first React migration slice.

### 2026-05-02 - Legacy Frontend Inventory

What I am doing now:

- Mapping the legacy agent and discovery UI surface before editing React code.

Changes made:

- No production code changes in this step.

Commands run:

- `rg "^export function|^export const|^function" packages/product-platform/frontend/src/agents.js`
- `rg "^export function|^export const|^function" packages/product-platform/frontend/src/discovery.js`
- `rg "Subtest|test\\(" packages/product-platform/frontend/test/agent-registration.test.js packages/product-platform/frontend/test/discovery-scan-runner.test.js packages/product-platform/frontend/test/discovery-reconciliation.test.js`
- `sed -n '1,620p' packages/product-platform/frontend/test/agent-registration.test.js`
- `sed -n '1,300p' packages/product-platform/frontend/test/discovery-scan-runner.test.js`
- `sed -n '1,300p' packages/product-platform/frontend/test/discovery-reconciliation.test.js`

Observed output:

- `agents.js` exports registration wizard, inventory/detail, lifecycle, credential, and tab render helpers.
- `discovery.js` exports scanner, target, run, finding table/detail, filter, and duration helpers.
- Legacy tests cover registration endpoints and wizard steps, inventory filters/actions/empty state, detail overview/identity/audit/runtime, lifecycle queue/modals/orphans, credential tables/actions, discovery scan runner, run detail/error states, findings risk/evidence/actions/filter params, and all related API client endpoints.

Analysis:

- The first React slice should establish typed API helpers and a React `/agents` page with enough behavior to replace the placeholder and exercise the main registry flows.
- The second React slice can then wire `/discovery` using the same data-fetching conventions.

Next action:

- Add typed React API helpers for agent registry and discovery endpoints.

### 2026-05-02 - Typed API Helpers

What I am doing now:

- Adding React-era typed endpoint wrappers for agent registry and discovery workflows.

Changes made:

- Added `src/api/agents.ts` with registration, inventory/detail, lifecycle, credential, expiring credential, and React Query helpers.
- Added `src/api/discovery.ts` with scanner, target, schedule, run, finding, reconcile, triage, and React Query helpers.
- Updated the shared API client request type to accept JSON bodies as `unknown` and serialize them centrally before fetch.

Commands run:

- `npm run typecheck`

Observed output:

- The first typecheck failed because plain JSON objects were being cast to `BodyInit`.
- After widening `ApiRequestInit` and avoiding body spread into `RequestInit`, typecheck passed.

Analysis:

- The endpoint paths now match the legacy client coverage while using the React framework's typed API client and tenant headers.

Next action:

- Build the React `/agents` page around these helpers, starting with registration, inventory, detail, lifecycle, and credentials.

### 2026-05-02 - Agents React Page

What I am doing now:

- Migrating the legacy Agents route from placeholder to React UI.

Changes made:

- Added `src/features/agents/AgentsPage.tsx`.
- Wired `/agents` to `AgentsPage` in the TanStack Router.
- Implemented registration draft form with six planned steps.
- Implemented inventory filters/table/actions and empty state.
- Implemented lifecycle workspace with funnel counts, approval queue, and orphan candidates.
- Implemented agent detail tabs for overview, identity, credentials, lifecycle, audit, runtime, policies, trust, and integrations.
- Implemented credential issue/rotate/revoke controls and rotation queue display.
- Wired audit tab events to the shared React detail drawer.
- Added `src/features/agents/AgentsPage.test.tsx` with deterministic fetch fixtures.

Commands run:

- `npm run typecheck`
- `npm test -- src/features/agents/AgentsPage.test.tsx`

Observed output:

- Typecheck initially caught JSX arrow escaping and an `unknown` mutation result; both were patched.
- Focused AgentsPage Vitest initially found ambiguous text queries because operational labels intentionally repeat in the page; tests were adjusted to assert repeated labels correctly.
- Focused AgentsPage Vitest passed 2 tests.

Analysis:

- `/agents` now covers the planned registry registration, inventory/detail, lifecycle, credential, and audit-drawer behaviors in React.
- Remaining feature scope is `/discovery` scan runner and findings reconciliation.

Next action:

- Build the React `/discovery` page and tests.

### 2026-05-02 - Discovery React Page

What I am doing now:

- Migrating discovery scan runner and findings reconciliation into React.

Changes made:

- Added `src/features/discovery/DiscoveryPage.tsx`.
- Wired `/discovery` to `DiscoveryPage` in the TanStack Router.
- Implemented scanner cards, target table, schedule/run-now controls, run history, run detail, raw finding rendering, and failed run error visibility.
- Implemented finding filters, hidden-by-default suppressed findings, risk/evidence detail, assign owner, register agent, suppress, and mark-decommissioned actions.
- Added `src/features/discovery/DiscoveryPage.test.tsx` with deterministic scan runner and reconciliation fixtures.

Commands run:

- `npm run typecheck`
- `npm test -- src/features/discovery/DiscoveryPage.test.tsx`

Observed output:

- Typecheck passed after wiring the discovery route.
- Focused discovery Vitest initially needed matcher adjustments for formatted raw JSON and repeated finding labels.
- Focused discovery Vitest passed 2 tests.

Analysis:

- `/discovery` now covers scan runner and reconciliation behavior in React using the same backend contracts as the legacy implementation.

Next action:

- Run focused combined React tests, full frontend validation, Playwright smoke, and focused backend contract tests for agent/discovery APIs.

### 2026-05-02 - 01 Agent Registry Validation

What I am doing now:

- Validating the migrated Agents and Discovery React workflows end-to-end before commit.

Changes made:

- Updated Playwright smoke fixtures for `/agents`, agent detail/timeline/audit/credentials, expiring credentials, discovery scanners, targets, runs, and findings.
- Extended the smoke path to visit Agents and Discovery and assert rendered registry/discovery data.
- Tightened the smoke assertions to use role-specific locators for repeated agent names.

Commands run:

- `npm test -- src/features/agents/AgentsPage.test.tsx src/features/discovery/DiscoveryPage.test.tsx`
- `npm run validate`
- `npm run test:e2e`
- `npm run test:legacy`
- `env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_agent_registration*.py' -v`
- `env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_agent_inventory*.py' -v`
- `env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_lifecycle_workflows.py' -v`
- `env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_credential*.py' -v`
- `env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_discovery_scan_runner*.py' -v`
- `env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_discovery_reconciliation*.py' -v`
- `env PYTHONPATH=src python3 -m unittest discover -s tests -v`

Observed output:

- Combined Agents and Discovery Vitest passed 4 tests.
- Full frontend validation passed: lint, typecheck, Vitest 11 files / 19 tests, and Vite build.
- First Playwright smoke run failed on a strict locator because `Smoke Agent` appears in both the table and detail heading.
- After switching the assertion to the detail heading, Playwright smoke passed 1 test.
- Legacy frontend tests passed 197 tests.
- Focused backend contract suites passed: agent registration 16 tests, agent inventory 8 tests, lifecycle workflows 8 tests, credential workflows 15 tests, discovery scan runner 14 tests, discovery reconciliation 15 tests.
- First full backend test run completed 492 tests with 2 sandbox-only local HTTP server binding errors in demo tests.
- Escalated full backend test rerun passed 492 tests.

Analysis:

- The migrated React routes preserve the planned registry, discovery, lifecycle, credential, and reconciliation behaviors and are covered by focused frontend tests, smoke coverage, legacy frontend tests, and backend contracts.
- The only full-suite failure was caused by sandbox restrictions when tests created temporary local HTTP servers; the same suite passed when rerun with approved local binding.

Next action:

- Run whitespace/status checks, stage the phase changes, and commit `01-agent-registry refactor`.
