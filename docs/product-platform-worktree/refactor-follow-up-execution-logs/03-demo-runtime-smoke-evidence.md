# Demo Runtime Smoke Evidence Follow-Up Execution Log

## Phase Overview

| Phase | Goal | Status | Biggest Checklist Items |
| --- | --- | --- | --- |
| Phase 1: Docker-Capable Environment Prep | Confirm Docker daemon and registry/base-image access. | Done | Run Docker/Compose version; record environment capabilities. |
| Phase 2: Production Image Smoke | Build and smoke frontend/API/worker cloud-preview images if possible. | Done | Run `deploy/cloud/smoke-images.sh`; capture health/ready/no-op evidence. |
| Phase 3: Local Compose Smoke | Run the demo compose stack and local demo smoke script if possible. | Done | Run compose up/wait and `deploy/local-demo-smoke.sh`; capture Demo Lab reset/run evidence. |
| Phase 4: Pilot Scope Decision | Document whether SQLite cloud preview is accepted or a DB runtime follow-up is needed. | Done | Inspect `PILOT_READINESS.md`; update evidence and closure notes. |

## Detailed Checklist

- [x] Read `docs/product-platform-worktree/refactor-audit-report.md`.
- [x] Locate all follow-up plan files.
- [x] Create this execution log in the dedicated refactor follow-up log folder.
- [x] Re-read `follow-ups/demo-runtime-smoke-evidence/plan.md`.
- [x] Run Docker/Compose capability checks.
- [x] Run image smoke if supported.
- [x] Run compose/local demo smoke if supported.
- [x] Run focused demo/cloud tests with localhost binding where required.
- [x] Document exact commands, outputs, blockers, and final status.

## Step Log

- Re-read `docs/product-platform-worktree/refactor-audit-report.md`, this follow-up plan, and `02-demo-cloud-runtime-verification.md` before starting this follow-up.
- Reused Docker capability evidence from the immediately preceding runtime follow-up: `docker version` passed with escalation, and `docker compose version` reported Docker Compose `v2.39.1-desktop.1`.
- Reused production image smoke evidence from `02-demo-cloud-runtime-verification.md`: after fixing image build context and production runtime dependencies, `sh deploy/cloud/smoke-images.sh` passed. It rebuilt API, worker, and frontend images, applied migrations `0001` through `0049`, probed `/health` and `/ready`, ran the worker `noop` command, and printed `Product platform image smoke checks passed.`
- Reused local compose smoke evidence from `02-demo-cloud-runtime-verification.md`: after fixing the local demo image and smoke script, `sh deploy/local-demo-smoke.sh` passed. It started the full demo stack, confirmed seeded integrations/credentials/scenario checks, ran the customer-support-refund scenario, verified SSE activity, probed the frontend, checked the sample MCP server, and printed `Local demo compose smoke checks passed.`
- Ran `/usr/bin/env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mvp_cloud_deployment_phase*.py' -v`: passed 19 tests.
- Ran `/usr/bin/env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_local_demo_compose*.py' -v` with localhost/Docker escalation: passed 11 tests.
- Re-read `deploy/cloud/PILOT_READINESS.md`: it explicitly documents SQLite on a durable application data volume for the MVP cloud preview, and defers managed PostgreSQL until a PostgreSQL connection and migration adapter are implemented.

## Completion Summary

This follow-up is complete and required no additional implementation beyond the runtime fixes made while completing `demo-cloud-runtime-verification`. The demo delivery gap now has actual Docker runtime evidence, current focused tests are green, and the PostgreSQL question remains an accepted pilot-scope limitation rather than a mixed-in implementation task.
