# Product Platform Worktree Audit

## Executive Summary

The seven top-level plan folders map cleanly to one implementation commit each after the initial planning commit. The strongest workstreams are `00-platform-foundation`, `03-trust-mesh`, and `04-mcp-runtime-security`: their committed surfaces line up with the plans and have broad backend/frontend coverage. `01-agent-registry` also appears functionally implemented, but current verification is blocked by later demo baseline seed changes that make old agent tests see unexpected demo agents.

The main incomplete scope is concentrated in three areas:

- `02-policy-governance` implemented policy library/editor/bindings, but not the planned policy simulator/evaluation feed or compliance control/evidence/report builder.
- `05-ecosystem-operations` implemented marketplace, observability, and most integration backend work, but workflow execution stops at catalog listing, the artifact/attestation store is not implemented, and the integration frontend is currently broken at module import time.
- `06-demo-delivery` implemented Demo Lab/reset/local/cloud artifacts with good execution logs, but it introduced cross-suite seed regressions, still has SQLite-only runtime persistence despite Postgres/cloud claims, and real Docker image builds were not verified.

Verification is not green at HEAD:

- Backend: `PYTHONPATH=src python3 -m unittest discover -s tests -v` ran 434 tests and failed with 5 failures and 8 errors. Two errors were sandbox-only local socket bind failures; the focused rerun of `test_local_demo_compose_phase2.py` passed when local socket binding was allowed. The remaining failures/errors are real suite regressions from demo baseline agent seeding and integration tests colliding with those seeded agents.
- Frontend: `npm run validate` passed lint and typecheck, then failed `node --test` because `frontend/test/integrations.test.js` imports integration helpers that `frontend/src/integrations.js` does not export.

## Plan-By-Plan Audit

| Plan folder | Intended scope | Related commit(s) | Status | Evidence | Test coverage | Gaps |
| --- | --- | --- | --- | --- | --- | --- |
| `00-platform-foundation` | Product API shell, auth/RBAC/tenancy, canonical SQLite schema/migrations, audit/event pipeline, background worker runtime, frontend shell/navigation, shared drawers. | Plan docs: `19c1bab`; implementation: `be08c50` (`00-platform-foundation implementation`). | Complete | Added `packages/product-platform` app skeleton, migrations `0001`, API/auth/audit/db/worker modules, frontend shell/drawers/state. Commit touched 76 files with focused phase tests. | Backend tests cover API shell, auth, DB, audit, worker phases. Frontend tests cover shell, auth context, permissions, drawers, correlation navigation, system status. Relevant tests passed during the full run. | No material plan gaps found. App code is large and centralized in `api/app.py`, but that follows the implementation sequence rather than unrelated churn. |
| `01-agent-registry` | Agent registration wizard, inventory/detail, lifecycle workflows, credential issuance/rotation/expiry, discovery scans, finding reconciliation/triage. | Plan docs: `19c1bab`; implementation: `72b2850` (`01-agent-registry`). | Needs verification | Added `agents/*`, `discovery/*`, migrations `0002`-`0005`, API/frontend surfaces, and broad backend/frontend tests. | Most agent, credential, lifecycle, discovery tests pass. Current full-suite run fails `test_agent_inventory_phase1` and `test_agent_registration_overall` because later demo seed data adds `agent_demo_*` records and a duplicate `Demo Support Agent`. | Original scope appears implemented, but HEAD is not verifiable until demo baseline seed isolation is fixed. Follow-up: `follow-ups/integrations-frontend-and-demo-seed-regressions/plan.md`. |
| `02-policy-governance` | Policy library/versioning, editor/linting, bindings/rollout, policy simulator/evaluation feed, audit explorer, control map/evidence library, compliance report builder. | Plan docs: `19c1bab`; implementation: `68b0a0b` (`02-policy-governance`). | Partially complete | Added `policies/*`, migrations `0006`-`0008`, policy routes/UI/tests. Current code has policy library/editor/binding surfaces, plus foundation audit APIs/drawers from `00`. | Policy library/editor/bindings tests are meaningful and pass in the full run. Audit event query/verify/stream tests also pass. | Missing `policy_evaluations` table and `/api/v1/policy-evaluations/*` APIs/UI. Missing compliance data model and `/api/v1/compliance/*` APIs/UI/reports. `/compliance` remains a placeholder route. Follow-ups: `follow-ups/policy-simulator-evaluation-feed/plan.md` and `follow-ups/compliance-evidence-and-reports/plan.md`. |
| `03-trust-mesh` | Trust score pipeline, trust cards, handshakes/thresholds, mesh topology/message feed, protocol bridge configuration and honest health checks. | Plan docs: `19c1bab`; implementation: `7316b9b` (`03-trust-mesh`). | Complete | Added `trust/*`, `mesh/*`, migrations `0009`-`0013`, trust/mesh frontend modules and tests. Protocol bridge plan explicitly allowed placeholder protocol implementations while reporting limited capability honestly. | Trust, handshake, mesh, and protocol bridge tests passed in the full run, including audit events, limited bridge health, and frontend route/component coverage. | No material gaps found. |
| `04-mcp-runtime-security` | MCP server/tool registry, security scans, proxy traffic/approvals/sanitization/rate limits, runtime sessions/rings, saga builder/monitor, sandbox profiles, kill switch. | Plan docs: `19c1bab`; implementation: `658ca89` (`04-mcp-runtime-security`). | Complete | Added `mcp/*`, `runtime/*`, migrations `0014`-`0022`, MCP/runtime frontend modules and tests. | MCP registry/scans/proxy and runtime sessions/rings/sagas/sandbox/kill-switch tests passed in the full run. Frontend MCP/runtime tests passed before the unrelated integrations import failure stopped the aggregate frontend run. | No material gaps found. |
| `05-ecosystem-operations` | Marketplace catalog/install/review/signing/trust, observability SLO/cost/incidents/chaos/rollouts, framework integrations/provider secrets, CLI workflow runner, artifact/attestation store. | Plan docs: `19c1bab`; implementation: `9d77b9b` (`05-ecosystem-operations`). | Partially complete | Added marketplace, observability, integrations, workflow catalog modules, migrations `0023`-`0038`, API/UI/tests. `GET /api/v1/workflows` exists, but no run/log/artifact APIs. | Marketplace, observability, and many integration backend tests exist. Workflow coverage is only `test_cli_workflow_runner_phase1.py` for catalog listing/input schemas. Frontend aggregate fails on integrations module exports. Backend full run also has integration errors caused by demo seed collisions. | Missing workflow runner phases 2-4: run creation, safe runner, logs, cancel, audit, UI. Missing artifact/attestation store entirely. Integration frontend is incomplete/broken relative to tests and `app.js` imports. Follow-ups: `follow-ups/workflow-runner-and-artifacts/plan.md` and `follow-ups/integrations-frontend-and-demo-seed-regressions/plan.md`. |
| `06-demo-delivery` | Scenario catalog/runner, resettable baseline, local demo compose, MVP cloud packaging/deployment readiness. | Plan docs: `19c1bab`; implementation: `0922fad` (`06-demo-delivery`). | Partially complete | Added detailed execution logs for all four demo plans, migrations `0039`-`0041`, `demo/*`, local compose/docs, cloud Dockerfiles/manifests/runbooks, `.github/workflows/product-platform-images.yml`. | Demo-focused backend/frontend tests are broad. Execution logs record focused passing commands. `test_local_demo_compose_phase2.py` passes when local socket binding is allowed. | Demo baseline seeding in generic `seed_demo_data()` now leaks demo agents into older tests. Local/cloud runtime is still SQLite-only (`db/migrator.py` rejects non-SQLite URLs) while compose/cloud artifacts advertise Postgres. Cloud readiness checks validate configuration strings, not real service connectivity, and real Docker builds remain unverified because Docker daemon was unavailable. Follow-ups: `follow-ups/integrations-frontend-and-demo-seed-regressions/plan.md` and `follow-ups/demo-cloud-runtime-verification/plan.md`. |

## Ambiguous, Incomplete, Or Risky Areas

### Policy Governance Split

The `02-policy-governance` commit delivered policy management well, but it did not implement the later policy-governance plans. The simulator plan explicitly requires `POST /api/v1/policy-evaluations/simulate`, `POST /api/v1/policy-evaluations/evaluate`, persisted evaluations, a simulator UI, and an evaluation feed. Current code only has binding resolution and agent-registration simulation helpers, not the general evaluation product surface.

The compliance plans are effectively not implemented. The worktree asks for `control_frameworks`, `controls`, `evidence_items`, `violations`, `compliance_reports`, report evidence links, and attestations. Current product code has audit APIs and navigation permissions for `/compliance`, but no compliance package, migrations, API routes, frontend module, or tests.

### Workflow And Artifact Scope

The workflow catalog exists and is seeded, but the CLI Workflow Runner definition of done is repeatable product workflows with logs and audit history. Current implementation stops after `GET /api/v1/workflows`. There are no workflow run/log tables beyond the foundation `workflow_runs` table, no run/cancel endpoints, no safe runner, no UI, and no tests beyond phase 1.

The artifact/attestation store is missing as a product surface. `product_platform.deployment.artifacts.LocalArtifactStore` exists for cloud smoke tests, but it is not the planned durable artifact metadata/link/attestation API and UI.

### Current Verification Regressions

`seed_demo_data()` now always calls `seed_demo_baseline_fixtures()`, which inserts `agent_demo_support`, `agent_demo_refund`, and `agent_demo_supervisor`. Older tests that call `seed_demo_data()` then insert their own agents now fail because they either see the extra demo agents in list responses or collide on the unique active agent name index.

The integration frontend test imports helpers such as `integrationAgentLinkPayloadFromValues`, `renderConnectorInstanceForm`, and `renderProviderCredentialsTable`, while `frontend/src/integrations.js` currently exports only the framework catalog renderer and support badge helpers. `frontend/src/app.js` also imports integration form helpers that are not present, so the issue is not test-only.

### Demo And Cloud Readiness

The demo execution logs are honest about two important limitations: local compose includes Postgres for parity while product persistence remains SQLite-backed, and real image builds were not verified because Docker daemon access was unavailable. The cloud readiness implementation currently treats a PostgreSQL URL as healthy without opening a database connection, while the actual migration runner rejects non-SQLite URLs.

## Unrelated Or Unexpected Changes

- `.github/workflows/product-platform-images.yml` was added by the `06-demo-delivery` cloud plan. It is outside `packages/product-platform`, but it is expected for the image-build workflow called out by the plan.
- `/compliance` and `/workflows` are registered product routes even though their planned product surfaces are placeholders or incomplete. This is expected from the navigation foundation, but it can make demo navigation look more complete than the implementation really is.
- No unrelated churn outside the product-platform workstream was found in the implementation commits reviewed.

## Follow-Up Plans Created

- `follow-ups/policy-simulator-evaluation-feed/plan.md`
- `follow-ups/compliance-evidence-and-reports/plan.md`
- `follow-ups/workflow-runner-and-artifacts/plan.md`
- `follow-ups/integrations-frontend-and-demo-seed-regressions/plan.md`
- `follow-ups/demo-cloud-runtime-verification/plan.md`
