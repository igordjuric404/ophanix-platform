# Tool Gateway Execution Log Overview

Source plans: `docs/product-platform-worktree/implementation-plans/07-tool-gateway`.

## Phase Overview

| # | Phase name | Goal | Status | Biggest checklist items |
|---|---|---|---|---|
| 1 | Tool Contract Registry | Persist, version, validate, and expose callable tool contracts. | Done | Tool definition migrations; repository CRUD and name lookup; schema validation; API routes; lifecycle audit events; registry tests. |
| 2 | Upstream Target Health | Register upstream business API targets and persist health state. | Done | Target and health-check migrations; target repository; health probe adapter; target APIs; health tests. |
| 3 | Gateway Token Verification | Authenticate external agent bearer tokens and resolve a gateway principal. | Done | Authorization parser; token hashing; credential lookup; agent lifecycle checks; safe verification events. |
| 4 | Agent Tool Permission Bindings | Grant, list, pause, revoke, and expire agent-to-tool permissions. | Done | Permission migrations; active lookup; API routes; reasoned lifecycle changes; expiration handling. |
| 5 | Tool Policy Decision | Produce deterministic allow/deny decisions and persist reasoned decision records. | Done | Decision models; payload summarization; deterministic checks; policy hook; decision tests. |
| 6 | Tool Invocation Endpoint | Add the external `/api/v1/tools/{tool_name}/invoke` contract. | Done | Gateway auth dependency; payload validation; policy call; mock executor; denied-call behavior. |
| 7 | Upstream Forwarding Adapter | Forward allowed invocations to registered upstream HTTP targets. | Done | Executor interface; target resolution; URL building; timeout/error handling; HTTP mock tests. |
| 8 | Response Handling And Redaction | Validate, size-limit, redact, and shape upstream responses. | Done | Response policy store; output validation; redaction; visibility controls; response tests. |
| 9 | Runtime Action Audit Store | Persist gateway runtime actions and event timelines. | Done | Runtime action migrations; write paths from gateway; read API; filters; security assertions. |
| 10 | Tool Decision Feed UI | Render operator-visible gateway decisions with filters and detail drawer. | Done | Navigation; API client; dense table; filters; drawer; component tests. |
| 11 | Python SDK Wrapper | Provide a thin typed Python client for calling the Tool Gateway. | Done | Client config; token provider; `call_tool`; error mapping; discovery helpers; SDK tests. |
| 12 | Direct HTTP Integration Examples | Provide tested direct HTTP examples and demo fixtures. | Done | Demo seed fixtures; curl examples; Python requests example; audit verification smoke tests. |

## Working Notes

- Current active phase: Complete. All Tool Gateway phases 1-12 are done.
- Assumption: the recommended build order in `07-tool-gateway/README.md` is mandatory ordering, so no later phase starts until the current phase has passing targeted tests.
- External docs consulted:
  - `jsonschema` validation docs: `Draft202012Validator.check_schema` validates JSON Schemas against the draft meta-schema.
  - HTTPX timeout docs: per-request and client timeouts raise timeout exceptions after inactivity.
- Phase 4 completed: added permission/history tables, repository grant/list/update/pause/revoke/active lookup, expiration marking, product API routes, RBAC, audit events, and 14 focused permission tests. All Tool Gateway tests passed through Phase 4 (55 tests).
- Phase 5 completed: added policy decision persistence, typed decision models, redacted payload summaries, deterministic allow/deny service, fail-closed policy hook, and 12 focused decision tests. All Tool Gateway tests passed through Phase 5 (67 tests).
- Phase 6 completed: added the external invocation endpoint, gateway bearer auth integration, request/correlation propagation, payload validation, decision calls, pluggable in-memory executor, denied non-execution behavior, and 10 focused invocation tests. All Tool Gateway tests passed through Phase 6 (77 tests).
- Phase 7 completed: added structured execution results/errors, upstream target URL building and resolution, default HTTP executor, timeout/connection/upstream-error normalization, and 12 focused forwarding tests. All Tool Gateway tests passed through Phase 7 (89 tests).
- Phase 8 completed: added response policy storage and APIs, default policy creation, output schema validation with strict/non-strict behavior, redaction, response size limits, visibility controls, and safe execution metadata. All Tool Gateway tests passed through Phase 8 (99 tests).
- Phase 9 completed: added runtime action/event storage, sanitized summaries, gateway runtime writers, auth-failure audit writes where safely identifiable, and scoped list/detail read APIs. All Tool Gateway tests passed through Phase 9 (113 tests).
- Phase 10 completed: added the Tool Gateway Decisions UI route, runtime action API client hooks, dense feed table, URL-backed filters, detail drawer, event timeline, redaction indicators, route registry/RBAC integration, and frontend tests. Focused UI/route/RBAC tests passed (17 tests), and `npm run build` passed with only Vite's large chunk warning.
- Phase 11 completed: added the thin Python SDK wrapper with token providers, typed call/discovery results, typed denied/gateway errors, `call_tool`, `list_tools`, `get_tool`, opt-in discovery caching, and package-level exports. SDK tests passed (15 tests), and the full Tool Gateway regression passed (128 tests).
- Phase 12 completed: added opt-in direct HTTP local fixtures, allowed/denied curl examples, Python requests example, expected response snippets, runtime action correlation-id filtering, and audit verification smoke tests. Direct HTTP example tests passed (9 tests), full Tool Gateway backend/example regression passed (137 tests), focused frontend Tool Decisions tests passed (17 tests), and frontend build passed with only Vite's large chunk warning.
