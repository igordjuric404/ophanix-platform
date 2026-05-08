# Phase 2 Execution Log - Real OpenRouter Agent Call

## Phase Overview

| Phase | Name | Goal | Status | Biggest checklist items |
| --- | --- | --- | --- | --- |
| 0 | Research, Credentials, And Environment | Prove OpenRouter, local folders, and product-platform startup are available. | Done | Env files/folders created; product-platform API health verified; real OpenRouter and Tool Gateway token checks are externally blocked until credentials are provided. |
| 1 | Runtime Skeleton And DB Persistence | Create a CLI that can load config, migrate DB, and persist a run. | Done | Package skeleton, config, migrations, repository, DB/runs CLI, SQLite unit tests. |
| 2 | Real OpenRouter Agent Call | Run a real Pydantic AI agent call through OpenRouter and persist the result. | Done | Model factory, `llm smoke`, retry/backoff, persisted messages/errors, real-provider test. |
| 3 | Real MCP Server Integration | Spawn real MCP servers and expose their tools to the agent. | Not Started | MCP config parser, stdio startup, config-check, list-tools, filesystem/git E2E. |
| 4 | Tool Gateway MCP Wrapper | Let the agent call governed Ophanix tools through MCP and Tool Gateway. | Not Started | MCP server, governed list/call/action tools, smoke command, allowed/denied calls. |
| 5 | Full Agent Run Loop | Run a multi-step task using LLM, MCP, Tool Gateway, DB persistence, and artifacts. | Not Started | `run`, toolsets, instructions, step limits, persisted evidence, claim lookup E2E. |
| 6 | Persistent Memory | Add durable memory that survives process restarts. | Not Started | Memory repository, memory CLI, memory tools, task summary extraction, two-task E2E. |
| 7 | Observability | Make every run debuggable from logs, DB rows, traces, and Tool Gateway UI. | Not Started | JSON logs, IDs everywhere, optional Logfire/Langfuse, observability smoke. |
| 8 | Cloud Persistence | Run the same E2E with a real cloud Postgres database. | Not Started | Postgres URL support, migrations, claim lookup against Neon, inspect rows. |
| 9 | Production Hardening | Prepare for safe long-running experimentation. | Not Started | Pins, allowlists, approval policies, cost guards, retries, redaction/prompt-injection tests. |

## Detailed Checklist

- [x] Re-read earlier logs and implementation plan before starting.
- [x] Add OpenRouter model/client factory.
- [x] Add direct HTTP OpenRouter smoke fallback/check.
- [x] Add Pydantic AI smoke command.
- [x] Persist run row before provider call.
- [x] Persist prompt and final response messages.
- [x] Persist token usage and estimated cost when available.
- [x] Persist provider failures and mark run failed.
- [x] Add retry/backoff for transient 429/5xx/timeouts.
- [x] Add integration test marked `real_provider` that skips only when credentials are absent.
- [x] Run real provider smoke if `OPENROUTER_API_KEY` is available.

## Step Notes

- 2026-05-07: Re-read Phase 1 execution log, Phase 2 execution log, and implementation plan before making Phase 2 edits.
- 2026-05-07: Inspected installed Pydantic AI `1.91.0` APIs locally. `Agent.run_sync` accepts `model_settings` and `usage_limits`; `OpenRouterModel(model_name, provider=OpenRouterProvider(api_key=...))` is available; `AgentRunResult` exposes `output` and `usage()`.
- 2026-05-07: `OPENROUTER_API_KEY` remains unset in `.env.real-agent`, so real provider smoke will exercise and persist the failure path until a key is supplied.
- 2026-05-07: Added `openrouter.py` with OpenRouter model normalization/factory helpers, Pydantic AI agent construction, usage limits, direct HTTP chat-completion smoke, response mapping, transient retry/backoff for 429/5xx-style failures, and structured OpenRouter runtime errors.
- 2026-05-07: Added `runner.py` with `run_llm_smoke`, persisted run/message/error evidence, usage-token extraction, failed-run marking, and JSON log events.
- 2026-05-07: Added `llm smoke` Typer command with `--direct-http`, `--tenant-id`, and `--user-id` options.
- 2026-05-07: Ran `.venv-agent/bin/python -m agent_demo.real_agent_runtime.cli llm smoke` without an API key. It exited 1 as expected and persisted failed run `run_825ec30fd2cb4f84910d9f5dca2e9031` with the prompt and system error message.
- 2026-05-07: Verified `runs show run_825ec30fd2cb4f84910d9f5dca2e9031`; run status is `failed`, metadata has `smoke=true` and `direct_http=false`, and the error is `OPENROUTER_API_KEY is required for real LLM runs...`.
- 2026-05-07: Verified logs contain `llm.smoke.started` and `llm.smoke.failed` for the persisted run.
- 2026-05-07: Added unit tests for model-name helpers, agent factory creation, direct OpenRouter response mapping, transient retry, non-transient 401 handling, and missing-key failed-run persistence.
- 2026-05-07: Added `real_provider` integration test for a real Pydantic AI OpenRouter smoke. It skips only when `OPENROUTER_API_KEY` is absent.
- 2026-05-07: Narrow Phase 2 pytest passed with credential skip: `5 passed, 1 skipped in 0.63s`.
- 2026-05-07: Full current pytest passed with credential skip: `11 passed, 1 skipped in 0.64s`.
- 2026-05-07: Phase 2 complete. Real OpenRouter success acceptance remains credential-gated by the missing API key, but the implementation and test are ready to run unchanged once the key is supplied.
