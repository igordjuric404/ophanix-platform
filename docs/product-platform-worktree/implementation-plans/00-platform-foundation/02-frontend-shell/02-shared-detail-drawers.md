# Shared Detail Drawers

## Feature Scope

Build reusable detail drawers and panels for audit events, policy decisions, agents, trust changes, MCP calls, runtime actions, workflow runs, and approval requests. These drawers keep feature pages consistent and make correlated evidence easy to inspect.

## Existing Repo Assets To Reuse

- Audit event fields from the event pipeline plan.
- Dashboard specification detail drawer requirements from `docs/product-platform-plan/04-dashboard-specification.md`.

## Out Of Scope

- Feature-specific tables and charts.
- Compliance report builder.

## Data Model

No new tables. Uses existing IDs from feature resources and audit events.

## API Surface

Consume:

- `GET /api/v1/audit/events/{id}`
- `GET /api/v1/audit/events?correlation_id=...`
- Future feature detail endpoints as they are implemented.

## UI Surface

Reusable drawers:

- Audit Event Drawer.
- Policy Decision Drawer.
- Agent Snapshot Drawer.
- Trust Change Drawer.
- MCP Call Drawer.
- Runtime Action Drawer.
- Workflow Run Drawer.
- Approval Request Drawer.

## Implementation Phases

### Phase 1: Drawer Framework

Steps:

1. Build a generic drawer component with title, subtitle, status badge, tabs, and action area.
2. Add loading, empty, and error states.
3. Add keyboard close and route-safe deep link support.

Tests:

- Component test opens and closes drawer.
- Component test renders loading and error states.
- Accessibility test verifies focus handling.

### Phase 2: Audit Event Drawer

Steps:

1. Render event metadata.
2. Render raw payload JSON.
3. Render hash verification status.
4. Render related events by correlation id.

Tests:

- Component test renders event metadata.
- Component test renders raw JSON.
- Mock API test loads related events.

### Phase 3: Decision And Action Drawers

Steps:

1. Implement Policy Decision Drawer using audit event payload fields.
2. Implement MCP Call Drawer with tool, params classification, decision, sanitizer action.
3. Implement Runtime Action Drawer with session, ring, sandbox, saga context.
4. Add standard "open in Audit Explorer" link.

Tests:

- Component test policy decision shows matched rule and reason.
- Component test MCP call shows tool and decision.
- Component test runtime action shows ring and sandbox status.

### Phase 4: Correlation Navigation

Steps:

1. Add related-events timeline component.
2. Allow clicking related event to replace drawer content.
3. Preserve original context and back navigation inside drawer.

Tests:

- Component test clicking related event loads new event.
- Component test back navigation returns to original event.
- Integration test related timeline handles empty result.

## Overall Validation

- From any feature page, a user can inspect why something happened, what policy matched, what agent acted, and what related events occurred.

## Dependencies

- Frontend shell.
- Event and audit pipeline.

## Definition Of Done

- Shared drawers are available to all feature pages.
- Raw evidence and correlation chains are visible without custom per-page implementations.
