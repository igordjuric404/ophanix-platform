# Tool Decision Feed UI

## Feature Scope

Build the product UI that shows tool gateway runtime activity. Operators can see allowed, denied, failed, and redacted calls, inspect the decision reason, and navigate to the related agent, tool, and permission binding.

## Atomic Boundary

This plan is complete when the UI can render a runtime action feed from API fixtures and show detail for one action. It is independently testable with mocked API responses.

## Objectives

- Make the gateway visibly useful to operators.
- Explain why a call was allowed or denied.
- Support scanning and filtering during demos and investigations.
- Link gateway events back to the registry and permission model.

## Existing Repo Assets To Reuse

- Product platform frontend shell in `packages/product-platform/frontend`.
- Existing table, filter, and detail drawer patterns in platform feature views.
- Runtime Action Audit Store endpoints.
- Agent and tool detail routes when available.

## Out Of Scope

- Creating or editing tool permissions from the feed.
- Approval workflow.
- Real-time websocket streaming.
- Advanced analytics dashboards.

## Data Model

No new database tables.

UI consumes:

- `GET /api/v1/tool-runtime/actions`
- `GET /api/v1/tool-runtime/actions/{id}`

## API Surface

No new API routes required.

The UI should require the runtime action list and detail endpoints from the audit store plan.

## UI Surface

Tool Gateway -> Decisions:

- Filter bar for status, decision, agent, tool, and time range.
- Dense table with time, agent, tool, decision, reason, upstream status, latency, and correlation id.
- Detail drawer with request metadata, payload summary, response summary, event timeline, linked permission, and matched policy.
- Empty, loading, and error states.

Agent Detail -> Runtime:

- Filtered view of decisions for that agent.

Tool Detail -> Runtime:

- Filtered view of decisions for that tool.

## Implementation Phases

### Phase 1: Feed Table

Steps:

1. Add Tool Gateway navigation item for Decisions.
2. Build API client methods for action list and detail.
3. Render table with status and decision indicators.
4. Add pagination and basic loading/error states.

Tests:

- Component test feed table renders allowed and denied rows.
- Component test loading state renders without layout shift.
- Component test API error shows recoverable error state.
- Component test pagination calls the API with the expected cursor or page.

### Phase 2: Filters

Steps:

1. Add status, decision, agent, tool, and time range filters.
2. Persist filter state in the URL where existing product patterns support it.
3. Reset pagination when filters change.
4. Keep table density suitable for repeated operator use.

Tests:

- Component test status filter calls API with status query.
- Component test tool filter calls API with tool id query.
- Component test reset clears filters.
- Component test URL state restores selected filters.

### Phase 3: Detail Drawer

Steps:

1. Open a detail drawer when a row is selected.
2. Show decision reason, matched policy, permission binding, payload summary, response summary, and event timeline.
3. Link to agent detail and tool detail.
4. Clearly mark redacted or hidden response values.

Tests:

- Component test drawer renders denied reason code.
- Component test drawer shows event timeline.
- Component test links include agent and tool ids.
- Component test redacted response marker appears when redaction was applied.

## Independent Verification

- Serve mocked action list data with allowed, denied, upstream failed, and redacted rows.
- Confirm the table renders all statuses.
- Apply a denied filter and confirm only denied rows are shown.
- Open a denied row and confirm the detail drawer explains the reason and links to the agent and tool.

## Dependencies

- Runtime Action Audit Store.
- Frontend shell navigation.
- Agent detail and tool detail routes.

## Definition Of Done

- Operators can inspect gateway decisions from the product UI.
- Decision reasons, correlation ids, and linked resources are visible.
- The UI is testable from API fixtures without a live upstream business API.

