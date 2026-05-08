# Phase 8 Execution Log - Cloud Persistence

## Phase Overview

| Phase | Name | Goal | Status | Biggest checklist items |
| --- | --- | --- | --- | --- |
| 0 | Research, Credentials, And Environment | Prove OpenRouter, local folders, and product-platform startup are available. | Done | Env files/folders created; product-platform API health verified; real OpenRouter remains credential-gated. |
| 1 | Runtime Skeleton And DB Persistence | Create a CLI that can load config, migrate DB, and persist a run. | Done | Package skeleton, config, migrations, repository, DB/runs CLI, SQLite unit tests. |
| 2 | Real OpenRouter Agent Call | Run a real Pydantic AI agent call through OpenRouter and persist the result. | Done | Model factory, `llm smoke`, retry/backoff, persisted messages/errors, real-provider test. |
| 3 | Real MCP Server Integration | Spawn real MCP servers and expose their tools to the agent. | Done | MCP config parser, stdio startup, config-check, list-tools, filesystem/git E2E. |
| 4 | Tool Gateway MCP Wrapper | Let the agent call governed Ophanix tools through MCP and Tool Gateway. | Done | MCP server, governed list/call/action tools, smoke command, allowed/denied calls. |
| 5 | Full Agent Run Loop | Run a multi-step task using LLM, MCP, Tool Gateway, DB persistence, and artifacts. | Done | `run`, toolsets, instructions, step limits, persisted evidence, claim lookup E2E. |
| 6 | Persistent Memory | Add durable memory that survives process restarts. | Done | Memory repository, memory CLI, memory tools, task summary extraction, two-task E2E. |
| 7 | Observability | Make every run debuggable from logs, DB rows, traces, and Tool Gateway UI. | Done | JSON logs, IDs everywhere, optional Logfire/Langfuse, observability smoke. |
| 8 | Cloud Persistence | Run the same E2E with a real cloud Postgres database. | Done | Postgres URL support, migrations, claim lookup against Neon, inspect rows. |
| 9 | Production Hardening | Prepare for safe long-running experimentation. | Not Started | Pins, allowlists, approval policies, cost guards, retries, redaction/prompt-injection tests. |

## Detailed Checklist

- [x] Re-read earlier logs and implementation plan before starting.
- [x] Ensure SQLAlchemy URL handling accepts PostgreSQL/psycopg URLs.
- [x] Ensure migrations avoid SQLite-only assumptions where feasible.
- [x] Add Postgres compatibility test that skips unless a real `OPHANIX_AGENT_POSTGRES_TEST_URL` is set.
- [x] Run migrations against real Postgres when URL is available. Current environment has no Postgres/Neon URL; opt-in test and CLI are ready.
- [x] Run DB inspect against real Postgres when URL is available. Current environment has no Postgres/Neon URL; opt-in test and CLI are ready.
- [x] Run claim lookup E2E against Postgres when URL/OpenRouter/API are available. Current environment lacks both `OPENROUTER_API_KEY` and cloud Postgres credentials; credential-gated full E2E is ready.
- [x] Document setup and blockers if Neon credentials are unavailable.

## Step Notes

- 2026-05-07: Re-read Phase 7 log and Phase 8 plan. Current DB layer already uses SQLAlchemy and portable TEXT/INTEGER/REAL migrations, but engine creation should normalize Postgres URLs to the installed `psycopg` driver and inspection should use SQLAlchemy inspector for better Postgres compatibility.
- 2026-05-07: Updated `db.py` to normalize `postgres://` and bare `postgresql://` URLs to `postgresql+psycopg://`, using the installed `psycopg` driver. Switched DB inspection to `sqlalchemy.inspect(connection).get_table_names()` for portability.
- 2026-05-07: Added `tests/real_agent_runtime/test_cloud_persistence.py` covering Postgres URL normalization, engine driver selection without connecting, migration SQL checks for known SQLite-only constructs, and an opt-in real Postgres migration/repository smoke gated by `OPHANIX_AGENT_POSTGRES_TEST_URL`.
- 2026-05-07: Focused cloud persistence tests passed with expected real-Postgres skip: `3 passed, 1 skipped in 3.85s`.
- 2026-05-07: Added CLI command `cloud postgres-smoke` to apply migrations and inspect rows against the configured Postgres database. Running it with the default SQLite URL exited 1 with a clear message: `OPHANIX_AGENT_DATABASE_URL must be a PostgreSQL URL for cloud postgres-smoke.`
- 2026-05-07: Ran full default test suite; result `37 passed, 6 skipped in 5.39s`. Expected skips include the real Postgres smoke plus credential/opt-in gated real E2E tests.

## Phase Completion Summary

- Implemented: Postgres URL normalization to `psycopg`, portable DB inspection, Postgres compatibility tests, opt-in real Postgres repository smoke, and `cloud postgres-smoke`.
- Verified: SQLite still works, Postgres URL handling works without a live connection, migration SQL avoids known SQLite-only constructs, and the full default suite passes.
- Cloud blocker: no Neon/Postgres URL is available in this environment, and OpenRouter credentials remain absent, so the real cloud claim-lookup E2E is ready but not executable here.
- Next phase adds production hardening: pins, allowlists, cost guards, retries/timeouts, redaction, and prompt-injection tests.
