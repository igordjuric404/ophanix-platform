# Demo Cloud Runtime Verification Follow-Up Execution Log

## Phase Overview

| Phase | Goal | Status | Biggest Checklist Items |
| --- | --- | --- | --- |
| Phase 1: Runtime Scope Verification | Reconfirm current database/runtime scope and static readiness evidence. | Done | Read plan/docs; inspect readiness and Docker scripts; run focused static tests. |
| Phase 2: Docker Availability Probe | Determine whether this environment can run Docker-backed smoke tests. | Done | Run Docker version/compose config; escalate where localhost/Docker access is required. |
| Phase 3: Runtime Smoke Attempt | Run image/compose smoke if the environment supports it, or document the blocker with evidence. | Done | Run `smoke-images.sh`, compose smoke, and local-demo smoke where feasible. |
| Phase 4: Closure Documentation | Mark the plan complete, superseded, or blocked with exact evidence. | Done | Update log and avoid duplicating demo-runtime-smoke work. |

## Detailed Checklist

- [x] Read `docs/product-platform-worktree/refactor-audit-report.md`.
- [x] Locate all follow-up plan files.
- [x] Create this execution log in the dedicated refactor follow-up log folder.
- [x] Re-read `follow-ups/demo-cloud-runtime-verification/plan.md`.
- [x] Inspect cloud runtime docs, Dockerfiles, smoke scripts, readiness probes, and migration support.
- [x] Run focused MVP cloud and local compose tests.
- [x] Probe Docker/Compose availability.
- [x] Attempt cloud image smoke script and inspect first failure.
- [x] Fix production image dependency/build-context regressions exposed by runtime smoke.
- [x] Fix local demo image/script regressions exposed by runtime smoke.
- [x] Re-run focused tests after each fix.
- [x] Run the cloud image smoke script to completion.
- [x] Run the local demo compose smoke script to completion.
- [x] Document whether remaining work is implementation or environment verification.

## Step Log

- Re-read the follow-up plan and current docs/scripts for cloud runtime verification.
- Ran `/usr/bin/env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mvp_cloud_deployment_phase*.py' -v`: passed 18 tests.
- Ran `docker version` without escalation: failed with Docker socket permission denial, so Docker-backed work requires escalation in this environment.
- Ran `docker compose version`: passed, `Docker Compose version v2.39.1-desktop.1`.
- Ran `docker compose --env-file .env.example -f docker-compose.demo.yml config`: passed and rendered the demo compose configuration.
- Ran `/usr/bin/env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_local_demo_compose*.py' -v` with localhost/Docker escalation: passed 10 tests.
- Ran `docker version` with escalation: passed; Docker Desktop/Engine are available.
- Ran `sh deploy/cloud/smoke-images.sh` with escalation: failed before image build because the script resolved `REPO_ROOT` to `ophanix-platform/packages`, while the Dockerfiles copy `packages/product-platform/...`.
- Updated `deploy/cloud/smoke-images.sh` to resolve `REPO_ROOT` to the monorepo root using `../../../..`.
- Removed the unused `# syntax=docker/dockerfile:1.7` directive from `deploy/cloud/Dockerfile.frontend`.
- Added regression assertions in `tests/test_mvp_cloud_deployment_phase1.py` that all image smoke builds use the monorepo root context.
- Re-ran `/usr/bin/env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mvp_cloud_deployment_phase1.py' -v`: passed 4 tests.
- Re-ran `sh deploy/cloud/smoke-images.sh` with escalation: API, worker, and frontend images built successfully, and the frontend production build passed inside Docker. The runtime probe then failed when the API container imported `EmailStr` because `email-validator` is not installed by the production package metadata.
- Updated `pyproject.toml` to declare `pydantic[email]>=2.4.0,<3.0`.
- Added `tests/test_mvp_cloud_deployment_phase1.py::test_production_package_installs_email_validation_dependency` to guard that production package metadata includes the email validation dependency.
- Re-ran `/usr/bin/env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mvp_cloud_deployment_phase1.py' -v`: passed 5 tests.
- Re-ran `sh deploy/cloud/smoke-images.sh` with escalation: the API image installed `email-validator` successfully, then failed during API startup because `product_platform.agents.credentials` imports `agentmesh.identity.credentials` and the production image does not install the local AgentMesh package.
- Updated `pyproject.toml` to declare `agentmesh-platform>=3.1.0,<4.0`.
- Updated `deploy/cloud/Dockerfile.api` and `deploy/cloud/Dockerfile.worker` to copy and install `packages/agent-mesh` before `packages/product-platform`.
- Extended `tests/test_mvp_cloud_deployment_phase1.py` to assert the API/worker images install the local AgentMesh package and product-platform metadata declares the dependency.
- Re-ran `/usr/bin/env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mvp_cloud_deployment_phase1.py' -v`: passed 5 tests.
- Re-ran `sh deploy/cloud/smoke-images.sh` with escalation: the API image installed local `agentmesh_platform==3.1.0` successfully, then failed during API startup because `product_platform.discovery.findings` imports `agent_discovery.models` and the production image does not install the local `packages/agent-discovery` package.
- Updated `pyproject.toml` to declare `agent-discovery>=0.1.0,<1.0`.
- Updated `deploy/cloud/Dockerfile.api` and `deploy/cloud/Dockerfile.worker` to copy and install `packages/agent-discovery` between `packages/agent-mesh` and `packages/product-platform`.
- Extended `tests/test_mvp_cloud_deployment_phase1.py` to assert the API/worker images install local Agent Discovery and product-platform metadata declares the dependency.
- Re-ran `/usr/bin/env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mvp_cloud_deployment_phase1.py' -v`: passed 5 tests.
- Re-ran `sh deploy/cloud/smoke-images.sh` with escalation: passed. The script rebuilt API/worker/frontend images, applied migrations `0001` through `0049`, successfully probed `/health` and `/ready`, ran `worker noop`, and printed `Product platform image smoke checks passed.`
- Re-ran `/usr/bin/env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_mvp_cloud_deployment_phase*.py' -v`: passed 19 tests.
- Inspected `Dockerfile.demo` before running the local demo smoke and found it had the same production runtime package gap as the API/worker cloud images.
- Updated `Dockerfile.demo` to build from the monorepo root, install local `packages/agent-mesh` and `packages/agent-discovery`, copy product-platform `README.md`, and remove the unused Dockerfile frontend syntax directive.
- Added `tests/test_local_demo_compose_phase1.py::test_demo_dockerfile_installs_runtime_sibling_packages` to guard the demo image dependency installs.
- Ran `/usr/bin/env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_local_demo_compose*.py' -v`: initially failed one assertion because the smoke script still checked `run["scenario_id"] == "customer-support-refund"`, while the API response exposes that value as `run["scenario"]["slug"]`.
- Updated `deploy/local-demo-smoke.sh` to assert `run["scenario"]["slug"] == "customer-support-refund"`.
- Re-ran `/usr/bin/env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_local_demo_compose*.py' -v` with localhost/Docker escalation: passed 11 tests.
- Ran `sh deploy/local-demo-smoke.sh` with Docker escalation: the stack built and all services became healthy, then the host-side scenario check failed because the script invoked `python`, which is not present in this environment.
- Updated `deploy/local-demo-smoke.sh` to use `${PYTHON:-python3}` and added a regression assertion in `tests/test_local_demo_compose_phase4.py`.
- Re-ran `/usr/bin/env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_local_demo_compose*.py' -v` with escalation: passed 11 tests.
- Re-ran `sh deploy/local-demo-smoke.sh` with escalation: the stack became healthy, then failed on the scenario id assertion. The script was still asserting the API's seeded scenario id where the smoke flow needs the public scenario slug.
- Completed the slug assertion fix in `deploy/local-demo-smoke.sh` and extended `tests/test_local_demo_compose_phase4.py` to guard it.
- Re-ran `/usr/bin/env PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_local_demo_compose*.py' -v` with escalation: passed 11 tests.
- Re-ran `sh deploy/local-demo-smoke.sh` with escalation: passed. The script started the full demo stack, confirmed the seeded integrations/credentials/scenario checks, executed the customer-support-refund scenario, verified SSE activity, probed the frontend, checked the sample MCP server, and printed `Local demo compose smoke checks passed.`
- Ran `docker ps --format '{{.Names}} {{.Status}}'` with escalation after the local demo smoke: no running containers were listed.

## Resolved Findings

The follow-up is no longer just a verification blocker. Runtime image smoke exposed production packaging bugs:

- The API imports Pydantic `EmailStr`, which requires the `email-validator` package. Fixed by declaring `pydantic[email]`.
- The API imports `agentmesh.identity.credentials`, but the API/worker Dockerfiles only installed `packages/product-platform`. Fixed by declaring `agentmesh-platform` and installing local `packages/agent-mesh`.
- The API imports `agent_discovery.models`, but the API/worker Dockerfiles did not install local `packages/agent-discovery`. Fixed by declaring `agent-discovery` and installing local `packages/agent-discovery`.
- The local demo image used the same incomplete package installation path. Fixed by installing the same local sibling runtime packages in `Dockerfile.demo`.
- The local demo smoke script assumed a `python` binary and asserted the scenario slug against `scenario_id`. Fixed by using `${PYTHON:-python3}` and asserting the response's `scenario.slug`.

## Completion Summary

This follow-up is complete. The production cloud image smoke and local demo compose smoke both now run against the actual containers and pass in this environment. The plan's PostgreSQL runtime question remains a documented pilot-scope constraint rather than missing implementation: the current cloud smoke validates the supported SQLite-on-volume preview path, and no new PostgreSQL follow-up is required from this phase.
