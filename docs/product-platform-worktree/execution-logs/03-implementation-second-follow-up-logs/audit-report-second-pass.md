# Product Platform Worktree Audit: Second Pass

## Executive Summary

This second pass verified the first audit against the original plan tree, the sequential implementation commits, follow-up execution logs, current code under `packages/product-platform`, and fresh test runs.

The first audit was directionally correct at the time it was written. Since then, commit `2de9148` (`gap fill v1`) implemented most first-pass follow-ups: policy evaluations, compliance evidence/reports, workflow/artifact APIs, integration frontend recovery, demo seed isolation, and cloud/local readiness cleanup.

Current verification is materially better than the first audit:

- Frontend: `npm run validate` passed lint, typecheck, and all 193 frontend tests.
- Backend: `PYTHONPATH=src python3 -m unittest discover -s tests -v` passed all 485 tests when localhost socket binding was allowed.
- Backend sandbox note: the same backend command without localhost binding permission failed only on two `test_local_demo_compose_phase2.py` tests that bind `127.0.0.1`; the escalated rerun passed.

The remaining gaps are narrower than the first audit reported:

- `02-policy-governance`: compliance is now implemented; policy simulator/feed is implemented, but the feed still lacks original-plan live updates, decision trends, and non-MCP/runtime producer coverage.
- `05-ecosystem-operations`: integrations are fixed and workflow/artifact surfaces exist, but workflow execution is still request-thread/synchronous for immediate runs, most workflow adapters are placeholders, and product-generated reports/exports are not yet stored as checksumed artifact rows.
- `06-demo-delivery`: seed regressions are fixed and cloud/runtime claims are honest, but real Docker image and compose smoke evidence still need a Docker-capable environment; the original managed-PostgreSQL pilot scope is explicitly deferred.

No product-platform fixes were implemented in this pass. Only audit documentation and follow-up plan status/delta sections were updated.

## Changes From The First Audit

| Area | First audit finding | Second-pass result |
| --- | --- | --- |
| `01-agent-registry` | `Needs verification` because demo seed data broke older agent tests. | `Audit finding revised`; now `Confirmed complete`. `seed_demo_data()` no longer leaks demo baseline fixtures by default, and agent/integration regressions pass. |
| `02-policy-governance` | `Partially complete`; policy simulator/feed and compliance were missing. | `Audit finding revised`. Policy evaluations and compliance are now present with tests, but a narrower policy-feed gap remains. |
| `05-ecosystem-operations` | `Partially complete`; workflow runner/artifacts missing and integrations frontend broken. | `Audit finding revised`. Integrations frontend and seed regressions are fixed; workflow/artifact APIs exist, but workflow execution/adapters/artifact integration remain incomplete. |
| `06-demo-delivery` | `Partially complete`; seed regressions, SQLite/Postgres mismatch, and unverified Docker/cloud runtime. | `Audit finding revised`. Seed isolation and readiness/doc honesty are fixed; Docker runtime smoke and original managed cloud scope still need verification or a separate product decision. |
| Verification state | Backend and frontend were red at HEAD. | Frontend green. Backend green with localhost socket permission; sandbox-only socket errors remain when binding is blocked. |

## Plan-By-Plan Reassessment

| Plan folder | Original audit status | Second-pass status | Evidence | Test coverage | Remaining gaps |
| --- | --- | --- | --- | --- | --- |
| `00-platform-foundation` | Complete | `Confirmed complete` | Original implementation commit `be08c50` added API shell, auth/RBAC/tenancy, migrations, audit/event pipeline, worker runtime, frontend shell, and drawers. Current code still contains those surfaces and no regression was found. | Backend foundation/auth/audit/worker tests pass in the 485-test run. Frontend shell/auth/drawer/navigation tests pass in the 193-test run. | None found. |
| `01-agent-registry` | Needs verification | `Audit finding revised`; `Confirmed complete` | Original implementation commit `72b2850` added agent identity, registration, lifecycle, credentials, discovery scanning, and reconciliation. Commit `2de9148` split generic seed data from demo baseline fixtures and fixed the verification blocker. | Agent inventory, registration, lifecycle, credential, discovery, demo seed boundary, and related frontend tests pass. | None found. The first audit's seed-regression follow-up is obsolete. |
| `02-policy-governance` | Partially complete | `Audit finding revised`; `Confirmed gap` | Original implementation commit `68b0a0b` covered policy library/editor/bindings. Commit `2de9148` added `0042_policy_evaluations`, `0043_audit_exports`, `0044`-`0046` compliance migrations, `policies/evaluations.py`, `policies/evaluation_repository.py`, `compliance/*`, `/api/v1/policy-evaluations/*`, `/api/v1/compliance/*`, and frontend policy/compliance surfaces. | Policy library/editor/bindings tests pass. Policy evaluation phase 1-3 tests pass. Compliance phase 1-4 tests pass. Frontend policy/compliance tests pass. | `New gap found`: policy evaluation feed still lacks original-plan decision trends/charts and live update stream. Producer coverage is MCP/runtime only; agent and framework-integration decisions are not yet persisted into the feed. Tracked in `follow-ups/policy-simulator-evaluation-feed/plan.md`. |
| `03-trust-mesh` | Complete | `Confirmed complete` | Original implementation commit `7316b9b` added trust score pipeline, cards, handshakes, mesh topology/message feed, and protocol bridge configuration. Current tests and code still line up with those plan files. | Trust score/card/handshake, mesh, protocol bridge, and frontend trust/mesh tests pass. | None found. |
| `04-mcp-runtime-security` | Complete | `Confirmed complete` | Original implementation commit `658ca89` added MCP registry/tools/scans/proxy traffic/approvals/rate limits plus runtime sessions/rings/sagas/sandbox/kill switch. Current policy follow-up adds feed rows without breaking MCP/runtime audit behavior. | MCP registry/scans/proxy tests, runtime/saga/sandbox tests, and frontend MCP/runtime tests pass. | None found. |
| `05-ecosystem-operations` | Partially complete | `Audit finding revised`; `Confirmed gap` | Original implementation commit `9d77b9b` added marketplace, observability, integrations, and workflow catalog. Commit `2de9148` fixed integrations frontend, added workflow runs/logs and artifact/attestation APIs/UI, and added migrations `0047`-`0049`. | Marketplace, observability, integrations, workflow runner phase 1-4, artifact, and frontend workflows/integrations tests pass. | `New gap found`: workflow runs execute inline in the API for immediate runs, queued runs lack worker execution, most workflow adapters are placeholder checks, and generated audit/compliance/workflow outputs are not stored as linked artifact rows. Tracked in `follow-ups/workflow-runner-and-artifacts/plan.md`. |
| `06-demo-delivery` | Partially complete | `Audit finding revised`; `Needs verification` | Original implementation commit `0922fad` added Demo Lab, reset, compose, and cloud artifacts/logs. Commit `2de9148` fixed demo seed boundaries, made SQLite cloud-preview scope explicit, rejected unsupported PostgreSQL URLs, added readiness probes, and added opt-in Docker smoke scripts. | Demo catalog/runner/reset/local/cloud tests pass. Backend aggregate passes with localhost socket permission. Local compose socket tests fail only when the sandbox blocks `127.0.0.1` binds. | Real Docker image builds, API/worker/frontend image smoke, and full `docker compose up` smoke are still not verified in this environment. Original managed-PostgreSQL MVP cloud scope is deferred. Tracked in `follow-ups/demo-cloud-runtime-verification/plan.md`. |

## Confirmed Follow-Ups

The following follow-ups remain valid and were updated rather than duplicated:

- `follow-ups/policy-simulator-evaluation-feed/plan.md`: `Confirmed gap`. The simulator/evaluation core is implemented; remaining work is live feed behavior, trend summaries, and agent/framework-integration producers.
- `follow-ups/workflow-runner-and-artifacts/plan.md`: `Confirmed gap`. Workflow/artifact surfaces exist; remaining work is worker-backed execution, real adapters, and product-generated artifact integration.
- `follow-ups/demo-cloud-runtime-verification/plan.md`: `Needs verification`. Runtime verification now has checked-in smoke scripts and honest docs, but actual Docker daemon-backed evidence is still missing.

No new follow-up folders were created because the remaining gaps fit existing follow-up ownership.

## Revised Or Obsolete Follow-Ups

| Follow-up folder | Second-pass status | Reason |
| --- | --- | --- |
| `follow-ups/compliance-evidence-and-reports` | `Obsolete follow-up` | Compliance APIs, data model, UI, evidence recompute, violations, reports, downloads, and report attestations are implemented and tested. Artifact-store integration is tracked under workflow/artifacts because it crosses report/export/workflow boundaries. |
| `follow-ups/integrations-frontend-and-demo-seed-regressions` | `Obsolete follow-up` | Seed leakage is fixed, Demo Lab reset explicitly restores baseline fixtures, integration frontend exports/routes are complete for current handlers/tests, and aggregate verification passes with localhost socket permission. |
| `follow-ups/policy-simulator-evaluation-feed` | `Audit finding revised` | Core implementation exists, but original-plan live/trend/producer coverage remains. |
| `follow-ups/workflow-runner-and-artifacts` | `Audit finding revised` | Core surfaces exist, but workflow execution and artifact integration are not yet end-to-end. |
| `follow-ups/demo-cloud-runtime-verification` | `Needs verification` | Static readiness work is implemented; Docker-backed smoke and original pilot cloud runtime acceptance remain open. |

## Newly Discovered Gaps

### `New gap found`: Policy Evaluation Feed Live/Trend/Producer Completeness

The original policy simulator/evaluation plan required a live evaluation feed, decision trends/charts, and decisions from agents, MCP proxy, runtime controls, and framework integrations. Current code provides simulator/evaluate/list/detail APIs and frontend feed rendering, with MCP/runtime producers. It does not provide feed-specific live update handling, decision trend summaries, or producer persistence for agent and framework-integration policy decisions.

Updated follow-up: `follow-ups/policy-simulator-evaluation-feed/plan.md`.

### `New gap found`: Workflow Execution Is Not Yet Worker-Backed Or Real-Adapter Complete

The workflow runner plan requires repeatable product workflows backed by persisted logs and audit history, ideally executed through the worker runtime. Current immediate workflow runs execute synchronously inside `create_workflow_run`, queued runs have no worker executor, and most seeded workflows use placeholder adapters rather than the existing repo CLI/script checks named in the plan.

Updated follow-up: `follow-ups/workflow-runner-and-artifacts/plan.md`.

### `New gap found`: Product-Generated Artifacts Are Not Integrated With The Artifact Store

The artifact APIs are implemented and tested for manual upload/link/attest flows. However, generated compliance reports and audit exports still store pseudo artifact URIs (`compliance-report://...`, `audit-export://...`) instead of creating checksumed artifact rows through `ArtifactRepository`; workflow runs also do not produce linked artifacts from outputs.

Updated follow-up: `follow-ups/workflow-runner-and-artifacts/plan.md`.

### `Needs verification`: Docker And Cloud Runtime Evidence

The demo/cloud follow-up added smoke scripts and static tests, but this checkout could not run Docker builds or compose-up smoke because Docker daemon access is unavailable. The original managed-PostgreSQL pilot deployment scope is also intentionally deferred in current docs/readiness. That is acceptable as an explicit scope decision only if pilot acceptance accepts SQLite cloud preview; otherwise it needs a separate database runtime plan.

Updated follow-up: `follow-ups/demo-cloud-runtime-verification/plan.md`.

## Verification Commands

| Command | Result |
| --- | --- |
| `npm run validate` from `packages/product-platform/frontend` | Passed lint, typecheck, and 193 frontend tests. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -v` from `packages/product-platform` | Failed in sandbox with 2 errors, both `PermissionError: [Errno 1] Operation not permitted` when binding `127.0.0.1` in `test_local_demo_compose_phase2.py`. No product failures observed. |
| Same backend command with localhost socket binding allowed | Passed all 485 backend tests in 77.935s. |

## Net Result

`00-platform-foundation`, `01-agent-registry`, `03-trust-mesh`, and `04-mcp-runtime-security` are `Confirmed complete`.

`02-policy-governance` is mostly complete after `2de9148`, with a narrowed `Confirmed gap` in policy feed live/trend/producer coverage.

`05-ecosystem-operations` is partially complete after `2de9148`, with a `Confirmed gap` in workflow execution and artifact integration.

`06-demo-delivery` is functionally much healthier, but remains `Needs verification` for Docker-backed runtime evidence and explicit cloud pilot scope acceptance.
