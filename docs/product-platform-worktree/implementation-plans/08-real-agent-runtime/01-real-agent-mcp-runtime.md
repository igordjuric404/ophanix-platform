# Real Agent Runtime With MCP And Tool Gateway

Last researched: 2026-05-07

This plan describes how to build and test a real autonomous agent runtime for the
Ophanix product platform using real model inference, real MCP servers, real
database persistence, and real Tool Gateway calls. It is written so an AI
software engineer agent can execute it from the CLI step by step.

The plan intentionally avoids mocks for the main validation path. Deterministic
test data is allowed, but the system must still make real network calls to the
LLM provider, spawn real MCP servers, write to a real database, and call the
local Tool Gateway API.

## Recommendation

Build the first real environment locally using:

- Pydantic AI as the Python agent runtime.
- OpenRouter as the hosted LLM provider.
- MCP stdio servers for local filesystem, git, memory, and the Tool Gateway MCP
  wrapper.
- SQLite for MVP persistence, with Neon Postgres as the first cloud database.
- The existing product-platform Tool Gateway for governed business tool
  invocation.
- JSON logs plus optional Pydantic Logfire or Langfuse via OpenTelemetry.

This is the best tradeoff because it uses the existing Python codebase, avoids
GPU setup, works with the user's existing OpenRouter account, gives real MCP
tools without deploying infrastructure, keeps data persistent, and allows the
whole loop to run cheaply on a laptop. OpenRouter free models can be used for
smoke tests, and paid test runs can be capped to pennies by limiting tokens and
steps.

Use LangGraph later if the runtime needs explicit graph checkpoints,
human-in-the-loop state editing, or long-running resumable workflows. Do not
start with LangGraph unless those production needs are immediate.

## Research Summary

### Option 1 - Local Runtime With OpenRouter

What it gives:

- Real hosted model inference through an OpenAI-compatible HTTP API.
- Access to many models through one account and one API key.
- No local GPU or model downloads.
- Works directly with Pydantic AI's OpenRouter provider.
- Good fit for repeatable CLI testing because the agent runtime, MCP servers,
  Tool Gateway, and SQLite database all run locally.

Pros:

- Fastest path to a real system.
- Lowest setup complexity.
- Cheap because free models exist and paid models are pay-as-you-go.
- Easy to cap spend with model choice, max tokens, max steps, and OpenRouter
  dashboard budgets.
- Better tool-calling reliability than many small local models.

Cons:

- Requires network access.
- Free models have rate limits and availability variability.
- Provider routing can change latency unless a specific model/provider is pinned.
- Secrets and prompts leave the machine, subject to OpenRouter/provider policy.

Cost profile:

- Free plan: OpenRouter lists free models and a free request limit.
- Paid: no minimum spend on pay-as-you-go; cost depends on the selected model and
  tokens.
- Recommended test budget: start with a model cap of 10 to 30 agent steps/day
  and a per-run max cost guard such as USD 0.05.

Verdict:

- Best MVP choice.

### Option 2 - Local Runtime With Ollama

What it gives:

- Real local model inference.
- No per-token API cost.
- OpenAI-compatible local API at `http://localhost:11434/v1/`.
- Good privacy story for local-only experiments.

Pros:

- No model API bill.
- Works offline after model download.
- Useful fallback when OpenRouter is unavailable.
- Useful for low-risk non-tool reasoning and summarization.

Cons:

- Requires disk, RAM, and CPU/GPU capacity.
- Tool calling quality depends heavily on the model.
- Slow on CPU for larger models.
- Reproducibility varies across machine hardware and model tags.
- Setup can take longer than OpenRouter if model downloads are large.

Cost profile:

- No API cost.
- Hardware and electricity are the real costs.

Verdict:

- Good fallback and privacy mode, but not the fastest route to a reliable real
  tool-using agent.

### Option 3 - Free-Tier Cloud Setup

Practical choices:

- Neon Postgres for a managed cloud database with a strong free tier.
- Render free web services for a preview deployment, but Render free Postgres
  expires after 30 days.
- Railway for simple app deployment with a trial credit and small recurring free
  credit, but free/trial network constraints can affect agent experiments.
- Fly.io for production-like containers and volumes, but it is usage-based and
  should be treated as low-cost rather than truly free.

Pros:

- Useful when the agent needs a long-running API endpoint.
- Cloud database makes results available across machines.
- Easier to share demos.

Cons:

- More moving parts than local.
- Free web instances can sleep, reset, expire, or restrict networking.
- Local filesystem MCP tools do not make sense in cloud unless they operate on a
  mounted cloud volume or a remote file service.
- Remote MCP servers must be authenticated and hardened.

Cost profile:

- Local app plus Neon free DB can stay at USD 0 for experiments.
- Render free is usable for previews, but not durable production.
- Railway/Fly can become low-cost paid quickly if left running.

Verdict:

- Use cloud only after local E2E works. First cloud target should be local agent
  runtime plus Neon Postgres. Deploy compute later.

### Option 4 - Existing Agent Framework With Native MCP

Candidate frameworks:

- Pydantic AI:
  - Native OpenRouter provider.
  - Native MCP client support for stdio, SSE, and Streamable HTTP.
  - Python-first and fits this repo.
  - Good for typed tool definitions and testable business logic.
- LangChain plus LangGraph:
  - Mature MCP adapters.
  - LangGraph persistence and memory are strong for durable agent workflows.
  - More framework surface area and more decisions up front.
- OpenAI Agents SDK:
  - Strong MCP support, tracing, sessions, and approvals.
  - Best when using OpenAI Responses models and hosted MCP tools.
  - OpenRouter support likely requires a model-provider adapter such as LiteLLM,
    which adds complexity for this use case.
- OpenRouter Agent SDK:
  - Good TypeScript agent loop for OpenRouter with tool execution and stop
    conditions.
  - Less natural for this Python backend and existing Tool Gateway code.
  - Native MCP is not the main reason to choose it today.

Verdict:

- Use Pydantic AI for the MVP.
- Keep the runtime boundaries framework-neutral enough that LangGraph can be
  introduced later for durable workflows.

## Architecture Overview

MVP runtime:

```text
CLI task request
  |
  v
Real Agent Runner (Python, Pydantic AI)
  |
  |-- OpenRouter model call
  |
  |-- MCP stdio client sessions
  |     |-- filesystem MCP server, scoped to .local/agent-sandbox
  |     |-- git MCP server, scoped to this repo
  |     |-- memory MCP server or product-platform memory DB tools
  |     `-- Ophanix Tool Gateway MCP wrapper
  |
  |-- Persistence repository
  |     `-- SQLite locally, Postgres later
  |
  `-- Observability
        |-- JSON logs
        |-- DB audit tables
        |-- Tool Gateway runtime actions
        `-- optional OpenTelemetry export
```

Governed business tool path:

```text
Agent decides it needs a business action
  |
  v
MCP tool: call_governed_tool
  |
  v
Local Tool Gateway MCP wrapper
  |
  v
product_platform.tool_gateway.sdk client
  |
  v
Product Platform Tool Gateway API
  |
  |-- Auth and policy decision
  |-- Runtime action audit store
  |-- Response redaction
  |
  v
Real upstream HTTP service or real integration
```

The agent must not call business APIs directly when a Tool Gateway contract
exists. It should call them through the Tool Gateway so policy, audit, and
redaction are visible in the UI.

## Tech Stack Choices

Use these libraries for the MVP:

- `pydantic-ai-slim[openrouter,mcp,logfire]`
  - OpenRouter provider, MCP client integration, optional Logfire tracing.
- `mcp`
  - Official Python MCP SDK for custom MCP servers and direct protocol tests.
- `sqlalchemy`
  - Database abstraction for SQLite and Postgres.
- `aiosqlite`
  - Async SQLite driver for local persistence.
- `psycopg[binary]`
  - Postgres driver for Neon or Supabase later.
- `structlog`
  - Structured JSON logs for CLI, agent runs, model calls, and tools.
- `python-dotenv`
  - Local `.env.real-agent` loading.
- `typer` and `rich`
  - CLI commands and readable terminal output.
- `pytest`, `pytest-asyncio`
  - Real integration tests.
- `httpx`
  - Existing dependency and HTTP client for Tool Gateway and OpenRouter smoke
    checks.

Optional later:

- `langgraph` and `langgraph-checkpoint-sqlite`
  - Durable graph execution and state replay.
- `langchain-mcp-adapters`
  - If LangGraph becomes the runtime engine.
- `langfuse`
  - Hosted or self-hosted LLM observability through OpenTelemetry.
- `sqlite-vec` or Postgres `pgvector`
  - Semantic memory search.

## Repository Locations To Add

Create these files during implementation:

```text
packages/product-platform/src/product_platform/real_agent_runtime/
  __init__.py
  cli.py
  config.py
  db.py
  models.py
  repository.py
  logging.py
  openrouter.py
  mcp_config.py
  mcp_client.py
  mcp_tool_gateway_server.py
  runner.py
  memory.py
  tools.py

packages/product-platform/tests/real_agent_runtime/
  test_config.py
  test_memory_repository.py
  test_mcp_tool_gateway_server.py
  test_real_openrouter_smoke.py
  test_real_mcp_filesystem_flow.py
  test_real_agent_tool_gateway_e2e.py

packages/product-platform/examples/real-agent-runtime/
  .env.real-agent.example
  mcp.local.json
  README.md
  tasks/
    customer_claim_lookup.md
    repo_summary.md
  scripts/
    select_openrouter_model.py
    prepare_sandbox.sh
```

Add migrations when the database tables are implemented:

```text
packages/product-platform/src/product_platform/db/migrations/
  0056_real_agent_runtime.up.sql
  0056_real_agent_runtime.down.sql
```

## Local Environment Setup

All commands assume:

```bash
cd /Users/igodju/Projects/Personal/ophanix/ophanix-platform/packages/product-platform
```

### Step 1 - Create An Isolated Agent Environment

```bash
python3 -m venv .venv-agent
source .venv-agent/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Acceptance check:

```bash
python -c "import product_platform; print(product_platform.__name__)"
```

Expected output includes:

```text
product_platform
```

### Step 2 - Install Real Agent Dependencies

For the first implementation, install directly:

```bash
python -m pip install \
  "pydantic-ai-slim[openrouter,mcp,logfire]" \
  mcp \
  sqlalchemy \
  aiosqlite \
  "psycopg[binary]" \
  structlog \
  python-dotenv \
  typer \
  rich \
  pytest \
  pytest-asyncio
```

After the first successful run, move these dependencies into
`packages/product-platform/pyproject.toml` under an optional dependency group:

```toml
[project.optional-dependencies]
real-agent = [
    "pydantic-ai-slim[openrouter,mcp,logfire]>=1.0",
    "mcp>=1.0",
    "sqlalchemy>=2.0",
    "aiosqlite>=0.19",
    "psycopg[binary]>=3.2",
    "structlog>=24.0",
    "python-dotenv>=1.0",
    "typer>=0.12",
    "rich>=13.0",
]
```

Then verify:

```bash
python -m pip install -e ".[real-agent]"
python -c "from pydantic_ai import Agent; print(Agent)"
python -c "from pydantic_ai.mcp import MCPServerStdio; print(MCPServerStdio)"
```

### Step 3 - Create Local Runtime Folders

```bash
mkdir -p .local/real-agent
mkdir -p .local/real-agent/sandbox/input
mkdir -p .local/real-agent/sandbox/output
mkdir -p .local/real-agent/logs
```

Acceptance check:

```bash
test -d .local/real-agent/sandbox/input
test -d .local/real-agent/sandbox/output
```

### Step 4 - Create Local Environment File

Create `examples/real-agent-runtime/.env.real-agent.example`:

```bash
OPHANIX_AGENT_DATABASE_URL=sqlite:///.local/real-agent/agent.sqlite3
OPHANIX_AGENT_MCP_CONFIG=examples/real-agent-runtime/mcp.local.json
OPHANIX_AGENT_SANDBOX_DIR=.local/real-agent/sandbox
OPHANIX_AGENT_MODEL=openrouter/free
OPHANIX_AGENT_TOOL_MODEL=
OPHANIX_AGENT_MAX_STEPS=12
OPHANIX_AGENT_MAX_OUTPUT_TOKENS=900
OPHANIX_AGENT_TEMPERATURE=0
OPHANIX_AGENT_LOG_LEVEL=INFO
OPHANIX_AGENT_OTEL_ENABLED=false
OPHANIX_PRODUCT_PLATFORM_API_BASE_URL=http://127.0.0.1:8088
OPHANIX_TOOL_GATEWAY_TOKEN=
OPENROUTER_API_KEY=
LOGFIRE_TOKEN=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
```

Then copy it:

```bash
cp examples/real-agent-runtime/.env.real-agent.example .env.real-agent
```

Edit `.env.real-agent` manually or with a secrets manager. At minimum set:

```bash
OPENROUTER_API_KEY=sk-or-...
OPHANIX_TOOL_GATEWAY_TOKEN=<local gateway token or demo token>
```

Do not commit `.env.real-agent`.

### Step 5 - Verify OpenRouter Access

Run a direct API smoke test before adding agent complexity:

```bash
set -a
source .env.real-agent
set +a

python - <<'PY'
import os
import httpx

api_key = os.environ["OPENROUTER_API_KEY"]
model = os.environ.get("OPHANIX_AGENT_MODEL", "openrouter/free")

response = httpx.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: ophanix-ok"}],
        "temperature": 0,
        "max_tokens": 20,
    },
    timeout=60,
)
print(response.status_code)
print(response.text[:1000])
response.raise_for_status()
PY
```

Acceptance check:

- Exit code is `0`.
- Status is `200`.
- Response contains model output.

If this fails:

- `401`: verify `OPENROUTER_API_KEY`.
- `404`: choose a model currently available in the OpenRouter model catalog.
- `429`: free-tier limit or provider limit; wait or switch to a low-cost paid
  model.
- Timeout: retry once, then pin a different model/provider.

### Step 6 - Select A Tool-Capable Model

The agent E2E requires tool calling. Do not assume every free model supports
tools.

Create `examples/real-agent-runtime/scripts/select_openrouter_model.py` that:

1. Calls `GET https://openrouter.ai/api/v1/models`.
2. Filters models where supported parameters include tool/function calling when
   that metadata is available.
3. Prints a ranked list:
   - free models first,
   - then lowest output token price,
   - then largest context window.
4. Exits non-zero if no candidate is found.

Run:

```bash
python examples/real-agent-runtime/scripts/select_openrouter_model.py
```

Set the result in `.env.real-agent`:

```bash
OPHANIX_AGENT_TOOL_MODEL=<selected-model-id>
```

For smoke tests, `OPHANIX_AGENT_MODEL=openrouter/free` is acceptable. For
reproducible E2E tests, use an explicit tool-capable model ID.

## Agent Runtime Setup

### Step 1 - Implement Configuration Loading

Create `product_platform/real_agent_runtime/config.py`.

Required behavior:

- Load `.env.real-agent` if present.
- Parse required settings into a Pydantic model.
- Validate that `OPENROUTER_API_KEY` exists for real LLM runs.
- Validate that `OPHANIX_AGENT_DATABASE_URL` exists.
- Resolve relative paths against `packages/product-platform`.
- Refuse to use a sandbox directory outside the repo unless explicitly allowed
  by `OPHANIX_AGENT_ALLOW_EXTERNAL_SANDBOX=true`.

CLI verification:

```bash
python -m product_platform.real_agent_runtime.cli config print
```

Expected:

- Prints redacted API keys.
- Prints database URL.
- Prints sandbox directory.
- Prints selected model.

### Step 2 - Implement The Runtime CLI

Create `product_platform/real_agent_runtime/cli.py` using Typer.

Required commands:

```bash
python -m product_platform.real_agent_runtime.cli config print
python -m product_platform.real_agent_runtime.cli db migrate
python -m product_platform.real_agent_runtime.cli db inspect
python -m product_platform.real_agent_runtime.cli llm smoke
python -m product_platform.real_agent_runtime.cli mcp list-tools
python -m product_platform.real_agent_runtime.cli tool-gateway smoke
python -m product_platform.real_agent_runtime.cli run --task-file examples/real-agent-runtime/tasks/customer_claim_lookup.md
python -m product_platform.real_agent_runtime.cli runs list
python -m product_platform.real_agent_runtime.cli runs show <run-id>
```

Every command must:

- Emit structured JSON logs to `.local/real-agent/logs/agent.log`.
- Print a human-readable summary to stdout.
- Return non-zero on failure.
- Include `run_id` and `correlation_id` where applicable.

### Step 3 - Implement The Pydantic AI Agent

Create `product_platform/real_agent_runtime/runner.py`.

Required behavior:

- Create an `Agent` using `openrouter:<model-id>` or `OpenRouterModel`.
- Attach MCP toolsets from the configured MCP servers.
- Add a system instruction that requires:
  - use tools when needed,
  - keep tool arguments minimal,
  - never bypass the Tool Gateway for governed actions,
  - write final artifacts to the sandbox output directory,
  - stop when the task is complete.
- Limit steps with the configured `OPHANIX_AGENT_MAX_STEPS`.
- Limit tokens with `OPHANIX_AGENT_MAX_OUTPUT_TOKENS`.
- Persist every run, message, tool call, and final output.

First CLI verification:

```bash
python -m product_platform.real_agent_runtime.cli llm smoke
```

Acceptance:

- Makes a real OpenRouter call.
- Writes one `agent_runs` row.
- Writes at least one `agent_messages` row.
- Prints the provider/model used.

## MCP Server Integration

### Step 1 - Create MCP Config File

Create `examples/real-agent-runtime/mcp.local.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "transport": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        ".local/real-agent/sandbox"
      ],
      "enabled": true
    },
    "git": {
      "transport": "stdio",
      "command": "uvx",
      "args": [
        "mcp-server-git",
        "--repository",
        "../.."
      ],
      "enabled": true
    },
    "memory": {
      "transport": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-memory"
      ],
      "enabled": true
    },
    "tool_gateway": {
      "transport": "stdio",
      "command": "python",
      "args": [
        "-m",
        "product_platform.real_agent_runtime.mcp_tool_gateway_server"
      ],
      "enabled": true
    }
  }
}
```

Notes:

- `filesystem` must be scoped to `.local/real-agent/sandbox`.
- `git` must be scoped to the repository, not the whole home directory.
- Pin server versions later once the first run works.
- If `npx` or `uvx` are missing, install Node.js and uv using the project's
  standard developer setup.

### Step 2 - Implement MCP Config Parsing

Create `product_platform/real_agent_runtime/mcp_config.py`.

Required behavior:

- Read JSON config.
- Reject unknown transports.
- Reject disabled servers.
- Resolve relative filesystem args against `packages/product-platform`.
- Reject commands containing shell control characters.
- Do not execute via shell.
- Redact env values in logs.

Verification:

```bash
python -m product_platform.real_agent_runtime.cli mcp config-check
```

Acceptance:

- Shows each enabled server.
- Shows command and args.
- Shows resolved allowed paths.
- Does not start any server yet.

### Step 3 - Implement MCP Client Tool Listing

Create `product_platform/real_agent_runtime/mcp_client.py`.

Required behavior:

- Convert each config entry to Pydantic AI `MCPServerStdio`.
- Enter server contexts safely.
- List tools and resources.
- Capture stderr logs from MCP servers when available.
- Time out server startup after 30 seconds.

Verification:

```bash
python -m product_platform.real_agent_runtime.cli mcp list-tools
```

Acceptance:

- Starts real MCP server subprocesses.
- Lists real tools from filesystem, git, memory, and Tool Gateway server.
- Exits cleanly and closes subprocesses.

### Step 4 - Implement Tool Gateway MCP Wrapper

Create `product_platform/real_agent_runtime/mcp_tool_gateway_server.py`.

MVP tools:

```text
list_governed_tools()
call_governed_tool(tool_name: str, payload: dict, reason: str)
get_tool_gateway_action(correlation_id: str)
```

Required behavior:

- Use the existing `product_platform.tool_gateway.sdk` client.
- Read `OPHANIX_PRODUCT_PLATFORM_API_BASE_URL`.
- Read `OPHANIX_TOOL_GATEWAY_TOKEN`.
- Generate a request ID and correlation ID for every call.
- Return structured JSON with:
  - status,
  - HTTP status,
  - tool name,
  - correlation ID,
  - response body or redacted error.
- Never expose the gateway token to the model.
- Log every call to the agent DB and rely on Tool Gateway runtime actions for
  the authoritative audit trail.

Verification:

```bash
python -m product_platform.real_agent_runtime.cli mcp call-tool \
  --server tool_gateway \
  --tool list_governed_tools
```

Acceptance:

- Starts the local MCP wrapper.
- Calls the real product-platform API.
- Returns registered Tool Gateway contracts.

Production upgrade:

- Dynamically expose typed MCP tools from Tool Gateway contracts.
- Validate arguments against the Tool Gateway JSON schemas before invocation.
- Add per-tool approval policies for mutating tools.

## Database Setup

### Step 1 - Add Runtime Tables

Create migration `0056_real_agent_runtime.up.sql`:

```sql
CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    objective TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    estimated_cost_usd REAL DEFAULT 0,
    error TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS agent_messages (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES agent_runs(id),
    sequence INTEGER NOT NULL,
    role TEXT NOT NULL,
    content_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_tool_calls (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES agent_runs(id),
    sequence INTEGER NOT NULL,
    server_name TEXT,
    tool_name TEXT NOT NULL,
    request_json TEXT NOT NULL,
    response_json TEXT,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_ms INTEGER,
    correlation_id TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS agent_memory (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    key TEXT NOT NULL,
    content TEXT NOT NULL,
    content_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (tenant_id, user_id, scope, key)
);

CREATE TABLE IF NOT EXISTS agent_checkpoints (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES agent_runs(id),
    sequence INTEGER NOT NULL,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_messages_run_id
    ON agent_messages(run_id);

CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_run_id
    ON agent_tool_calls(run_id);

CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_correlation_id
    ON agent_tool_calls(correlation_id);

CREATE INDEX IF NOT EXISTS idx_agent_memory_lookup
    ON agent_memory(tenant_id, user_id, scope);
```

Create matching down migration.

### Step 2 - Implement Repository

Create `repository.py`.

Required methods:

```python
create_run(...)
finish_run(...)
fail_run(...)
append_message(...)
append_tool_call(...)
finish_tool_call(...)
upsert_memory(...)
search_memory(...)
write_checkpoint(...)
list_runs(...)
get_run_detail(...)
```

Verification:

```bash
python -m product_platform.real_agent_runtime.cli db migrate
python -m product_platform.real_agent_runtime.cli db inspect
sqlite3 .local/real-agent/agent.sqlite3 ".tables"
```

Acceptance:

- Tables exist in SQLite.
- CLI prints migration status.
- Repository unit tests insert and read real rows.

### Step 3 - Postgres Compatibility Check

After SQLite works, create a Neon free database and set:

```bash
OPHANIX_AGENT_DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>/<db>?sslmode=require
```

Run:

```bash
python -m product_platform.real_agent_runtime.cli db migrate
python -m product_platform.real_agent_runtime.cli db inspect
python -m product_platform.real_agent_runtime.cli llm smoke
```

Acceptance:

- Same CLI commands pass against Postgres.
- No SQLite-specific SQL is required outside migrations.

## Tool Execution Layer

### Rule 1 - Governed Tools Go Through Tool Gateway

If a tool exists in the Tool Gateway registry, the agent must call it through
`call_governed_tool`. It must not call the upstream HTTP service directly.

### Rule 2 - MCP Tools Are Allowed Only From Config

The agent runtime may only start MCP servers declared in
`examples/real-agent-runtime/mcp.local.json` or another explicitly provided
config file.

### Rule 3 - Mutations Need Approval Gates

For MVP, allow read-only filesystem actions and governed Tool Gateway read
actions. Require an approval policy before enabling:

- file deletion,
- shell execution,
- external network fetches,
- writes to production databases,
- mutating business tools.

### Rule 4 - Capture Full Tool Evidence

Every tool call must write:

- run ID,
- tool name,
- MCP server name,
- request JSON,
- response JSON or redacted error,
- start and finish timestamps,
- duration,
- correlation ID if available.

For Tool Gateway calls, cross-check `agent_tool_calls.correlation_id` against
the Tool Gateway runtime action feed.

## Memory System

MVP memory:

- Store conversation messages in `agent_messages`.
- Store extracted durable memories in `agent_memory`.
- Use exact lookup and simple text search first.
- Only save memories when the agent explicitly emits a memory write action or
  the runner extracts a durable fact after task completion.

Memory scopes:

```text
user_preference
project_fact
tool_result
task_summary
```

CLI commands:

```bash
python -m product_platform.real_agent_runtime.cli memory list
python -m product_platform.real_agent_runtime.cli memory get --key <key>
python -m product_platform.real_agent_runtime.cli memory put --scope project_fact --key demo --content "..."
python -m product_platform.real_agent_runtime.cli memory search "tool gateway"
```

Acceptance:

- Memory persists across separate CLI invocations.
- A second agent task can read memory from the first task.
- Memory writes are tenant/user scoped.

Upgrade path:

- Add embeddings after MVP with either `sqlite-vec` locally or `pgvector` in
  Postgres.
- Add decay, provenance, and explicit delete commands before production.

## Logging And Observability

### MVP Logging

Implement `logging.py`.

Required fields on every log event:

```text
timestamp
level
event
run_id
correlation_id
tenant_id
user_id
model
tool_name
duration_ms
status
```

Write JSON logs to:

```text
.local/real-agent/logs/agent.log
```

CLI checks:

```bash
tail -n 20 .local/real-agent/logs/agent.log
```

Validate JSON-lines logs with:

```bash
python - <<'PY'
import json
from pathlib import Path
for line in Path(".local/real-agent/logs/agent.log").read_text().splitlines():
    json.loads(line)
print("logs-ok")
PY
```

### Optional Logfire

When `OPHANIX_AGENT_OTEL_ENABLED=true` and `LOGFIRE_TOKEN` exists:

- Configure Logfire.
- Instrument Pydantic AI.
- Instrument HTTPX.
- Include run ID and correlation ID as trace attributes.

CLI check:

```bash
python -m product_platform.real_agent_runtime.cli observability smoke
```

Acceptance:

- A trace appears in Logfire.
- Model call spans and tool call spans are visible.

### Optional Langfuse

If Langfuse is preferred:

- Configure OpenTelemetry exporter to Langfuse.
- Include `userId`, `sessionId`, run ID, and trace metadata.
- Do not put secrets, raw credentials, or full PII into trace baggage.

## End-To-End Testing Strategy

The E2E suite must run real components. It may use a temporary database and
deterministic fixture data, but no mocked model, no fake MCP client, and no fake
Tool Gateway client.

### Test Tiers

Tier 0 - local deterministic unit tests:

- Config parsing.
- MCP config validation.
- DB repository behavior against SQLite.
- JSON redaction.
- Tool Gateway argument mapping.

Tier 1 - real provider smoke tests:

- Real OpenRouter model call with low token cap.
- Real MCP filesystem server writes and reads a file.
- Real MCP git server reads repository status.
- Real Tool Gateway API call against local product-platform.

Tier 2 - real agent E2E:

- Agent receives a task file.
- Agent reads a real file through filesystem MCP.
- Agent calls Tool Gateway through MCP wrapper.
- Agent writes a real output file through filesystem MCP.
- Agent persists run/message/tool rows.
- Tool Gateway UI shows allowed or denied runtime actions.

Tier 3 - cloud persistence test:

- Same Tier 2 flow, but with Neon Postgres as the runtime DB.

### Required E2E Scenario 1 - Claim Lookup Through Tool Gateway

Prepare task file:

```bash
cat > examples/real-agent-runtime/tasks/customer_claim_lookup.md <<'EOF'
Read .local/real-agent/sandbox/input/customer_claim.md.
Use governed tools only for business data.
Look up the claim referenced in the file.
Write a concise answer to .local/real-agent/sandbox/output/customer_claim_answer.md.
Also include the Tool Gateway correlation ID in the output.
EOF
```

Prepare sandbox input:

```bash
cat > .local/real-agent/sandbox/input/customer_claim.md <<'EOF'
Customer asks for the current status of claim CLM-1001.
Only use governed tool access.
EOF
```

Start product-platform API and Tool Gateway dependencies:

```bash
./start.sh
```

If `./start.sh` is too broad, run the minimal commands documented in
`packages/product-platform/README.md`:

```bash
PYTHONPATH=src OPHANIX_DATABASE_URL=sqlite:///ophanix_product.db \
  python3 -m product_platform.cli db migrate

PYTHONPATH=src OPHANIX_DATABASE_URL=sqlite:///ophanix_product.db \
  python3 -m product_platform.cli db seed

PYTHONPATH=src OPHANIX_DATABASE_URL=sqlite:///ophanix_product.db \
  python3 -m product_platform.cli serve --host 127.0.0.1 --port 8088
```

Run the agent:

```bash
set -a
source .env.real-agent
set +a

python -m product_platform.real_agent_runtime.cli run \
  --task-file examples/real-agent-runtime/tasks/customer_claim_lookup.md \
  --tenant-id demo-tenant \
  --user-id demo-user \
  --max-steps 12
```

Acceptance checks:

```bash
test -s .local/real-agent/sandbox/output/customer_claim_answer.md
grep -i "CLM-1001" .local/real-agent/sandbox/output/customer_claim_answer.md
grep -i "correlation" .local/real-agent/sandbox/output/customer_claim_answer.md

sqlite3 .local/real-agent/agent.sqlite3 \
  "select status, model from agent_runs order by started_at desc limit 1;"

sqlite3 .local/real-agent/agent.sqlite3 \
  "select tool_name, status, correlation_id from agent_tool_calls order by started_at desc limit 5;"
```

Then inspect the Tool Gateway UI:

```bash
cd /Users/igodju/Projects/Personal/ophanix/ophanix-platform/packages/product-platform
./start.sh
```

Open the frontend URL printed by `./start.sh` and navigate to the Tool Gateway
decisions page. Confirm:

- A runtime action exists for the agent call.
- The correlation ID matches the agent output file.
- Decision status is `allowed` for the valid fixture.
- Denied tests show `permission_missing` or the correct policy reason.

### Required E2E Scenario 2 - Denied Tool Call

Create a task that asks for a tool/action the agent is not allowed to use.

Run:

```bash
python -m product_platform.real_agent_runtime.cli run \
  --task "Try to retrieve a restricted claim using governed tools and explain the policy result." \
  --tenant-id demo-tenant \
  --user-id unauthorized-user \
  --max-steps 8
```

Acceptance:

- Agent does not bypass the gateway.
- Tool Gateway returns denied decision.
- Agent final answer explains the denial without fabricating data.
- `agent_runs.status` is `completed_with_denial` or equivalent, not a crash.
- Tool Gateway UI shows the denied runtime action.

### Required E2E Scenario 3 - MCP Filesystem Artifact

Run:

```bash
python -m product_platform.real_agent_runtime.cli run \
  --task "Create .local/real-agent/sandbox/output/hello-agent.md with a one paragraph summary of this repo's product-platform package. Use MCP filesystem and git tools." \
  --tenant-id demo-tenant \
  --user-id demo-user \
  --max-steps 10
```

Acceptance:

- Output file exists.
- At least one filesystem MCP tool call was recorded.
- At least one git MCP tool call was recorded.
- Run is persisted.

### Required E2E Scenario 4 - Persistent Memory

Run first task:

```bash
python -m product_platform.real_agent_runtime.cli run \
  --task "Remember that demo-user prefers concise operational summaries. Save this as durable memory." \
  --tenant-id demo-tenant \
  --user-id demo-user \
  --max-steps 5
```

Run second task:

```bash
python -m product_platform.real_agent_runtime.cli run \
  --task "Summarize the last Tool Gateway call using any durable preference you know for this user." \
  --tenant-id demo-tenant \
  --user-id demo-user \
  --max-steps 8
```

Acceptance:

- `agent_memory` contains the preference.
- Second run reads or includes the preference.
- Memory persists across separate Python processes.

## Example Real Tasks To Validate

Use these as recurring smoke tasks:

1. Read a file in the sandbox, call a governed claim lookup tool, write a
   response file, and include the Tool Gateway correlation ID.
2. Summarize the product-platform package using real git and filesystem MCP
   tools.
3. Create a persistent memory, then use it in a later run.
4. Attempt a denied governed tool call and explain the policy result.
5. Query the runtime DB for the last run and write a Markdown incident summary.
6. Run against Neon Postgres and confirm the same rows appear in the cloud DB.

## Deployment Options

### MVP Deployment - Local Only

Use:

- Local product-platform API.
- Local MCP stdio servers.
- Local SQLite.
- OpenRouter hosted model inference.

This is the recommended starting point.

### Shared Database - Local Agent Plus Neon Postgres

Use:

- Local agent runtime.
- Local MCP stdio servers.
- Neon Postgres for `OPHANIX_AGENT_DATABASE_URL`.
- OpenRouter for model calls.

This is the best next step when results need to persist outside one laptop.

### Preview Web Deployment

Use only after local E2E is reliable:

- Render or Railway for a product-platform preview API.
- Neon Postgres for durable DB.
- Remote MCP servers only if they have authentication and explicit allowlists.

Do not deploy local filesystem MCP access to a public service without sandboxing.

### Production-Like Deployment

Use:

- Containerized agent worker.
- Postgres with backups.
- Remote MCP gateway with authentication.
- Tool Gateway policy enforcement.
- OpenTelemetry collector.
- Secrets manager.
- Queue-based task dispatch.
- Human approval workflow for high-risk tools.

## Cost Estimates

Local MVP:

- Runtime compute: USD 0, using your laptop.
- SQLite: USD 0.
- MCP stdio servers: USD 0.
- OpenRouter free model smoke tests: USD 0 within free limits.
- OpenRouter paid tool-capable tests: typically cents per test run if max steps
  and max tokens are capped.
- Logs: USD 0 with local JSON logs.

Local plus Neon:

- Neon free tier should cover small experiments.
- OpenRouter remains the main variable cost.

Cloud preview:

- Render free web service can work for preview, but free Postgres expires after
  30 days.
- Railway starts with trial credits and then small free monthly credit, but
  network constraints may apply on limited trials.
- Fly.io is usage-based and should be treated as low-cost paid infrastructure.

Production:

- Expect costs from model usage, Postgres, compute, logs/traces, and any paid
  MCP integrations.

Cost controls:

- Set OpenRouter dashboard budget caps.
- Use separate OpenRouter API keys for dev and staging.
- Set `OPHANIX_AGENT_MAX_STEPS`.
- Set `OPHANIX_AGENT_MAX_OUTPUT_TOKENS`.
- Use one explicit low-cost tool-capable model for E2E.
- Stop cloud services when idle.

## Failure Modes And Debugging

### OpenRouter Failures

Symptoms:

- `401 Unauthorized`
- `404 no endpoints for this model`
- `429 rate limit`
- Timeouts
- Tool calls not produced

Debug commands:

```bash
python -m product_platform.real_agent_runtime.cli llm smoke --verbose
python examples/real-agent-runtime/scripts/select_openrouter_model.py
```

Fixes:

- Verify key.
- Switch to explicit current model ID.
- Use paid low-cost model for reproducible E2E.
- Lower max tokens.
- Add retry with backoff for 429 and transient 5xx.

### MCP Server Startup Failures

Symptoms:

- `npx` missing.
- `uvx` missing.
- Server writes non-JSON to stdout.
- Tool list timeout.

Debug commands:

```bash
npx -y @modelcontextprotocol/server-memory
uvx mcp-server-git --repository ../..
python -m product_platform.real_agent_runtime.cli mcp list-tools --verbose
```

Fixes:

- Install Node.js or uv.
- Pin server versions.
- Capture stderr.
- Reject unsafe configs.
- Increase startup timeout only after confirming the server is valid.

### Filesystem Permission Failures

Symptoms:

- Agent cannot read or write sandbox files.
- Files are written outside expected location.

Debug commands:

```bash
ls -la .local/real-agent/sandbox
python -m product_platform.real_agent_runtime.cli mcp call-tool \
  --server filesystem \
  --tool list_allowed_directories
```

Fixes:

- Ensure filesystem MCP server is scoped to `.local/real-agent/sandbox`.
- Resolve all paths before passing config.
- Reject path traversal in custom tools.

### Tool Gateway Failures

Symptoms:

- `403 permission_missing`.
- Missing runtime action rows.
- Upstream unavailable.
- Redacted fields missing or too broad.

Debug commands:

```bash
python -m product_platform.real_agent_runtime.cli tool-gateway smoke --verbose
curl http://127.0.0.1:8088/health
sqlite3 ophanix_product.db "select * from tool_runtime_actions order by created_at desc limit 5;"
```

Fixes:

- Verify product-platform API is running.
- Verify seed data and tool contracts.
- Verify gateway token.
- Match correlation ID between agent DB and Tool Gateway audit UI.

### Database Failures

Symptoms:

- SQLite locked.
- Migration mismatch.
- Postgres SSL failure.

Debug commands:

```bash
python -m product_platform.real_agent_runtime.cli db inspect --verbose
sqlite3 .local/real-agent/agent.sqlite3 "pragma integrity_check;"
```

Fixes:

- Use one writer process for SQLite MVP.
- Add transaction retries.
- Use Postgres for concurrent workers.
- Require `sslmode=require` for Neon.

### Agent Loop Failures

Symptoms:

- Agent loops until max steps.
- Agent ignores tool results.
- Agent calls wrong tool.
- Agent fabricates output after denial.

Debug commands:

```bash
python -m product_platform.real_agent_runtime.cli runs show <run-id> --include-messages --include-tools
tail -n 100 .local/real-agent/logs/agent.log
```

Fixes:

- Strengthen system instructions.
- Reduce tool catalog.
- Use explicit task acceptance criteria.
- Add max cost and max step stop conditions.
- Add denial-specific final answer policy.

## Phased Build Roadmap

### Phase 0 - Research, Credentials, And Environment

Goal:

- Prove OpenRouter, local folders, and product-platform startup are available.

Steps:

1. Create `.env.real-agent`.
2. Set `OPENROUTER_API_KEY`.
3. Run direct OpenRouter HTTP smoke.
4. Start product-platform API locally.
5. Confirm Tool Gateway UI works.
6. Create `.local/real-agent/sandbox`.

Acceptance:

- OpenRouter smoke returns `200`.
- Product Platform API health endpoint returns success.
- Tool Gateway page loads locally.

### Phase 1 - Runtime Skeleton And DB Persistence

Goal:

- Create a CLI that can load config, migrate DB, and persist a run.

Steps:

1. Add `real_agent_runtime` package.
2. Add Typer CLI.
3. Add config loading and redaction.
4. Add SQL migration.
5. Add repository.
6. Add `db migrate`, `db inspect`, `runs list`, and `runs show`.
7. Add unit tests against real SQLite.

Acceptance:

- `db migrate` creates tables.
- `llm smoke` can create a run row after Phase 2.
- Unit tests pass.

### Phase 2 - Real OpenRouter Agent Call

Goal:

- Run a real Pydantic AI agent call through OpenRouter and persist the result.

Steps:

1. Add OpenRouter model factory.
2. Add `llm smoke`.
3. Persist request, response, token usage when available, and errors.
4. Add retry/backoff for transient provider errors.
5. Add integration test marked `real_provider`.

Acceptance:

- `llm smoke` makes a real model call.
- DB contains run and message rows.
- Failure paths are persisted.

### Phase 3 - Real MCP Server Integration

Goal:

- Spawn real MCP servers and expose their tools to the agent.

Steps:

1. Add MCP config parser.
2. Add MCP server startup with Pydantic AI `MCPServerStdio`.
3. Add `mcp config-check`.
4. Add `mcp list-tools`.
5. Add real filesystem MCP E2E that writes to sandbox.
6. Add real git MCP E2E that reads repo state.

Acceptance:

- Tool listing shows filesystem and git tools.
- E2E proves real file write through MCP.
- Server subprocesses shut down cleanly.

### Phase 4 - Tool Gateway MCP Wrapper

Goal:

- Let the agent call governed Ophanix tools through MCP and Tool Gateway.

Steps:

1. Implement `mcp_tool_gateway_server.py`.
2. Add `list_governed_tools`.
3. Add `call_governed_tool`.
4. Add `get_tool_gateway_action`.
5. Add Tool Gateway smoke command.
6. Run allowed and denied real calls.
7. Verify Tool Gateway UI shows both decisions.

Acceptance:

- Agent can invoke a real Tool Gateway contract through MCP.
- Agent DB and Tool Gateway runtime action share correlation ID.
- Denied calls are handled gracefully.

### Phase 5 - Full Agent Run Loop

Goal:

- Run a multi-step task that uses LLM reasoning, MCP tools, Tool Gateway, DB
  persistence, and filesystem artifacts.

Steps:

1. Implement `run --task-file`.
2. Attach MCP toolsets to Pydantic AI agent.
3. Add system instructions and step limits.
4. Persist messages and tool calls.
5. Write final output and run summary.
6. Run Claim Lookup E2E.

Acceptance:

- Real task completes.
- Output file exists.
- Tool Gateway UI shows the action.
- DB contains run, messages, and tool calls.

### Phase 6 - Persistent Memory

Goal:

- Add durable memory that survives process restarts.

Steps:

1. Implement memory repository.
2. Add CLI memory commands.
3. Add memory tools to the agent.
4. Add task summary extraction.
5. Run two-task memory E2E.

Acceptance:

- Memory persists.
- Later task uses earlier memory.
- Memory is tenant/user scoped.

### Phase 7 - Observability

Goal:

- Make every run debuggable from CLI logs, DB rows, traces, and Tool Gateway UI.

Steps:

1. Add structlog JSON logs.
2. Add run/correlation IDs everywhere.
3. Add optional Logfire instrumentation.
4. Add optional Langfuse OpenTelemetry export.
5. Add `observability smoke`.

Acceptance:

- Logs are valid JSON lines.
- Trace shows model spans and tool spans when enabled.
- Tool Gateway UI correlates with agent DB.

### Phase 8 - Cloud Persistence

Goal:

- Run the same E2E with a real cloud Postgres database.

Steps:

1. Create Neon Postgres database.
2. Set `OPHANIX_AGENT_DATABASE_URL`.
3. Run migrations.
4. Run Claim Lookup E2E.
5. Inspect rows in Neon SQL console.

Acceptance:

- E2E passes with Postgres.
- No SQLite-only assumptions remain in runtime code.

### Phase 9 - Production Hardening

Goal:

- Prepare for safe long-running experimentation.

Steps:

1. Pin MCP server package versions.
2. Add tool allowlists and approval policies.
3. Add per-run and per-day cost guards.
4. Add queue-based task execution.
5. Add timeout and retry policy per tool.
6. Add secret redaction tests.
7. Add prompt-injection tests for untrusted file content.
8. Add Postgres connection pooling.
9. Add backup/restore instructions.
10. Evaluate LangGraph for durable workflow checkpoints.

Acceptance:

- The runtime can run repeatedly without manual cleanup.
- Costs are capped.
- Sensitive tools require approval.
- A failed run can be inspected and retried.

## Implementation Rules For The AI Agent

Follow these rules while executing this plan:

1. Do not commit or push changes.
2. Do not mock OpenRouter, MCP, database, or Tool Gateway in the E2E path.
3. Keep deterministic fixture data small and explicit.
4. Run the smallest useful test after each implementation step.
5. Inspect command output before continuing.
6. Store every failure and fix in an execution log under:

```text
docs/product-platform-worktree/execution-logs/08-real-agent-runtime/
```

7. Before starting a new phase, read the execution logs and this plan.
8. Do not enable broad filesystem or shell access for MCP servers.
9. Redact all API keys and gateway tokens in logs, DB rows, and final output.
10. Prefer CLI commands over manual UI steps, except final visual confirmation in
    the Tool Gateway UI.

## Sources Consulted

- OpenRouter Quickstart:
  https://openrouter.ai/docs/quickstart
- OpenRouter Pricing and rate limits:
  https://openrouter.ai/pricing
- OpenRouter Agent SDK:
  https://openrouter.ai/docs/agent-sdk/overview
- Pydantic AI OpenRouter provider:
  https://pydantic.dev/docs/ai/models/openrouter/
- Pydantic AI MCP client:
  https://pydantic.dev/docs/ai/mcp/client/
- Pydantic AI Logfire integration:
  https://pydantic.dev/docs/ai/integrations/logfire/
- MCP transports:
  https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
- MCP security best practices:
  https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices
- MCP reference servers:
  https://github.com/modelcontextprotocol/servers
- Ollama OpenAI compatibility:
  https://docs.ollama.com/api/openai-compatibility
- LangChain MCP adapters:
  https://docs.langchain.com/oss/python/langchain/mcp
- LangGraph persistence:
  https://docs.langchain.com/oss/python/langgraph/persistence
- OpenAI Agents SDK MCP support:
  https://openai.github.io/openai-agents-python/mcp/
- Langfuse OpenTelemetry:
  https://langfuse.com/integrations/native/opentelemetry
- Neon pricing:
  https://neon.com/pricing
- Render free deployment:
  https://render.com/docs/free
- Railway free trial:
  https://docs.railway.com/pricing/free-trial
- Fly.io pricing:
  https://fly.io/pricing/
