# Phase 1 Execution Log - Runtime Skeleton And DB Persistence

## Phase Overview

| Phase | Name | Goal | Status | Biggest checklist items |
| --- | --- | --- | --- | --- |
| 0 | Research, Credentials, And Environment | Prove OpenRouter, local folders, and product-platform startup are available. | Done | Env files/folders created; product-platform API health verified; real OpenRouter and Tool Gateway token checks are externally blocked until credentials are provided. |
| 1 | Runtime Skeleton And DB Persistence | Create a CLI that can load config, migrate DB, and persist a run. | Done | Package skeleton, config, migrations, repository, DB/runs CLI, SQLite unit tests. |
| 2 | Real OpenRouter Agent Call | Run a real Pydantic AI agent call through OpenRouter and persist the result. | Not Started | Model factory, `llm smoke`, retry/backoff, persisted messages/errors, real-provider test. |
| 3 | Real MCP Server Integration | Spawn real MCP servers and expose their tools to the agent. | Not Started | MCP config parser, stdio startup, config-check, list-tools, filesystem/git E2E. |
| 4 | Tool Gateway MCP Wrapper | Let the agent call governed Ophanix tools through MCP and Tool Gateway. | Not Started | MCP server, governed list/call/action tools, smoke command, allowed/denied calls. |
| 5 | Full Agent Run Loop | Run a multi-step task using LLM, MCP, Tool Gateway, DB persistence, and artifacts. | Not Started | `run`, toolsets, instructions, step limits, persisted evidence, claim lookup E2E. |
| 6 | Persistent Memory | Add durable memory that survives process restarts. | Not Started | Memory repository, memory CLI, memory tools, task summary extraction, two-task E2E. |
| 7 | Observability | Make every run debuggable from logs, DB rows, traces, and Tool Gateway UI. | Not Started | JSON logs, IDs everywhere, optional Logfire/Langfuse, observability smoke. |
| 8 | Cloud Persistence | Run the same E2E with a real cloud Postgres database. | Not Started | Postgres URL support, migrations, claim lookup against Neon, inspect rows. |
| 9 | Production Hardening | Prepare for safe long-running experimentation. | Not Started | Pins, allowlists, approval policies, cost guards, retries, redaction/prompt-injection tests. |

## Detailed Checklist

- [x] Re-read Phase 0 log and implementation plan before starting.
- [x] Create Python project metadata in `agent-demo/pyproject.toml`.
- [x] Create `agent_demo` package and `real_agent_runtime` modules.
- [x] Add Typer CLI entry point.
- [x] Implement `.env.real-agent` loading.
- [x] Implement config validation, path resolution, and secret redaction.
- [x] Add SQL migration files for runtime tables.
- [x] Implement SQLite/Postgres-aware DB connection helpers.
- [x] Implement repository methods for runs, messages, tool calls, memory, checkpoints.
- [x] Add `config print` command.
- [x] Add `db migrate` command.
- [x] Add `db inspect` command.
- [x] Add `runs list` command.
- [x] Add `runs show` command.
- [x] Add deterministic unit tests for config.
- [x] Add deterministic unit tests for repository behavior against real SQLite.
- [x] Run the smallest test after each chunk and record observed output.

## Step Notes

- 2026-05-07: Re-read Phase 0 log and Phase 1 implementation plan before making Phase 1 edits.
- 2026-05-07: Implementation target remains standalone `agent-demo`, with CLI module `agent_demo.real_agent_runtime.cli`.
- 2026-05-07: Dependency probe found global `pydantic`, `rich`, `httpx`, `dotenv`, and `structlog`; missing globally: `typer`, `sqlalchemy`, `aiosqlite`, `pytest`, `pydantic_ai`, and `mcp`. Plan is to declare dependencies in `agent-demo/pyproject.toml` and install into local `.venv-agent`.
- 2026-05-07: Added `agent-demo/pyproject.toml` with runtime dependencies and test extras, `README.md`, and package init files under `src/agent_demo`.
- 2026-05-07: Import check passed: `PYTHONPATH=src python3 -c "import agent_demo; print(agent_demo.__version__)"` printed `0.1.0`.
- 2026-05-07: Added `agent_demo.real_agent_runtime.config` with `.env.real-agent` loading, environment override support, Pydantic validation, project-relative path resolution, SQLite URL normalization, sandbox escape guard, required OpenRouter/Tool Gateway helper methods, and secret/database URL redaction.
- 2026-05-07: Config smoke passed: loading `agent-demo/.env.real-agent` resolved database URL to `sqlite:////Users/igodju/Projects/Personal/ophanix/agent-demo/.local/real-agent/agent.sqlite3`, sandbox to `/Users/igodju/Projects/Personal/ophanix/agent-demo/.local/real-agent/sandbox`, and redacted empty OpenRouter key as `None`.
- 2026-05-07: Sandbox guard smoke passed: `OPHANIX_AGENT_SANDBOX_DIR=/tmp/outside` raised a `RuntimeConfigError` saying the sandbox is outside the project root.
- 2026-05-07: Created `agent-demo/.venv-agent` with `python3 -m venv .venv-agent`.
- 2026-05-07: Sandboxed `.venv-agent/bin/python -m pip install -e ".[test]"` failed because DNS/network was blocked while resolving `hatchling`. Retried with approved escalation as required by the sandbox policy.
- 2026-05-07: Escalated dependency install succeeded. Notable installed packages: `pydantic-ai-slim==1.91.0`, `mcp==1.27.0`, `sqlalchemy==2.0.49`, `typer==0.25.1`, `pytest==9.0.3`, `pytest-asyncio==1.3.0`.
- 2026-05-07: Dependency import check passed: `.venv-agent/bin/python -c "from pydantic_ai import Agent; from pydantic_ai.mcp import MCPServerStdio; import sqlalchemy; print(sqlalchemy.__version__)"` printed Pydantic AI classes and SQLAlchemy `2.0.49`.
- 2026-05-07: Added migration SQL `0001_real_agent_runtime.up.sql` and `.down.sql` under `agent-demo/src/agent_demo/real_agent_runtime/migrations`.
- 2026-05-07: Added `models.py`, `db.py`, and `repository.py` with SQLAlchemy engine creation, migration runner, table inspection, run/message/tool/memory/checkpoint persistence, JSON serialization, and exact memory search.
- 2026-05-07: Repository smoke passed against real SQLite: migration returned `['0001']`; after create/append/finish operations, detail printed `completed 1 1 1 phase1`; table inspect showed `agent_runs=1`.
- 2026-05-07: Added `logging.py` with JSON-lines log events and `cli.py` with Typer commands: `config print`, `db migrate`, `db inspect`, `runs list`, and `runs show`.
- 2026-05-07: First `config print` exposed a bug: `OPHANIX_AGENT_MAX_OUTPUT_TOKENS` was redacted as `***` because the redactor matched `TOKENS`. Fixed redaction to only match `_TOKEN`, `_KEY`, `_API_KEY`, `SECRET`, `PASSWORD`, and `CREDENTIAL`, and normalized blank Logfire/Langfuse secrets to `None`.
- 2026-05-07: Retested `config print`; output now shows `OPHANIX_AGENT_MAX_OUTPUT_TOKENS` as `900` and secret values as `null`.
- 2026-05-07: CLI DB checks passed against `agent-demo/.local/real-agent/agent.sqlite3`: `db migrate` printed `Applied migrations: 0001`; `db inspect` showed all runtime tables and `schema_migrations=1`.
- 2026-05-07: CLI run inspection passed after inserting a repository smoke run. `runs list` displayed the completed run, and `runs show run_1497d9e96cc247a485c05da187d5c395` returned one completed run with one user message.
- 2026-05-07: JSON-lines log validation passed: `.venv-agent/bin/python -c "import json; ..."` printed `logs-ok`.
- 2026-05-07: Added config tests covering path resolution, required secrets helpers, redaction, sandbox rejection, and explicit external sandbox allowance.
- 2026-05-07: Added repository tests covering real SQLite migration, run/message/tool/checkpoint/memory persistence, memory search, and tenant/user scoping.
- 2026-05-07: Narrow Phase 1 pytest passed: `6 passed in 0.15s`.
- 2026-05-07: Full current `agent-demo` pytest passed: `6 passed in 0.14s`.
- 2026-05-07: Phase 1 complete. Remaining external blockers are not Phase 1 code blockers: OpenRouter key, Tool Gateway token, and frontend UI process.
