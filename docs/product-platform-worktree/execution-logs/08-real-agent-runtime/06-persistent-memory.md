# Phase 6 Execution Log - Persistent Memory

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
| 7 | Observability | Make every run debuggable from logs, DB rows, traces, and Tool Gateway UI. | Not Started | JSON logs, IDs everywhere, optional Logfire/Langfuse, observability smoke. |
| 8 | Cloud Persistence | Run the same E2E with a real cloud Postgres database. | Not Started | Postgres URL support, migrations, claim lookup against Neon, inspect rows. |
| 9 | Production Hardening | Prepare for safe long-running experimentation. | Not Started | Pins, allowlists, approval policies, cost guards, retries, redaction/prompt-injection tests. |

## Detailed Checklist

- [x] Re-read earlier logs and implementation plan before starting.
- [x] Implement memory repository wrappers if not already complete.
- [x] Add `memory list`.
- [x] Add `memory get`.
- [x] Add `memory put`.
- [x] Add `memory search`.
- [x] Add memory tools available to the agent.
- [x] Include tenant/user memory context in full-run prompt.
- [x] Add task summary extraction after runs.
- [x] Add deterministic tests for scoped memory behavior.
- [x] Run two-process memory persistence check.
- [x] Run two-task memory E2E when real agent is available. Current environment lacks `OPENROUTER_API_KEY`; opt-in test is ready and skips honestly until credentials are supplied.

## Step Notes

- 2026-05-07: Re-read Phase 5 log and Phase 6 plan. The `agent_memory` table and tenant/user scoped repository methods already exist from Phase 1; Phase 6 will add CLI commands, an MCP memory server backed by the same DB, run prompt memory context, and extraction tests.
- 2026-05-07: Added CLI commands `memory put`, `memory get`, `memory search`, and `memory list`. Each command applies migrations before using the repository and emits structured log events.
- 2026-05-07: Added `mcp_memory_server.py`, a FastMCP stdio server backed by the runtime database with tools `memory_put`, `memory_get`, and `memory_search`. Added the `memory` server to `examples/real-agent-runtime/mcp.local.json`.
- 2026-05-07: Updated full-run prompt construction to include durable memory tenant/user IDs and instruct the model to use memory MCP tools for remember/recall/preference tasks.
- 2026-05-07: Added explicit memory extraction after successful runs for tasks containing `Remember that...` or `Save this as durable memory`; extracted memories are tenant/user scoped and checkpointed by memory id.
- 2026-05-07: Added tests for memory extraction and real MCP memory persistence across separate stdio server processes. Focused run `.venv-agent/bin/python -m pytest tests/real_agent_runtime/test_full_agent_run.py tests/real_agent_runtime/test_memory_runtime.py -vv`; result `7 passed in 4.01s`.
- 2026-05-07: Verified memory CLI across separate Python processes with a temp SQLite DB. `memory put` created `mem_a3e2e52135d2424d9129462dfd32f6e1`; `memory get`, `memory search --query concise`, and `memory list` all returned `Use concise operational summaries.`
- 2026-05-07: Added `tests/real_agent_runtime/test_real_memory_agent_flow.py`, a credential-gated two-task real E2E for remembering a concise-summary preference and using it in a later run. Default run result: `1 skipped`.
- 2026-05-07: Ran `mcp config-check`; output includes the new `memory` server. Ran `mcp list-tools --server memory`; output lists `memory_put`, `memory_get`, and `memory_search`.
- 2026-05-07: Ran full default test suite; result `30 passed, 5 skipped in 5.30s`. Expected skips: real full agent E2E, real filesystem MCP opt-in, real two-task memory E2E, real OpenRouter smoke, and real Tool Gateway opt-in.

## Phase Completion Summary

- Implemented: memory CLI, DB-backed memory MCP server, MCP config registration, full-run memory context, explicit memory extraction, and checkpointing extracted memory ids.
- Verified: repository scoped memory tests, real memory MCP subprocess persistence, CLI persistence across separate Python invocations, memory tool listing, and full default pytest suite.
- Credential-gated acceptance: two-task real memory run requires `OPENROUTER_API_KEY`; opt-in test is ready once credentials are supplied.
- Next phase adds observability smoke and stronger run/log correlation checks.
