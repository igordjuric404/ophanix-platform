# Phase 3 Execution Log - Real MCP Server Integration

## Phase Overview

| Phase | Name | Goal | Status | Biggest checklist items |
| --- | --- | --- | --- | --- |
| 0 | Research, Credentials, And Environment | Prove OpenRouter, local folders, and product-platform startup are available. | Done | Env files/folders created; product-platform API health verified; real OpenRouter and Tool Gateway token checks are externally blocked until credentials are provided. |
| 1 | Runtime Skeleton And DB Persistence | Create a CLI that can load config, migrate DB, and persist a run. | Done | Package skeleton, config, migrations, repository, DB/runs CLI, SQLite unit tests. |
| 2 | Real OpenRouter Agent Call | Run a real Pydantic AI agent call through OpenRouter and persist the result. | Done | Model factory, `llm smoke`, retry/backoff, persisted messages/errors, real-provider test. |
| 3 | Real MCP Server Integration | Spawn real MCP servers and expose their tools to the agent. | Done | MCP config parser, stdio startup, config-check, list-tools, filesystem/git E2E. |
| 4 | Tool Gateway MCP Wrapper | Let the agent call governed Ophanix tools through MCP and Tool Gateway. | Not Started | MCP server, governed list/call/action tools, smoke command, allowed/denied calls. |
| 5 | Full Agent Run Loop | Run a multi-step task using LLM, MCP, Tool Gateway, DB persistence, and artifacts. | Not Started | `run`, toolsets, instructions, step limits, persisted evidence, claim lookup E2E. |
| 6 | Persistent Memory | Add durable memory that survives process restarts. | Not Started | Memory repository, memory CLI, memory tools, task summary extraction, two-task E2E. |
| 7 | Observability | Make every run debuggable from logs, DB rows, traces, and Tool Gateway UI. | Not Started | JSON logs, IDs everywhere, optional Logfire/Langfuse, observability smoke. |
| 8 | Cloud Persistence | Run the same E2E with a real cloud Postgres database. | Not Started | Postgres URL support, migrations, claim lookup against Neon, inspect rows. |
| 9 | Production Hardening | Prepare for safe long-running experimentation. | Not Started | Pins, allowlists, approval policies, cost guards, retries, redaction/prompt-injection tests. |

## Detailed Checklist

- [x] Re-read earlier logs and implementation plan before starting.
- [x] Create `examples/real-agent-runtime/mcp.local.json` under `agent-demo`.
- [x] Implement MCP config parser.
- [x] Reject unknown transports and disabled servers.
- [x] Resolve local filesystem/git paths safely.
- [x] Reject shell control characters and avoid shell execution.
- [x] Implement conversion to Pydantic AI `MCPServerStdio`.
- [x] Add server startup/list-tools logic with timeout.
- [x] Add `mcp config-check` command.
- [x] Add `mcp list-tools` command.
- [x] Add `mcp call-tool` command for direct CLI verification.
- [x] Add tests for MCP config validation.
- [x] Run real filesystem MCP write/read if `npx` and package download are available.
- [x] Run real git MCP read if a git MCP server launcher is available.

## Step Notes

- 2026-05-07: Re-read Phase 2 log and MCP integration requirements before making Phase 3 edits.
- 2026-05-07: Web lookup confirmed the current filesystem MCP server is available through `npx @modelcontextprotocol/server-filesystem`.
- 2026-05-07: Local introspection confirmed `pydantic_ai.mcp.MCPServerStdio`, official MCP `stdio_client`, `ClientSession.list_tools`, `ClientSession.call_tool`, and FastMCP stdio server support.
- 2026-05-07: `uvx` is absent in this environment, so the plan's `uvx mcp-server-git` command is not directly runnable. Conservative deviation: implement a tiny local Git MCP stdio server using FastMCP and real `/usr/bin/git`, scoped to `../ophanix-platform`.
- 2026-05-07: Added `agent-demo/examples/real-agent-runtime/mcp.local.json` with filesystem MCP via `npx` and local git MCP via current venv Python.
- 2026-05-07: Added `mcp_config.py` with JSON parsing, `stdio`-only enforcement, disabled-server rejection, command allowlist, shell control character rejection, sandbox path enforcement, repository path resolution, and secret-redacted config summaries.
- 2026-05-07: Added `mcp_client.py` with conversion to Pydantic AI `MCPServerStdio`, official MCP stdio client list/call helpers, subprocess timeout handling, and stderr capture.
- 2026-05-07: Added `mcp_git_server.py`, a real FastMCP stdio server that exposes read-only `git_status`, `git_log`, and `git_rev_parse` against `/Users/igodju/Projects/Personal/ophanix/ophanix-platform`.
- 2026-05-07: Added CLI commands `mcp config-check`, `mcp list-tools`, and `mcp call-tool`.
- 2026-05-07: `mcp config-check` passed and showed filesystem sandbox resolved to `agent-demo/.local/real-agent/sandbox` and git repo resolved to `ophanix-platform`.
- 2026-05-07: First git MCP `list-tools`/`call-tool` failed with `fileno`; root cause was passing `io.StringIO` to `stdio_client` as subprocess stderr. Fixed by using `tempfile.TemporaryFile` and reading it after subprocess exit.
- 2026-05-07: Real git MCP retest passed. `mcp list-tools --server git` listed `git_status`, `git_log`, `git_rev_parse`; `mcp call-tool --server git --tool git_status` returned real git status with return code 0.
- 2026-05-07: Sandboxed filesystem MCP `list-tools` failed with subprocess termination warning `Operation not permitted`, so reran with approved escalation because it starts `npx` and a real server.
- 2026-05-07: Escalated filesystem MCP `list-tools` passed and listed tools including `read_text_file`, `write_file`, `list_directory`, and `list_allowed_directories`. Stderr confirmed allowed directory is only `agent-demo/.local/real-agent/sandbox`.
- 2026-05-07: Real filesystem MCP write/read passed. `write_file` wrote `.local/real-agent/sandbox/output/mcp-filesystem-smoke.md`; `read_text_file` returned `filesystem mcp smoke ok`; `test -s` passed.
- 2026-05-07: Combined escalated `mcp list-tools` passed for both filesystem and git.
- 2026-05-07: Added MCP config tests for path resolution, Python command resolution, unknown transport rejection, disabled server rejection, shell metacharacter rejection, and filesystem path escape rejection.
- 2026-05-07: Added real MCP flow tests for git status and opt-in filesystem write/read.
- 2026-05-07: Phase 3 config + real git pytest passed: `6 passed in 1.53s`.
- 2026-05-07: Opt-in real filesystem MCP pytest passed with `OPHANIX_RUN_REAL_FILESYSTEM_MCP=1` and escalation: `1 passed in 2.45s`.
- 2026-05-07: Full current pytest passed with expected skips: `17 passed, 2 skipped in 2.19s`.
- 2026-05-07: Phase 3 complete. Deviation from original plan: custom local git MCP server replaces `uvx mcp-server-git` because `uvx` is unavailable; it still uses a real MCP stdio subprocess and real git command.
