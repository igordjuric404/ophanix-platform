# MCP Proxy Traffic And Approvals

## Feature Scope

Record MCP gateway traffic and build the approval workflow for risky tool calls. The feature shows allowed, denied, escalated, sanitized, and rate-limited calls and lets authorized users approve or deny pending tool calls.

## Existing Repo Assets To Reuse

- `MCPGateway` from `packages/agent-os/src/agent_os/mcp_gateway.py`.
- MCP response scanner.
- Policy evaluation adapter.
- Trust thresholds.

## Out Of Scope

- MCP server registration.
- Tool definition scanning.

## Data Model

Tables:

- `mcp_tool_calls`: id, organization_id, environment_id, server_id, tool_id, source_agent_id, params_summary_json, decision, matched_policy_id, sanitizer_action, latency_ms, correlation_id, created_at.
- `mcp_approvals`: id, tool_call_id, status, requested_by_agent_id, approved_by_user_id, decision_reason, requested_at, decided_at.
- `mcp_rate_limits`: id, target_type, target_id, window_seconds, max_calls, enabled.

## API Surface

Implement:

- `POST /api/v1/mcp/proxy/call`
- `GET /api/v1/mcp/traffic`
- `GET /api/v1/mcp/approvals`
- `POST /api/v1/mcp/approvals/{id}/approve`
- `POST /api/v1/mcp/approvals/{id}/deny`
- `GET /api/v1/mcp/rate-limits`
- `POST /api/v1/mcp/rate-limits`

## UI Surface

MCP Security -> Proxy Traffic.

MCP Security -> Approvals.

MCP Security -> Rate Limits.

## Implementation Phases

### Phase 1: Proxy Call Wrapper

Steps:

1. Add endpoint that accepts source agent, server, tool, params, and correlation id.
2. Resolve active policies and trust threshold.
3. Call existing MCP gateway or gateway adapter.
4. Persist tool call decision and metadata.

Tests:

- API test allowed call is persisted.
- API test denied call is persisted.
- Unit test missing agent identity fails closed.
- Integration test policy evaluation is linked.

### Phase 2: Escalation And Approval

Steps:

1. When gateway returns escalation, create approval record.
2. Do not execute tool until approved.
3. Implement approve and deny endpoints.
4. On approval, execute or release queued call according to demo-safe adapter.

Tests:

- API test escalated call creates pending approval.
- API test approve requires Security Admin or Operator permission.
- API test deny requires reason.
- Integration test approval decision emits audit event.

### Phase 3: Response Scanning And Sanitization

Steps:

1. Run response scanner on tool output.
2. Store sanitizer action.
3. Return sanitized response to caller.
4. Emit audit event when response is sanitized or blocked.

Tests:

- Unit test response scanner flags credential fixture.
- API test sanitized response hides sensitive value.
- Integration test sanitizer action persisted.

### Phase 4: Traffic And Approval UI

Steps:

1. Build proxy traffic table with filters.
2. Build approval queue with context, policy, trust, params summary.
3. Add approve/deny modals with required reason.
4. Add rate-limit configuration page.

Tests:

- Component test traffic table renders allowed and denied calls.
- Component test approval detail shows matched policy.
- Component test approve action requires reason where configured.

## Overall Validation

- Run allowed CRM call.
- Run refund call requiring approval.
- Approve it.
- Run denied shell tool call.
- Confirm all traffic and approvals are visible and auditable.

## Dependencies

- MCP server/tool registry.
- Policy simulator/evaluation.
- Trust thresholds.
- Event pipeline.

## Definition Of Done

- MCP tool execution is governed through product-visible traffic, approval, and audit state.
