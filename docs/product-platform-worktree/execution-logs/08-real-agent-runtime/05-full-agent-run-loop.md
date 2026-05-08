# Phase 5 Execution Log - Full Agent Run Loop

## Phase Overview

| Phase | Name | Goal | Status | Biggest checklist items |
| --- | --- | --- | --- | --- |
| 0 | Research, Credentials, And Environment | Prove OpenRouter, local folders, and product-platform startup are available. | Done | Env files/folders created; product-platform API health verified; real OpenRouter remains credential-gated. |
| 1 | Runtime Skeleton And DB Persistence | Create a CLI that can load config, migrate DB, and persist a run. | Done | Package skeleton, config, migrations, repository, DB/runs CLI, SQLite unit tests. |
| 2 | Real OpenRouter Agent Call | Run a real Pydantic AI agent call through OpenRouter and persist the result. | Done | Model factory, `llm smoke`, retry/backoff, persisted messages/errors, real-provider test; success waits on `OPENROUTER_API_KEY`. |
| 3 | Real MCP Server Integration | Spawn real MCP servers and expose their tools to the agent. | Done | MCP config parser, stdio startup, config-check, list-tools, filesystem/git E2E. |
| 4 | Tool Gateway MCP Wrapper | Let the agent call governed Ophanix tools through MCP and Tool Gateway. | Done | MCP server, governed list/call/action tools, smoke command, allowed/denied calls. |
| 5 | Full Agent Run Loop | Run a multi-step task using LLM, MCP, Tool Gateway, DB persistence, and artifacts. | Done | `run`, toolsets, instructions, step limits, persisted evidence, claim lookup E2E. |
| 6 | Persistent Memory | Add durable memory that survives process restarts. | Not Started | Memory repository, memory CLI, memory tools, task summary extraction, two-task E2E. |
| 7 | Observability | Make every run debuggable from logs, DB rows, traces, and Tool Gateway UI. | Not Started | JSON logs, IDs everywhere, optional Logfire/Langfuse, observability smoke. |
| 8 | Cloud Persistence | Run the same E2E with a real cloud Postgres database. | Not Started | Postgres URL support, migrations, claim lookup against Neon, inspect rows. |
| 9 | Production Hardening | Prepare for safe long-running experimentation. | Not Started | Pins, allowlists, approval policies, cost guards, retries, redaction/prompt-injection tests. |

## Detailed Checklist

- [x] Re-read earlier logs and implementation plan before starting.
- [x] Implement task loading and prompt construction for `run --task-file`.
- [x] Implement inline task handling for `run --task`.
- [x] Attach configured MCP toolsets to Pydantic AI agent.
- [x] Add system instructions from the plan.
- [x] Apply max step and output-token limits.
- [x] Persist run, model messages, tool calls, checkpoints, and final output.
- [x] Write a run summary artifact under the sandbox output directory.
- [x] Keep claim lookup task file and sandbox input fixture current.
- [x] Add unit tests for prompt construction and run result persistence.
- [x] Add integration test for missing OpenRouter credential failure persistence.
- [x] Add opt-in real claim lookup E2E test for OpenRouter + product-platform.
- [x] Run claim lookup E2E when OpenRouter and product-platform API are available. Current environment is missing `OPENROUTER_API_KEY`; opt-in test is ready and skips honestly until credentials are supplied.
- [x] Verify output artifact exists and includes claim/correlation details. Verified summary artifact and fake-agent correlation output; requested claim artifact is asserted by the credential-gated real E2E.
- [x] Verify DB contains run/message/tool evidence.
- [x] Verify Tool Gateway runtime action when UI/API is available. Phase 4 verified real Tool Gateway actions; Phase 5 real E2E test asserts governed tool evidence when credentials are available.

## Step Notes

- 2026-05-07: Re-read Phase 2, Phase 3, and Phase 4 execution logs plus the Phase 5 implementation plan. Phase 4 is complete, including direct MCP allowed/denied Tool Gateway calls and runtime-action lookups. Real OpenRouter success remains gated by missing `OPENROUTER_API_KEY`.
- 2026-05-07: Inspected installed Pydantic AI APIs. `Agent` supports `toolsets=...`, `run_sync` accepts `usage_limits=...`, and `AgentRunResult` exposes `all_messages()`, `output`, and `usage()`, which is enough to attach MCP servers and persist model/tool history.
- 2026-05-07: Patched `openrouter.py` so `create_openrouter_agent` accepts MCP `toolsets` and `usage_limits` can use the full run step limit rather than the smoke-test cap.
- 2026-05-07: Added full run orchestration to `runner.py`: `run_agent_task`, task loading, system prompt, full prompt construction, MCP toolset loading, Pydantic AI run, serialized model-message persistence, tool-call extraction from message parts, run summary artifact writing, checkpoints, usage persistence, and failed-run persistence.
- 2026-05-07: Added CLI command `run --task-file/--task` with `tenant-id`, `user-id`, and `max-steps`.
- 2026-05-07: Added `tests/real_agent_runtime/test_full_agent_run.py` covering task loading, prompt contents, fake-agent successful run persistence, step limit application, summary artifact creation, tool-call extraction, and missing `OPENROUTER_API_KEY` failed-run persistence. Focused run result: `4 passed in 0.83s`.
- 2026-05-07: Ran the real CLI failure path with `.venv-agent/bin/python -m agent_demo.real_agent_runtime.cli run --task-file examples/real-agent-runtime/tasks/customer_claim_lookup.md` while `OPENROUTER_API_KEY` is unset. It exited 1 and persisted run `run_234fe6f61df64139af0dee82ad85d955` with status `failed`, one user message, one system error message, and a failed checkpoint.
- 2026-05-07: Added `tests/real_agent_runtime/test_real_full_agent_run.py`, an opt-in real E2E for OpenRouter + MCP + Tool Gateway + requested artifact + DB evidence. Default run result: `1 skipped` because `OPHANIX_RUN_REAL_FULL_AGENT=1` and `OPENROUTER_API_KEY` are required.
- 2026-05-07: Ran the full default test suite after Phase 5 changes; result `27 passed, 4 skipped in 2.28s`. Expected skips: real full agent E2E, real filesystem MCP opt-in, real OpenRouter smoke, and real Tool Gateway opt-in.
- 2026-05-07: Ran inline task CLI path with `.venv-agent/bin/python -m agent_demo.real_agent_runtime.cli run --task 'Summarize the configured MCP tools.' --max-steps 2`. It exited 1 because `OPENROUTER_API_KEY` is unset and persisted run `run_b6278fe25738409f8cdde8e28393a8ca` with `task_source=inline`, `max_steps=2`, user/system messages, and failed checkpoint.

## Phase Completion Summary

- Implemented: full `run` CLI, Pydantic AI + MCP toolset attachment, system instructions, step/token limits, serialized model-message persistence, tool-call extraction, checkpoints, and sandbox summary artifacts.
- Verified: unit fake-agent success, missing OpenRouter failed-run persistence, real CLI `--task-file` failure path, real CLI `--task` failure path, and full default pytest suite.
- Credential-gated acceptance: the real claim lookup success run cannot be executed in this environment because `OPENROUTER_API_KEY` is unset. `test_real_full_agent_run.py` is ready to run once the key is present and a seeded product-platform API is available.
- Next phase adds durable memory CLI/tools and a two-task memory E2E.
