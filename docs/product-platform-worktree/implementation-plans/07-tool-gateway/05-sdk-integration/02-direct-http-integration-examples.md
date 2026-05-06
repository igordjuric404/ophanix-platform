# Direct HTTP Integration Examples

## Feature Scope

Create tested examples that show teams how to call the Tool Gateway without an SDK. These examples demonstrate credential use, request shape, denied responses, allowed responses, and correlation id handling.

## Atomic Boundary

This plan is complete when direct HTTP examples can run against a local or mocked gateway and prove the public invocation contract. It is independently testable without SDK code.

## Objectives

- Support teams that do not want an SDK dependency.
- Make the gateway contract concrete for early adopters.
- Provide demo fixtures for allowed and denied calls.
- Keep examples aligned with the real API contract.

## Existing Repo Assets To Reuse

- Existing quickstart and examples folders.
- Tool Invocation Endpoint.
- Local demo compose plans from `06-demo-delivery`.
- Product platform test fixtures.

## Out Of Scope

- Full production deployment docs.
- Language-specific SDK behavior.
- Credential issuance UI walkthrough.
- OAuth or MCP authorization metadata.

## Data Model

No database tables.

Example fixtures:

- Active demo agent.
- Active demo tool such as `claims.lookup`.
- Active agent-tool permission.
- Denied fixture without permission.

## API Surface

Examples consume:

- `POST /api/v1/tools/{tool_name}/invoke`
- `GET /api/v1/tool-runtime/actions`

Example commands should show:

- Bearer token header.
- Correlation id header.
- JSON payload.
- Allowed response.
- Denied response.

## UI Surface

No new UI. The examples should point operators to Tool Gateway -> Decisions after calls are made.

## Implementation Phases

### Phase 1: Example Fixtures

Steps:

1. Add seed data for demo agent, demo tool, upstream target, and permission.
2. Add a second fixture that intentionally lacks permission.
3. Provide deterministic token placeholders for local-only tests.
4. Ensure fixtures do not contain production secrets.

Tests:

- Integration test fixture creates active agent, tool, target, and permission.
- Integration test denied fixture has no active permission.
- Security test no real secret values are committed.

### Phase 2: HTTP Examples

Steps:

1. Add a curl example for allowed invocation.
2. Add a curl example for denied invocation.
3. Add a minimal Python `requests` example for direct HTTP usage.
4. Include expected response snippets with request id and decision fields.

Tests:

- Documentation test or smoke test verifies curl command shape against local gateway.
- Unit test expected response snippets match current response model.
- Smoke test direct Python example handles allowed and denied responses.

### Phase 3: Audit Verification Example

Steps:

1. Add a short verification step that queries runtime actions after invocation.
2. Show filtering by correlation id.
3. Confirm allowed and denied calls appear in the decision feed API.
4. Keep examples short enough for demo delivery.

Tests:

- Smoke test invokes allowed call and finds matching audit record.
- Smoke test invokes denied call and finds matching denied record.
- Smoke test correlation id links invocation response and runtime action.

## Independent Verification

- Start the local product API with seeded demo data.
- Run the allowed curl example and confirm an allowed response.
- Run the denied curl example and confirm a `403`.
- Query runtime actions by correlation id and confirm both calls are visible.

## Dependencies

- Tool Invocation Endpoint.
- Upstream Forwarding Adapter.
- Runtime Action Audit Store.
- Local demo compose or equivalent local product API startup.

## Definition Of Done

- Teams can integrate with the gateway using plain HTTP.
- Examples cover both allowed and denied outcomes.
- Examples prove the audit trail from request to decision feed.

