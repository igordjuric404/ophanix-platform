# Response Handling And Redaction

## Feature Scope

Validate and shape upstream responses before returning them to the external agent. This plan applies output schema checks, safe error normalization, response size limits, and configurable redaction for sensitive fields.

## Atomic Boundary

This plan is complete when the gateway can process an upstream response into a safe agent-facing response. It is independently testable with fixture responses and does not require a real upstream service.

## Objectives

- Prevent sensitive upstream details from leaking to agents.
- Keep returned data aligned with the tool output contract.
- Preserve enough metadata for debugging and audit.
- Support future visibility flags, such as "store but do not expose to agent".

## Existing Repo Assets To Reuse

- `CredentialRedactor` from `packages/agent-os/src/agent_os/credential_redactor.py`.
- Tool output schemas from Tool Contract Registry.
- Product error format from the API shell.
- Audit event conventions.

## Out Of Scope

- Request payload validation.
- Upstream routing and forwarding.
- LLM-specific response filtering.
- Human approval workflows.

## Data Model

Tables:

- `tool_response_policies`: id, organization_id, environment_id, tool_id, max_response_bytes, redaction_rules_json, expose_to_agent, store_full_response, status, created_at, updated_at.

Optional columns on audit or execution records:

- `response_status_code`
- `response_summary_json`
- `response_redaction_applied`
- `response_schema_valid`

## API Surface

Implement:

- `GET /api/v1/tools/{tool_id}/response-policy`
- `PATCH /api/v1/tools/{tool_id}/response-policy`

The invocation endpoint uses response handling internally.

## UI Surface

Tool Detail -> Response Handling:

- Max response size.
- Redaction rules.
- Agent visibility toggle.
- Output schema validation status.

## Implementation Phases

### Phase 1: Response Policy Store

Steps:

1. Add response policy table.
2. Create default policy for new tools.
3. Add repository methods to fetch and update policy.
4. Validate max response size and rule shape.

Tests:

- Integration test default policy is created.
- Unit test invalid max response size is rejected.
- API test updates response policy.

### Phase 2: Output Validation

Steps:

1. Validate successful upstream responses against the tool output schema when present.
2. Mark validation result in execution metadata.
3. Return a controlled gateway error when strict validation fails.
4. Allow non-strict mode to pass response with a warning marker.

Tests:

- Unit test valid output schema passes.
- Unit test invalid output schema fails in strict mode.
- Unit test invalid output schema passes with warning in non-strict mode.

### Phase 3: Redaction And Visibility

Steps:

1. Apply credential and sensitive-pattern redaction to response bodies.
2. Enforce max response size before returning to the agent.
3. Respect `expose_to_agent` by returning only metadata when disabled.
4. Store response summary without plaintext secrets.

Tests:

- Unit test token-like values are redacted.
- Unit test oversized response is blocked or truncated according to policy.
- API test hidden response returns metadata but not body.
- Integration test audit record marks redaction applied.

## Independent Verification

- Configure a tool with an output schema and redaction rule.
- Feed a fixture upstream response containing a secret-like value.
- Confirm the agent-facing response is redacted.
- Confirm the audit summary records schema validity and redaction status.

## Dependencies

- Tool Contract Registry.
- Tool Invocation Endpoint.
- Upstream Forwarding Adapter.
- Event audit pipeline.

## Definition Of Done

- Upstream responses are validated against tool output contracts when configured.
- Sensitive values are redacted before reaching agents or audit summaries.
- Operators can configure response visibility and size limits per tool.

