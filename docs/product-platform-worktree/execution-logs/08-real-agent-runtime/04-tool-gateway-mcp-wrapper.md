# Phase 4 Execution Log - Tool Gateway MCP Wrapper

## Phase Overview

| Phase | Name | Goal | Status | Biggest checklist items |
| --- | --- | --- | --- | --- |
| 0 | Research, Credentials, And Environment | Prove OpenRouter, local folders, and product-platform startup are available. | Done | Env files/folders created; product-platform API health verified; real OpenRouter and Tool Gateway token checks are externally blocked until credentials are provided. |
| 1 | Runtime Skeleton And DB Persistence | Create a CLI that can load config, migrate DB, and persist a run. | Done | Package skeleton, config, migrations, repository, DB/runs CLI, SQLite unit tests. |
| 2 | Real OpenRouter Agent Call | Run a real Pydantic AI agent call through OpenRouter and persist the result. | Done | Model factory, `llm smoke`, retry/backoff, persisted messages/errors, real-provider test. |
| 3 | Real MCP Server Integration | Spawn real MCP servers and expose their tools to the agent. | Done | MCP config parser, stdio startup, config-check, list-tools, filesystem/git E2E. |
| 4 | Tool Gateway MCP Wrapper | Let the agent call governed Ophanix tools through MCP and Tool Gateway. | Done | MCP server, governed list/call/action tools, smoke command, allowed/denied calls. |
| 5 | Full Agent Run Loop | Run a multi-step task using LLM, MCP, Tool Gateway, DB persistence, and artifacts. | Not Started | `run`, toolsets, instructions, step limits, persisted evidence, claim lookup E2E. |
| 6 | Persistent Memory | Add durable memory that survives process restarts. | Not Started | Memory repository, memory CLI, memory tools, task summary extraction, two-task E2E. |
| 7 | Observability | Make every run debuggable from logs, DB rows, traces, and Tool Gateway UI. | Not Started | JSON logs, IDs everywhere, optional Logfire/Langfuse, observability smoke. |
| 8 | Cloud Persistence | Run the same E2E with a real cloud Postgres database. | Not Started | Postgres URL support, migrations, claim lookup against Neon, inspect rows. |
| 9 | Production Hardening | Prepare for safe long-running experimentation. | Not Started | Pins, allowlists, approval policies, cost guards, retries, redaction/prompt-injection tests. |

## Detailed Checklist

- [x] Re-read earlier logs and implementation plan before starting.
- [x] Implement `mcp_tool_gateway_server.py`.
- [x] Implement `list_governed_tools`.
- [x] Implement `call_governed_tool`.
- [x] Implement `get_tool_gateway_action`.
- [x] Generate request IDs and correlation IDs.
- [x] Redact gateway token and sensitive errors.
- [x] Persist Tool Gateway MCP call evidence in agent DB where possible.
- [x] Add `tool-gateway smoke` command.
- [x] Add direct MCP `call-tool --server tool_gateway` verification.
- [x] Add unit tests for Tool Gateway argument mapping and redaction.
- [x] Run allowed call against real product-platform API when service/token are available.
- [x] Run denied call against real product-platform API when service/token are available.

## Step Notes

- 2026-05-07: Re-read Phase 3 log and Tool Gateway MCP wrapper requirements before making Phase 4 edits.
- 2026-05-07: Inspected existing `product_platform.tool_gateway.sdk` and direct HTTP fixture tokens. Deterministic local demo tokens are `ophanix-local-only-tool-gateway-allowed-token` and `ophanix-local-only-tool-gateway-denied-token`.
- 2026-05-07: Inspected product-platform runtime action API. `/api/v1/tool-runtime/actions?correlation_id=...` exists, but it uses UI/user auth (`require_permission(Permission.AGENT_READ)`), not the gateway bearer token. Wrapper will call it honestly and return structured HTTP/auth status.
- 2026-05-07: Retried runtime-action verification with `agent-demo/.venv-agent/bin/python` against the seeded local product-platform helper on `127.0.0.1:8095`. Calls using the operator bearer token but no environment header returned HTTP 400 for both allowed and denied correlations.
- 2026-05-07: Probed the runtime-action endpoint directly. Response body confirmed `X-Environment-ID is required.` Adding `X-Environment-ID: env_default` returned HTTP 200 and the allowed action row with `action_status=completed`.
- 2026-05-07: Added `OPHANIX_PRODUCT_PLATFORM_ENVIRONMENT_ID` to runtime config and env files, defaulting to `env_default`. Patched `get_tool_gateway_action` to send `X-Environment-ID` with the operator bearer token.
- 2026-05-07: Ran `.venv-agent/bin/python -m pytest tests/real_agent_runtime/test_config.py`; result `4 passed`. Ran `config print`; output includes `OPHANIX_PRODUCT_PLATFORM_ENVIRONMENT_ID: env_default`.
- 2026-05-07: Re-ran real runtime action verification through the patched wrapper. Allowed correlation `corr-agent-demo-allowed-phase4-port8095` returned HTTP 200 with `action_status=completed`, `reason_code=allowed`. Denied correlation `corr-agent-demo-denied-phase4-port8095` returned HTTP 200 with `action_status=denied`, `reason_code=permission_missing`.
- 2026-05-07: Added `tests/real_agent_runtime/test_tool_gateway_runtime.py` covering governed tool list mapping, call argument mapping, denied-call redaction, action lookup headers, missing operator token handling, and audit persistence. Ran `.venv-agent/bin/python -m pytest tests/real_agent_runtime/test_tool_gateway_runtime.py -vv`; result `6 passed in 0.29s`.
- 2026-05-07: Verified direct MCP allowed path with `mcp call-tool --server tool_gateway --tool call_governed_tool` against `127.0.0.1:8095`; structured content returned `status=ok`, HTTP 200, `reason_code=allowed`, and upstream `claim_status=open` for correlation `corr-agent-demo-mcp-allowed-phase4-port8095`.
- 2026-05-07: Verified direct MCP audit lookup for the allowed correlation through `get_tool_gateway_action`; result `ok 200 ['completed'] ['allowed']`.
- 2026-05-07: Verified direct MCP denied path with the denied local token; structured content returned `status=error`, HTTP 403, `reason_code=permission_missing` for correlation `corr-agent-demo-mcp-denied-phase4-port8095`.
- 2026-05-07: Verified direct MCP audit lookup for the denied correlation through `get_tool_gateway_action`; result `ok 200 ['denied'] ['permission_missing']`.
- 2026-05-07: Added `tests/real_agent_runtime/test_real_tool_gateway_flow.py`, an opt-in E2E test for allowed MCP call, denied MCP call, and audit lookup for both correlations. Default run produced `1 skipped`; opt-in run with `OPHANIX_RUN_REAL_TOOL_GATEWAY=1` against the seeded local helper produced `1 passed in 3.10s`.
- 2026-05-07: Ran the full `agent-demo` test suite with `.venv-agent/bin/python -m pytest`; result `23 passed, 3 skipped in 2.41s`. Expected skips: real filesystem MCP opt-in, real OpenRouter credential missing, and real Tool Gateway opt-in for normal runs.

## Phase Completion Summary

- Implemented: `tool_gateway_runtime.py`, `mcp_tool_gateway_server.py`, Tool Gateway CLI smoke, config/env support for product-platform base URL/environment/operator token, error redaction, and persisted audit evidence in `agent_runs`/`agent_tool_calls`.
- Verified: missing-token path, allowed path, denied path, runtime action lookup, direct MCP allowed/denied calls, opt-in real Tool Gateway E2E pytest, and full default suite.
- Deviation: `list_governed_tools` uses the existing SDK endpoint honestly, but product-platform protects `/api/v1/tools` with UI auth rather than gateway bearer auth. The wrapper returns a structured 401 for that path while governed invoke and audit lookup are fully working.
- Next phase starts with a full run loop that combines LLM, MCP tools, Tool Gateway, persistence, and output artifacts.
