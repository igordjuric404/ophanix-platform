# Product Platform Frontend Refactor Audit

## Executive Summary

This audit covers the frontend framework refactor sequence after `origin/main`: `243d062` (`framework setup refactor`), the ordered workstream commits `1df0636` through `9a2c754`, and the final validation commit `2b3f627`. The refactor replaced the active frontend entry point with React, TypeScript, Vite, TanStack Router/Query, Tailwind-style UI primitives, Vitest, React Testing Library, Playwright, ESLint, and Prettier, while preserving the FastAPI backend and product route taxonomy.

The implementation is broadly successful. The main product workspaces are mounted as React routes, the backend feature contracts still pass, and the React test suite covers meaningful user behavior across every migrated area. Current verification is green when localhost binding is allowed for local browser/server tests:

- `npm run validate`: passed lint, typecheck, 22 Vitest files / 47 tests, and production build.
- `npm run test:legacy`: passed 197 legacy frontend tests.
- `npm run test:e2e`: passed 1 Chromium smoke test with localhost binding allowed. The normal sandbox run fails before tests with `listen EPERM 127.0.0.1:3000`.
- `/usr/bin/env PYTHONPATH=src python3 -m unittest discover -s tests -v`: passed 492 backend tests with localhost binding allowed. The normal sandbox run fails only two local-demo compose tests that bind temporary `127.0.0.1` HTTP servers.

The strongest workstreams are `00-platform-foundation`, `01-agent-registry`, `03-trust-mesh`, and `04-mcp-runtime-security`: their intended refactor scopes map cleanly to committed React pages, typed API helpers, route wiring, execution logs, and passing focused tests.

The incomplete or risky areas are narrower and mostly frontend/refactor-quality issues:

- Framework cleanup is incomplete: the active app is React/Vite, but the old vanilla page modules and `node --test` legacy suite remain in `frontend/src` and `frontend/test`, and no concise `MIGRATION_NOTES.md` was added.
- `02-policy-governance` preserves the product behavior, but the evaluation feed does not fully match the planned framework shape: it opens `EventSource` directly instead of using the shared hook, lacks a UI test that simulates live stream updates, renders evaluation detail inline rather than through the shared drawer pattern, and renders trends as metric summaries rather than real charts.
- `05-ecosystem-operations` is functionally implemented, but the planned observability/SLO/cost charts are currently metric grids and tables. `recharts` is installed but unused.
- `06-demo-delivery` is functionally migrated and statically tested, but real Docker image, compose-up, and cloud-preview runtime smoke evidence still requires a Docker-capable environment with registry/base-image access.

## Plan-By-Plan Audit

| Subfolder / phase | Intended refactor scope | Related commit(s) | Status | Evidence | Test coverage | Gaps |
| --- | --- | --- | --- | --- | --- | --- |
| Framework setup | Establish the shared React/TypeScript/Vite framework, TanStack Router/Query, Tailwind/shadcn-style primitives, typed API/auth foundation, route registry, test tooling, Vite local runtime, and Docker frontend build path. | `243d062`; final validation docs in `2b3f627`. | `Partially complete` | `frontend/index.html` now loads `src/main.tsx`; `package.json` has `dev`, `build`, `test`, `test:e2e`, `lint`, `typecheck`, `format`; `src/app`, `src/api`, `src/components`, `src/lib`, and Vite/Tailwind/Playwright/ESLint config exist; `start.sh`, `docker-compose.demo.yml`, and `deploy/cloud/Dockerfile.frontend` were updated. | Current `npm run validate` passed; Playwright smoke passed with localhost binding allowed. | Old vanilla modules and legacy tests remain tracked and passing; no `MIGRATION_NOTES.md`; `src/lib/eventSource.ts` exists but policy live feed bypasses it; `recharts` is installed but unused. Follow-up: `follow-ups/frontend-legacy-retirement-and-migration-notes/plan.md`. |
| `00-platform-foundation` | React shell/navigation, auth and tenant context, system status, RBAC/access denied behavior, shared detail drawer, audit event drawer variants, and correlation navigation. | `1df0636`; validation in `2b3f627`. | `Complete` | Added `drawerContext`, `tenantContext`, React drawer components, environment selector, notification/status components, RBAC helpers/tests, and route integration. `/settings` remains a route scaffold as planned by the shell plan. | React tests cover tenant headers, RBAC, shell/status, drawer states, audit drawer variants, related-event navigation, and access denied behavior. Backend API/auth/audit tests pass in the 492-test run. | No material gaps found. |
| `01-agent-registry` | React migration for agent registration wizard, inventory/detail, lifecycle workflows, credential issuance/rotation/revocation, discovery scan runner, and findings reconciliation. | `ea64b9d`; validation in `2b3f627`. | `Complete` | Added typed `api/agents.ts` and `api/discovery.ts`; mounted `AgentsPage` and `DiscoveryPage`; implemented registry, lifecycle, credential, scan, finding, and reconciliation flows. | React feature tests cover rendering, actions, payload normalization, API paths, and route behavior. Legacy frontend tests and backend agent/discovery/credential suites pass. | No product/refactor gap beyond the cross-cutting legacy retirement follow-up. |
| `02-policy-governance` | React migration for policy library/versioning, editor/linting, bindings/rollout, simulator/evaluation feed, audit explorer, control/evidence library, violations, reports, and attestations. | `662b1e2`; validation in `2b3f627`. | `Partially complete` | Added typed `api/policies.ts`, `api/compliance.ts`, React `PoliciesPage` and `CompliancePage`, stream URL helpers, simulator/feed UI, compliance evidence/report UI, and execution log. Backend already contains policy evaluation/compliance implementations and tests. | React tests cover policy library/editor/bindings/simulator/feed helpers and compliance audit/evidence/report behavior. Backend policy/compliance/evaluation tests pass, including SSE/backend producer coverage. | The evaluation feed still misses the planned framework polish: direct `EventSource` use instead of shared `useEventStream`, no React test that drives a streamed evaluation through the UI, inline detail instead of shared drawer, and text summary buckets rather than charted decision trends. Follow-up: `follow-ups/policy-live-feed-and-governance-visuals/plan.md`. |
| `03-trust-mesh` | React migration for trust scores, trust cards, thresholds, handshakes, mesh topology, messages, handoffs, protocol bridges, route editor, health checks, and limited-capability warnings. | `027a86b`; validation in `2b3f627`. | `Complete` | Added typed `api/trust.ts` and `api/mesh.ts`; mounted `TrustPage` and `MeshPage`; retained honest limited bridge status for placeholder/pass-through bridge adapters. | React tests cover trust score/cards/thresholds/handshakes and mesh topology/messages/handoffs/bridges. Backend trust/mesh/protocol tests pass. | No material gaps found. Limited protocol-bridge runtime behavior is explicitly surfaced rather than hidden. |
| `04-mcp-runtime-security` | React migration for MCP server/tool registry, scans/findings, proxy traffic/approvals/rate limits, runtime sessions/rings, saga builder/monitor, sandbox profiles, and kill switch. | `5b8dbaf`; validation in `2b3f627`. | `Complete` | Added typed `api/mcp.ts` and `api/runtime.ts`; mounted `McpPage` and `RuntimePage`; implemented registry, scans, finding lifecycle, proxy testing, approval actions, sessions, ring rules, sagas, sandbox tests, and kill switch UI. | React MCP/runtime tests cover route rendering, mutations, payload normalization, and API paths. Backend MCP/runtime/saga/sandbox suites pass. | No material gaps found. |
| `05-ecosystem-operations` | React migration for marketplace catalog/install/review/signing/trust, observability SLO/cost/incidents/chaos/rollouts, integrations/framework connectors/provider credentials/health, workflows, artifacts, downloads, links, and attestations. | `e94b632`; validation in `2b3f627`. | `Partially complete` | Added typed APIs and React pages for marketplace, observability, integrations, and workflows/artifacts. Workflow/artifact backend second-pass tests now verify worker-backed queued runs and generated linked artifacts. | React tests cover each 05 page with user actions and payload/API path checks. Backend marketplace/observability/integrations/workflow/artifact suites pass. | Product behavior is present, but observability visualization is below the plan: SLO detail and cost "charts" are rendered as metric grids/tables, and `recharts` is unused. Follow-up: `follow-ups/observability-dashboard-visualization/plan.md`. |
| `06-demo-delivery` | React migration for Demo Lab scenario catalog/runner, proof checklist, reset confirmation/history/baseline, plus verification of local compose and MVP cloud deployment support. | `9a2c754`; validation in `2b3f627`. | `Needs verification` | Added typed `api/demo.ts`, mounted `DemoLabPage`, and covered scenario, run, proof, reset, and baseline UI. Backend/static tests cover demo APIs, local compose config, MVP cloud readiness docs/scripts, and SQLite cloud-preview scope. | React Demo Lab tests pass. Backend demo/local-compose/cloud tests pass with localhost binding allowed. | Real `docker build`, API/worker/frontend image smoke, `docker compose up --build --wait`, and local demo smoke script execution still lack current runtime evidence in this environment. Follow-up: `follow-ups/demo-runtime-smoke-evidence/plan.md`. |

## Detail Notes

### Framework Cleanup Boundary

The active application no longer depends on the vanilla entry point: `frontend/index.html` loads `src/main.tsx`, and the router mounts React pages for every main product route. However, the old modules (`src/app.js`, `src/render.js`, `src/apiClient.js`, and the page modules such as `agents.js`, `policies.js`, `workflows.js`) remain in `frontend/src`, and the legacy `node --test test/*.test.js` suite remains part of the package. This gave useful parity coverage during migration, but it now creates drift risk because future behavior can be changed in React without updating or retiring the old render helpers.

### Policy Live Feed And Detail Pattern

Policy evaluation behavior is implemented end to end on the backend and rendered in React. The remaining issue is conformance to the refactor framework pattern and original Phase 4 UI plan. `src/lib/eventSource.ts` provides a shared hook, but `PoliciesPage` constructs `window.EventSource` directly. The tests validate deterministic upsert helper behavior and backend SSE behavior, but they do not simulate an EventSource message through the React page. Evaluation detail is an inline section rather than the shared drawer pattern used elsewhere.

### Observability Visualization

The observability page preserves SLO, cost, incident, chaos, and rollout actions. The gap is visual rather than behavioral: the original plan called for SLO/detail and cost charts, and the refactor dependency set includes `recharts`, but no Recharts components are used anywhere under `frontend/src`. The current UI uses metric cards and tables, which are useful but not the planned chart-first dashboard surface.

### Demo Runtime Evidence

The checked-in demo/cloud tests are meaningful static and API tests, and current backend verification is green with localhost binding allowed. What is still missing is evidence from a Docker-capable runtime: production image build/start checks, worker no-op container smoke, frontend container smoke, and `docker compose up` against the local demo stack. This is a verification gap, not a known product-code failure.

## Unrelated Or Unexpected Changes

- `.gitignore`, `start.sh`, `docker-compose.demo.yml`, and `deploy/cloud/Dockerfile.frontend` changes are expected framework-runtime wiring.
- `package-lock.json` is large but expected from introducing the frontend framework stack.
- `docs/frontend-refactor-execution-log/*` is outside `docs/product-platform-worktree`, but it is expected audit evidence for the sequential refactor.
- The main unexpected residue is the retained inactive vanilla frontend code and legacy test suite. It is not active in runtime, but it should be retired or explicitly archived.
- No unrelated product-platform backend rewrites were introduced by the frontend refactor commits.

## Follow-Up Plans Created

- `follow-ups/frontend-legacy-retirement-and-migration-notes/plan.md`
- `follow-ups/policy-live-feed-and-governance-visuals/plan.md`
- `follow-ups/observability-dashboard-visualization/plan.md`
- `follow-ups/demo-runtime-smoke-evidence/plan.md`
