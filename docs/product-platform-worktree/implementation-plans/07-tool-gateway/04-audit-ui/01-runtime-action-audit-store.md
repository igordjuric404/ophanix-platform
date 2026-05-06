# Runtime Action Audit Store

## Feature Scope

Persist every gateway action in an audit-friendly runtime log. This includes authentication failures where safe, denied decisions, allowed calls, upstream execution metadata, response handling outcomes, and correlation identifiers.

## Atomic Boundary

This plan is complete when gateway runtime events are stored and queryable without relying on the UI. It is independently testable by invoking gateway services with fake decisions and execution results.

## Objectives

- Make every allow and deny decision explainable after the fact.
- Preserve correlation from external agent request to upstream business API call.
- Store summaries instead of raw sensitive payloads.
- Give the UI a stable read model for runtime activity.

## Existing Repo Assets To Reuse

- Event audit pipeline from `00-platform-foundation/01-control-plane-api/04-event-audit-pipeline.md`.
- `MCPGateway` audit record shape from `packages/agent-os/src/agent_os/mcp_gateway.py`.
- Product DB repository conventions.
- Credential redaction helpers.

## Out Of Scope

- UI tables and filters.
- Long-term archive exports.
- Tamper-evident hash chain storage.
- Approval workflow.

## Data Model

Tables:

- `tool_runtime_actions`: id, organization_id, environment_id, request_id, correlation_id, agent_id, credential_id, tool_id, permission_id, decision_id, action_status, reason_code, upstream_status_code, latency_ms, payload_summary_json, response_summary_json, redaction_applied, error_code, created_at.
- `tool_runtime_action_events`: id, runtime_action_id, event_type, event_summary_json, created_at.

Action status values:

- `authentication_failed`
- `denied`
- `allowed`
- `forwarded`
- `upstream_failed`
- `response_blocked`
- `completed`

## API Surface

Implement read endpoints:

- `GET /api/v1/tool-runtime/actions`
- `GET /api/v1/tool-runtime/actions/{id}`

Gateway internals write to the audit store.

## UI Surface

No UI in this plan. The decision feed UI consumes these endpoints.

## Implementation Phases

### Phase 1: Audit Store

Steps:

1. Create runtime action and runtime action event tables.
2. Add repository methods to create, update, append events, list, and fetch detail.
3. Index by organization, environment, agent, tool, decision, status, and created time.
4. Store redacted payload and response summaries.

Tests:

- Integration test creates runtime action for denied decision.
- Integration test creates runtime action for allowed call.
- Integration test payload summary excludes secret-like values.
- Repository test filters by agent, tool, status, and time.

### Phase 2: Gateway Writers

Steps:

1. Write an action when authentication fails where an agent can be safely identified.
2. Write an action when policy denies a call.
3. Update the action when an allowed call is forwarded.
4. Update the action when response handling completes or blocks.

Tests:

- Integration test denied invocation writes one denied action.
- Integration test allowed invocation writes forwarded and completed states.
- Integration test upstream failure records error code.
- Security test raw bearer token is never stored.

### Phase 3: Read API

Steps:

1. Add list and detail response models.
2. Implement filters for decision, status, agent, tool, and time range.
3. Paginate results.
4. Enforce organization and environment scoping.

Tests:

- API test list returns newest actions first.
- API test filters by denied status.
- API test detail includes event timeline.
- API test cross-organization access is blocked.

## Independent Verification

- Run one allowed tool invocation and one denied invocation.
- Query `/api/v1/tool-runtime/actions`.
- Confirm both records exist with request id, correlation id, agent, tool, decision, and reason.
- Confirm no raw token or unredacted secret appears in stored summaries.

## Dependencies

- Event audit pipeline.
- Gateway Token Verification.
- Tool Policy Decision.
- Tool Invocation Endpoint.
- Response Handling And Redaction.

## Definition Of Done

- Gateway runtime actions are queryable and scoped by tenant and environment.
- Allowed, denied, and failed calls are recorded with stable reason metadata.
- Sensitive request and response data is summarized safely.

