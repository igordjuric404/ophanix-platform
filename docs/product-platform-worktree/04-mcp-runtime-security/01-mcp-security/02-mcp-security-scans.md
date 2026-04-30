# MCP Security Scans

## Feature Scope

Run and persist MCP tool security scans. The feature detects prompt injection, hidden Unicode, encoded payloads, schema abuse, rug-pull changes, cross-server risk, and typosquatting findings using existing scanner logic.

## Existing Repo Assets To Reuse

- `MCPSecurityScanner` from `packages/agent-os/src/agent_os/mcp_security.py`.
- MCP response scanner from `packages/agent-os/src/agent_os/mcp_response_scanner.py` for later response checks.

## Out Of Scope

- Proxy enforcement.
- Human approval workflow.
- Third-party risk feeds.

## Data Model

Tables:

- `mcp_scan_runs`: id, server_id, status, started_at, finished_at, summary_json, error_message.
- `mcp_findings`: id, scan_run_id, tool_id, finding_type, severity, title, description, evidence_json, recommendation, status, created_at.
- `mcp_scan_baselines`: id, server_id, tool_id, schema_hash, accepted_by, accepted_at, reason.

## API Surface

Implement:

- `POST /api/v1/mcp/servers/{id}/scan`
- `GET /api/v1/mcp/scans`
- `GET /api/v1/mcp/scans/{id}`
- `GET /api/v1/mcp/findings`
- `POST /api/v1/mcp/findings/{id}/accept-risk`
- `POST /api/v1/mcp/findings/{id}/resolve`

## UI Surface

MCP Security -> Security Scans.

MCP Security -> Tools finding badges.

MCP finding detail drawer.

## Implementation Phases

### Phase 1: Scanner Adapter

Steps:

1. Wrap existing `MCPSecurityScanner`.
2. Convert product tool definitions into scanner input.
3. Normalize scanner output into finding records.
4. Preserve raw evidence.

Tests:

- Unit test scanner adapter identifies prompt injection fixture.
- Unit test hidden Unicode fixture creates finding.
- Unit test no findings for safe tool fixture.

### Phase 2: Scan Run Job

Steps:

1. Add background job for server scan.
2. Persist run status and findings.
3. Handle scanner exceptions as failed run.
4. Emit scan started/completed audit events.

Tests:

- Integration test successful scan creates run and findings.
- Integration test failed scan records error.
- Integration test completion emits audit event.

### Phase 3: Finding Lifecycle

Steps:

1. Add finding statuses: open, accepted risk, resolved, false positive.
2. Require reason for accepted risk and false positive.
3. Link finding to tool version and scan run.
4. Reopen finding if future tool version still has issue.

Tests:

- API test accept risk requires reason.
- API test resolved finding persists status.
- Unit test changed schema can reopen finding.

### Phase 4: UI

Steps:

1. Build scan run history.
2. Build findings table with severity filters.
3. Build finding detail drawer with evidence and recommendation.
4. Add accept risk and resolve actions.

Tests:

- Component test findings table renders severity.
- Component test finding drawer shows evidence.
- Component test accept risk modal requires reason.

## Overall Validation

- Scan demo MCP server containing safe and unsafe tools.
- Confirm findings appear.
- Accept one risk and resolve another.
- Confirm status and audit events.

## Dependencies

- MCP server and tool registry.
- Background worker.
- Event pipeline.

## Definition Of Done

- MCP security posture is based on persisted scan results, not one-off CLI output.
