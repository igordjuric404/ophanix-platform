# Phase 0 Execution Log - Research, Credentials, And Environment

## Phase Overview

| Phase | Name | Goal | Status | Biggest checklist items |
| --- | --- | --- | --- | --- |
| 0 | Research, Credentials, And Environment | Prove OpenRouter, local folders, and product-platform startup are available. | Done | Env files/folders created; product-platform API health verified; real OpenRouter and Tool Gateway token checks are externally blocked until credentials are provided. |
| 1 | Runtime Skeleton And DB Persistence | Create a CLI that can load config, migrate DB, and persist a run. | Not Started | Package skeleton, config, migrations, repository, DB/runs CLI, SQLite unit tests. |
| 2 | Real OpenRouter Agent Call | Run a real Pydantic AI agent call through OpenRouter and persist the result. | Not Started | Model factory, `llm smoke`, retry/backoff, persisted messages/errors, real-provider test. |
| 3 | Real MCP Server Integration | Spawn real MCP servers and expose their tools to the agent. | Not Started | MCP config parser, stdio startup, config-check, list-tools, filesystem/git E2E. |
| 4 | Tool Gateway MCP Wrapper | Let the agent call governed Ophanix tools through MCP and Tool Gateway. | Not Started | MCP server, governed list/call/action tools, smoke command, allowed/denied calls. |
| 5 | Full Agent Run Loop | Run a multi-step task using LLM, MCP, Tool Gateway, DB persistence, and artifacts. | Not Started | `run`, toolsets, instructions, step limits, persisted evidence, claim lookup E2E. |
| 6 | Persistent Memory | Add durable memory that survives process restarts. | Not Started | Memory repository, memory CLI, memory tools, task summary extraction, two-task E2E. |
| 7 | Observability | Make every run debuggable from logs, DB rows, traces, and Tool Gateway UI. | Not Started | JSON logs, IDs everywhere, optional Logfire/Langfuse, observability smoke. |
| 8 | Cloud Persistence | Run the same E2E with a real cloud Postgres database. | Not Started | Postgres URL support, migrations, claim lookup against Neon, inspect rows. |
| 9 | Production Hardening | Prepare for safe long-running experimentation. | Not Started | Pins, allowlists, approval policies, cost guards, retries, redaction/prompt-injection tests. |

## Detailed Checklist

- [x] Read the full implementation plan.
- [x] Create dedicated execution-log directory.
- [x] Create initial phase execution log files.
- [x] Confirm `agent-demo` exists and identify whether it has existing files.
- [x] Check whether `OPENROUTER_API_KEY` is present without exposing it.
- [x] Check whether `OPHANIX_TOOL_GATEWAY_TOKEN` is present without exposing it.
- [x] Check Python version.
- [x] Check MCP launcher availability (`npx`, `uvx`).
- [x] Check whether product-platform API health endpoint is already running.
- [x] Create `agent-demo/.env.real-agent.example`.
- [x] Create `agent-demo/.env.real-agent` from the example if it does not exist.
- [x] Create `agent-demo/.local/real-agent/sandbox/input`.
- [x] Create `agent-demo/.local/real-agent/sandbox/output`.
- [x] Create `agent-demo/.local/real-agent/logs`.
- [x] Run direct OpenRouter HTTP smoke when credentials are available.
- [x] Start or verify product-platform API locally.
- [x] Verify Tool Gateway API/UI availability when the product-platform service is running.
- [x] Document blockers and handoff facts for Phase 1.

## Step Notes

- 2026-05-07: Read the full implementation plan from `ophanix-platform/docs/product-platform-worktree/implementation-plans/08-real-agent-runtime/01-real-agent-mcp-runtime.md`.
- 2026-05-07: Chosen implementation target is the user-requested `agent-demo` directory, while reusing existing product-platform Tool Gateway API/SDK concepts.
- 2026-05-07: Web docs checked: Pydantic AI OpenRouter provider and MCP client docs, MCP SDK/transports docs.
- 2026-05-07: `agent-demo` exists and is effectively empty.
- 2026-05-07: `OPENROUTER_API_KEY` is not present in the current shell environment.
- 2026-05-07: `OPHANIX_TOOL_GATEWAY_TOKEN` is not present in the current shell environment.
- 2026-05-07: Python is available as `Python 3.13.7`.
- 2026-05-07: `npx` is available at `/Users/igodju/.nvm/versions/node/v22.18.0/bin/npx`.
- 2026-05-07: `uvx` is not available.
- 2026-05-07: `curl http://127.0.0.1:8088/health` failed to connect; product-platform API is not already running.
- 2026-05-07: Added `agent-demo/.env.real-agent.example` and blank local `agent-demo/.env.real-agent`.
- 2026-05-07: Added `agent-demo/.gitignore` to keep local env, virtualenv, cache, and `.local/` runtime artifacts out of source tracking.
- 2026-05-07: Created `.local/real-agent/sandbox/input`, `.local/real-agent/sandbox/output`, and `.local/real-agent/logs` under `agent-demo`; `test -d` checks passed.
- 2026-05-07: Added deterministic claim lookup task and sandbox input fixture for later E2E phases.
- 2026-05-07: Product-platform CLI help succeeded with commands `serve`, `db`, `worker`, and `demo-service`.
- 2026-05-07: Mistakenly started `db migrate` and `db seed` in parallel against `/private/tmp/ophanix_real_agent_phase0.db`; `seed` succeeded but `migrate` failed with `sqlite3.IntegrityError: UNIQUE constraint failed: schema_migrations.version`. Root cause was the parallel ordering race. Fix was to retry sequentially against a fresh temp DB.
- 2026-05-07: Sequential retry against `/private/tmp/ophanix_real_agent_phase0_seq.db` succeeded. `db migrate` applied migrations `0001` through `0055`; `db seed` printed `Seeded demo data`.
- 2026-05-07: Starting product-platform API inside the sandbox failed with `ERROR: [Errno 1] error while attempting to bind on address ('127.0.0.1', 8088): [errno 1] operation not permitted`. Reran with approved escalation because the local server bind is required for real API checks.
- 2026-05-07: Product-platform API started successfully in session `27577` with `PYTHONPATH=src OPHANIX_DATABASE_URL=sqlite:////private/tmp/ophanix_real_agent_phase0_seq.db python3 -m product_platform.cli serve --host 127.0.0.1 --port 8088`.
- 2026-05-07: Escalated `curl http://127.0.0.1:8088/health` returned HTTP 200 with `status=ok`, database healthy with 55 migrations, worker healthy, event store healthy, Redis not configured, and model provider not configured.
- 2026-05-07: Escalated `curl -i http://127.0.0.1:8088/api/v1/tools` returned HTTP 401 `UNAUTHENTICATED`, confirming the Tool Gateway route is mounted and authentication is enforced. `OPHANIX_TOOL_GATEWAY_TOKEN` remains unset, so authorized gateway smoke is deferred until Phase 4/token availability.
- 2026-05-07: Escalated `curl -i http://127.0.0.1:8088/` returned HTTP 404 because this command starts the API only, not the frontend UI. Tool Gateway visual page verification remains a manual/frontend follow-up unless `./start.sh` or frontend dev server is launched later.
- 2026-05-07: Direct OpenRouter smoke could not be run because neither the environment nor `agent-demo/.env.real-agent` contains `OPENROUTER_API_KEY`. The code will keep the real smoke path and mark real-provider tests skipped until the key is supplied.
- 2026-05-07: Phase 0 is closed for implementation purposes with explicit external blockers: OpenRouter API key, Tool Gateway bearer token, and frontend UI process.
