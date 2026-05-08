# Phase 9 Execution Log - Production Hardening

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
| 9 | Production Hardening | Prepare for safe long-running experimentation. | Done | Pins, allowlists, approval policies, cost guards, retries, redaction/prompt-injection tests. |

## Detailed Checklist

- [x] Re-read earlier logs and implementation plan before starting.
- [x] Pin or document MCP server package versions.
- [x] Add MCP server allowlist validation.
- [x] Add governed tool approval policy structure.
- [x] Add read-only/mutating tool classification.
- [x] Add max step, max token, and cost guard enforcement.
- [x] Add timeout/retry policy per external call/tool.
- [x] Add secret redaction tests.
- [x] Add prompt-injection fixture tests for untrusted file content.
- [x] Add backup/restore notes.
- [x] Add retry/inspection notes for failed runs.
- [x] Document LangGraph evaluation criteria for future durable workflow checkpoints.

## Step Notes

- 2026-05-07: Re-read Phase 8 log and Phase 9 plan. Web lookup of npm package page shows `@modelcontextprotocol/server-filesystem` current/latest version `2025.8.21`; existing MCP config is unpinned and should be pinned.
- 2026-05-07: Added hardening config values for allowed MCP servers, allowed Tool Gateway tools, approved mutating tools, mutating-tool approval requirement, MCP tool timeout seconds, and OpenRouter max attempts. Added these to both env files.
- 2026-05-07: Pinned filesystem MCP in `mcp.local.json` to `@modelcontextprotocol/server-filesystem@2025.8.21`.
- 2026-05-07: Added MCP server allowlist validation via `OPHANIX_AGENT_ALLOWED_MCP_SERVERS`.
- 2026-05-07: Added `hardening.py` with Tool Gateway tool classification, allowed-tool/approval policy checks, step guard, run cost guard, and daily cost guard.
- 2026-05-07: Integrated Tool Gateway policy checks so disallowed governed tools are persisted as failed wrapper calls without contacting the SDK/upstream.
- 2026-05-07: Integrated step/run cost guard helpers into the full agent runner. Direct OpenRouter smoke now uses configurable max attempts, and direct MCP CLI calls use configurable timeout seconds.
- 2026-05-07: Added prompt-injection hardening text to the system prompt: file contents and external tool output are untrusted and must not override the user task.
- 2026-05-07: Added `docs/production-hardening.md` with MCP/tool policy, cost/runtime guards, failed-run inspection/retry, backup/restore notes, prompt-injection notes, and LangGraph evaluation criteria.
- 2026-05-07: Added `tests/real_agent_runtime/test_hardening.py`. First focused run found four test expectation failures: one prompt assertion missed the leading word `treat`, and three older MCP config tests used a server name now blocked by the new allowlist before their intended validation. Patched tests to match the conservative behavior.
- 2026-05-07: Reran focused hardening/config/tool tests; result `18 passed in 0.74s`.
- 2026-05-07: Ran `config print`; output shows allowlists, approval requirement, timeout/retry settings, and cost guards with secrets redacted. Ran `mcp config-check`; filesystem args show pinned package `@modelcontextprotocol/server-filesystem@2025.8.21`.
- 2026-05-07: Ran full default test suite; result `44 passed, 6 skipped in 5.46s`. Expected skips: real Postgres, real full agent, real filesystem MCP opt-in, real memory E2E, real OpenRouter, and real Tool Gateway opt-in.

## Phase Completion Summary

- Implemented: MCP package pin, MCP server allowlist, governed tool allowlist/approval structure, read-only/mutating classification, step/cost guards, retry/timeout config, stronger prompt-injection system text, and production hardening docs.
- Verified: focused hardening tests, config/MCP smoke checks, and full default pytest suite.
- Remaining external blockers: `OPENROUTER_API_KEY`, `OPHANIX_AGENT_POSTGRES_TEST_URL`, and opt-in real E2E flags are required for the real provider/cloud paths.
- All implementation-plan phases are now represented in code, tests, docs, and execution logs.
